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
import chromadb
from langchain_core.documents import Document
from uuid import uuid4

load_dotenv()  # Load environment variables from .env file

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


class LLMRAGProcessor:
    def __init__(self):
        self.llm = ChatGroq(groq_api_key= GROQ_API_KEY, model_name="Llama-3.1-70b-Versatile")
        self.embeddings = HuggingFaceEmbeddings(model_name="avsolatorio/GIST-small-Embedding-v0")
        self.client = chromadb.PersistentClient(path='chroma_db')
        self.db_vector = Chroma(client=self.client, collection_name='TESTING', embedding_function=self.embeddings)
        # Setup retrieval chain for querying
        self.conversation_retrieval_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type='stuff',
            retriever=self.db_vector.as_retriever(search_type='mmr', search_kwargs={'k': 3, 'lambda_mult': 0.25}),
            return_source_documents=True,
            input_key='input'
            )
        # Initialize specific models for summarizing different elements
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

     # Method to delete document from Chroma DB and user_pdf folder
    def delete_document(self, document_name):
        try:
            # Path ke folder user_pdf tempat dokumen disimpan
            user_pdf_path = 'user_pdf'
            document_path = os.path.join(user_pdf_path, document_name)

            # Cek apakah file ada di folder user_pdf
            if os.path.exists(document_path):
                os.remove(document_path)
                print(f"Dokumen {document_name} berhasil dihapus dari folder user_pdf.")
            else:
                print(f"Dokumen {document_name} tidak ditemukan di folder user_pdf.")

            # Menghapus dokumen berdasarkan metadata 'source' dari Chroma DB
            deletion_result = self.db_vector.delete(where={"source": document_path})

            if deletion_result:
                print(f"Dokumen {document_name} berhasil dihapus dari Chroma DB.")
            else:
                print(f"Dokumen {document_name} tidak ditemukan di Chroma DB.")

            return True  # Dokument berhasil dihapus dari kedua tempat

        except Exception as e:
            print(f"Error deleting document: {e}")
            return False  # Terjadi kesalahan saat penghapusan

    # Process and summarize uploaded document
    def process_uploaded_document(self, document_path):
        try:
            print('unstructured dimulai')

            # Proses dokumen menggunakan unstructured
            elements = partition_pdf(
            filename=document_path,
            strategy='hi_res',
            infer_table_structure=True,
            hi_res_model_name="yolox"
            )

            # Gabungkan teks dari elemen yang tidak kosong
            combined_text = "\n".join([element.text for element in elements if element.text])
            print('element selesai')

            # Split teks menjadi chunk untuk penyimpanan vektor
            text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=80
            )
            chunks = text_splitter.split_text(combined_text)
            documents = [Document(page_content=chunk, metadata={'source': document_path}) for chunk in chunks]
            print('text splitter selesai')

            # Tambahkan dokumen ke Chroma DB
            print("Menambahkan dokumen ke Chroma DB")
            self.db_vector.add_documents(documents=documents)
            print("Dokumen berhasil ditambahkan ke Chroma DB")

            return True

        except Exception as e:
            print(f"Error processing document: {e}")
            return False

        
    def process_prompt(self, prompt, user_uuid):
        formatted_prompt = self.conversation_template.format(input=prompt)
        print('prompt telah diformat')
        chat_history = self.retrieve_chat_history(user_uuid, 8)
        print('chat history berhasil di dapatkan')

        # Use the retrieval chain to get the answer
        print(formatted_prompt)
        print(chat_history)
        print(self.conversation_retrieval_chain)
        
        output = self.conversation_retrieval_chain({'input': formatted_prompt, 'chat_history': chat_history})
        print('test prompt')
        answer = output['result']
        source_documents = output['source_documents']

        self.save_to_database(prompt, answer, user_uuid)

        return answer, source_documents

    # Close any connections if necessary
    def close_connection(self):
        pass
