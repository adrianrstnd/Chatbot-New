import os
from dotenv import load_dotenv
from unstructured.partition.pdf import partition_pdf
from langchain_groq import ChatGroq
from langchain.chains import RetrievalQA
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
import torch
import mysql.connector


load_dotenv()  # Load environment variables from .env file

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEVICE = 'cuda:0' if torch.cuda.is_available() else 'cpu'


class LLMRAGProcessor:
    def __init__(self):
        self.llm = ChatGroq(
            groq_api_key='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',
            model_name="Llama-3.1-70b-Versatile"
        )
        self.embeddings = HuggingFaceEmbeddings(model_name="thenlper/gte-small")
        self.vector_db_path = "VECTOR_DB"  # Folder to store vector DB on disk
        self.db_vector = None
        self.conversation_retrieval_chain = None

    def extract_text_from_pdf(self, file_path):
        """
        Extract text content from a PDF file using `unstructured`.
        """
        try:
            # Use unstructured partitioning for PDF extraction
            elements = partition_pdf(
                filename=file_path,
                strategy='hi_res',
                infer_table_structure=True,
                hi_res_model_name="yolox"
            )

            # Combine text from all elements extracted
            combined_element = [element.text for element in elements if element.text]
            combined_text = "\n".join(combined_element)

            return combined_text
        except Exception as e:
            print(f"Error extracting text from PDF using unstructured: {e}")
            return ""

    def create_embeddings(self, text):
        """
        Generate embeddings from the provided text.
        """
        try:
            # Menggunakan HuggingFaceEmbeddings untuk membuat embeddings
            return self.embeddings.embed_documents([text])[0]
        except Exception as e:
            print(f"Error creating embeddings: {e}")
            return None

    def create_chroma_db(self, chunks):
        """
        Create and store embeddings in a new Chroma DB.
        """
        try:
            print("Creating new Chroma DB and storing embeddings...")

            # Create Chroma DB from the provided text chunks
            self.db_vector = Chroma.from_texts(chunks, embedding=self.embeddings)
            self.db_vector.persist(persist_directory=self.vector_db_path)

            print(f"Chroma DB successfully created and saved to {self.vector_db_path}")
        except Exception as e:
            print(f"Error creating Chroma DB: {e}")

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

    def save_to_database(self, user_message, bot_response, user_uuid):
        query = "INSERT INTO conversation_history (user_message, bot_response, user_uuid) VALUES (%s, %s, %s)"
        with self.connect_to_database() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (user_message, bot_response, user_uuid))
            connection.commit()

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

    def load_chromadb(self):
        """Load the existing Chroma DB if it exists."""
        try:
            if os.path.exists(self.vector_db_path):
                print(f"Loading existing Chroma DB from {self.vector_db_path}")
                self.db_vector = Chroma(persist_directory=self.vector_db_path, embedding_function=self.embeddings)
            else:
                print(f"No existing Chroma DB found. You need to process a document first.")
        except Exception as e:
            print(f"Error loading Chroma DB: {e}")

    def process_uploaded_document(self, document_path, user_uuid):
        try:
            print('Extracting text from PDF using unstructured')
            combined_text = self.extract_text_from_pdf(document_path)

            if not combined_text:
                print("No text extracted from PDF.")
                return False

            # Split the combined text into chunks for vector storage
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=800,
                chunk_overlap=80
            )
            chunks = text_splitter.split_text(combined_text)
            print('Text splitting completed')

            # Create or load Chroma DB and store embeddings
            if not self.db_vector:
                self.create_chroma_db(chunks)  # This is the new function
            else:
                print(f"Chroma DB already exists. Using the existing one.")

            # Setup retrieval chain for querying the Chroma DB
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

    def close_connection(self):
        pass
