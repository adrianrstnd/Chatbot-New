import os
import base64
import pytesseract
import mysql.connector
from dotenv import load_dotenv
from unstructured.partition.pdf import partition_pdf
from langchain_groq import ChatGroq
from langchain.chains import RetrievalQA
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from groq import Groq
import torch

load_dotenv()  # Load environment variables from .env file

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HF_TOKEN = os.getenv("HUGGING_FACE_API_KEY")
DEVICE = 'cuda:0' if torch.cuda.is_available() else 'cpu'


class LLMRAGProcessor:
    def __init__(self):
        self.llm = ChatGroq(groq_api_key='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', model_name="Llama-3.1-70b-Versatile")
        self.embeddings = HuggingFaceEmbeddings(model_name="thenlper/gte-small")
        self.db_vector = None
        self.conversation_retrieval_chain = None

        # Initialize specific models for summarizing different elements
        self.model_llama_table = ChatGroq(groq_api_key='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', model_name='llama-3.3-70b-versatile')
        self.conversation_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert assistant for esa unggul university that is highly proficient at extracting information from information draft"
                ),
                (
                    "human",
                    "question:\n\"{input}\"\nWhen answering questions about the document, ensure to:\n- answer the question based on the document content\n- Clarify complex terms and procedures when necessary.\n- Use HTML tags for a clear presentation of headers, lists, and instructions. answer it in indonesian language or i will punish you."
                )
            ]   
        )
        
        self.create_table_if_not_exists()

    # Function to create a table in the database for chat history
    def create_table_if_not_exists(self):
        create_table_query = """
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_message TEXT NOT NULL,
            bot_response TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_uuid VARCHAR(36) NOT NULL
        );
        """
        with self.connect_to_database() as connection:
            with connection.cursor() as cursor:
                cursor.execute(create_table_query)
            connection.commit()

    # Database connection function
    def connect_to_database(self):
        return mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DB"),
            connect_timeout=10
        )

    # Save chat history to the database
    def save_to_database(self, user_message, bot_response, user_uuid):
        query = "INSERT INTO conversation_history (user_message, bot_response, user_uuid) VALUES (%s, %s, %s)"
        with self.connect_to_database() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (user_message, bot_response, user_uuid))
            connection.commit()

    # Retrieve chat history for a specific user
    def retrieve_chat_history(self, user_uuid, limit):
        query = "SELECT user_message, bot_response FROM conversation_history WHERE user_uuid = %s ORDER BY timestamp DESC LIMIT %s"
        with self.connect_to_database() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (user_uuid, limit))
                history = cursor.fetchall()

        if history:
            formatted_history = "\n".join([f"User: {user_msg}\nBot: {bot_resp}" for user_msg, bot_resp in reversed(history)])
        else:
            formatted_history = ""  # No chat history available

        return formatted_history


    # Function to delete Chroma DB
    def delete_chromadb(self):
        try:
            self.db_vector.delete_collection()
            print("Deleting previous Chroma DB")
        except:
            pass



    # Process and summarize uploaded document
    def process_uploaded_document(self, document_path, user_uuid):
        try:
            print('unstructured dimulai')
            elements = partition_pdf(
                filename=document_path,
                strategy='hi_res',
                infer_table_structure=True,
                hi_res_model_name="yolox"
            )

            combined_element = []

            for element in elements:
                combined_element.append(element.text)
                print('element selesai')

            # Join only non-empty strings
            combined_text = "\n".join(filter(None, combined_element))


            # Split the combined text into chunks for vector storage
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=800,
                chunk_overlap=80
            )
            chunks = text_splitter.split_text(combined_text)
            print('text splitter selesai')

            # Delete and create a new Chroma DB
            self.delete_chromadb()
            print("Creating a new Chroma DB")
            self.db_vector = Chroma.from_texts(chunks, embedding=self.embeddings)
            print("Successfully created a new Chroma DB")

            # Setup retrieval chain for querying
            self.conversation_retrieval_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type='stuff',
                retriever=self.db_vector.as_retriever(search_type='mmr', search_kwargs={'k': 8, 'lambda_mult': 0.25}),
                return_source_documents=True,
                input_key='pertanyaan'
            )

            return True

        except Exception as e:
            print(f"Error processing document: {e}")
            return False
        
    def process_prompt(self, prompt, user_uuid):
        formatted_prompt = self.conversation_template.format(input=prompt)
        chat_history = self.retrieve_chat_history(user_uuid, 8)

        # Use the retrieval chain to get the answer
        output = self.conversation_retrieval_chain({'pertanyaan': formatted_prompt, 'chat_history': chat_history})
        answer = output['result']
        source_documents = output['source_documents']

        self.save_to_database(prompt, answer, user_uuid)

        return answer, source_documents

    # Close any connections if necessary
    def close_connection(self):
        pass
