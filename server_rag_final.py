from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import logging
import os
from llm_rag import LLMRAGProcessor
import uuid
import chromadb  # Chroma DB
from chromadb.config import Settings

app = Flask(__name__)
app.secret_key = 'testing'  # Necessary for session management
cors = CORS(app, resources={r'/*': {'origins': '*'}})
app.logger.setLevel(logging.ERROR)

# Initialize Chroma DB with the correct configuration (using Settings)
settings = Settings(chroma_db_impl="sqlite", persist_directory="VECTOR_DB")
chroma_client = chromadb.Client()

# Now use the client to create a collection for storing document embeddings
collection = chroma_client.create_collection(name="pdf_embeddings")
processor = LLMRAGProcessor()

# Create a directory for user PDFs if it doesn't exist
if not os.path.exists('user_pdf'):
    os.makedirs('user_pdf')

@app.before_request
def initialize_db():
    # Ensure the table exists before handling any requests
    processor.create_table_if_not_exists()

@app.before_request
def assign_user_id():
    # Assign a unique ID to each user if not already assigned
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        print(session['user_id'])

@app.route('/')
def chat():
    return render_template('chat.html')

@app.route('/admin')
def admin():
    # Get the list of files in the admin_pdfs directory
    pdf_files = os.listdir('user_pdf')
    return render_template('admin.html', pdf_files=pdf_files)

@app.route('/admin/upload', methods=['POST'])
def admin_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'Please upload a PDF file.'}), 400

    file = request.files['file']
    if file.filename.endswith('.pdf'):
        # Tentukan path untuk menyimpan file di folder user_pdf
        file_path = os.path.join('user_pdf', file.filename)

        # Pastikan folder user_pdf ada
        os.makedirs('user_pdf', exist_ok=True)

        # Simpan file ke folder
        file.save(file_path)

        # Periksa apakah embedding untuk file ini sudah ada di Chroma DB
        if not embeddings_exist(file.filename):
            # Proses dan simpan embeddings ke Chroma DB
            process_and_store_embeddings(file_path, file.filename)

        return redirect(url_for('admin'))

    return jsonify({'error': 'Only PDF files are allowed.'}), 400

@app.route('/admin/delete/<filename>', methods=['POST'])
def admin_delete(filename):
    # Path file langsung di folder user_pdf
    file_path = os.path.join('user_pdf', filename)

    # Debugging path file
    print(f"Attempting to delete file: {file_path}")

    # Periksa apakah file ada
    if os.path.exists(file_path):
        try:
            os.remove(file_path)  # Hapus file
            print(f"File deleted: {file_path}")
            return jsonify({'success': 'File deleted successfully.'}), 200
        except Exception as e:
            print(f"Error deleting file: {e}")
            return jsonify({'error': 'An error occurred while deleting the file.'}), 500
    else:
        print(f"File not found: {file_path}")
        return jsonify({'error': 'File not found.'}), 404

@app.route('/admin/update/<filename>', methods=['POST'])
def admin_update(filename):
    if 'file' not in request.files:
        return jsonify({'error': 'Please upload a new PDF file.'}), 400

    file = request.files['file']
    if file.filename.endswith('.pdf'):
        # Path file langsung di folder user_pdf
        file_path = os.path.join('user_pdf', filename)

        try:
            # Cek apakah file lama ada dan hapus jika ada
            if os.path.exists(file_path):
                os.remove(file_path)  # Menghapus file lama
                print(f"File removed: {file_path}")
            else:
                print(f"File to be updated not found: {file_path}")

            # Simpan file baru
            file.save(file_path)
            print(f"File updated: {file_path}")
            return jsonify({'success': 'File updated successfully.'}), 200
        except Exception as e:
            print(f"Error updating file: {e}")
            return jsonify({'error': 'An error occurred while updating the file.'}), 500

    return jsonify({'error': 'Only PDF files are allowed.'}), 400

@app.route('/process-message', methods=['POST'])
def process_prompt_route():
    user_prompt = request.json.get('userMessage')
    user_id = session['user_id']

    if not user_prompt:
        return jsonify({'error': 'Please enter a prompt.'}), 400

    print('User message:', user_prompt)

    # Pass the user_id to the processor to handle user-specific data
    response, msds_source_documents = processor.process_prompt(user_prompt, user_id)

    print('Source document:', msds_source_documents)

    return jsonify({'botResponse': response}), 200

@app.route('/process-document', methods=['POST'])
def process_document_route():
    user_id = session['user_id']

    if 'file' not in request.files:
        return jsonify({'botResponse': 'Please upload a PDF file.'}), 400

    file = request.files['file']

    # Store file in a user-specific directory
    user_dir_pdf = os.path.join("user_pdf", user_id)
    os.makedirs(user_dir_pdf, exist_ok=True)

    # Remove any existing files in the user's directory
    for existing_file in os.listdir(user_dir_pdf):
        existing_file_path = os.path.join(user_dir_pdf, existing_file)
        os.remove(existing_file_path)

    # Save the new file
    msds_doc_path = os.path.join(user_dir_pdf, file.filename)
    file.save(msds_doc_path)

    # Check if the embeddings already exist in Chroma DB
    if embeddings_exist(file.filename):
        return jsonify({'botResponse': 'This document has already been processed. You can ask questions related to this document.'}), 200
    else:
        # Process and store embeddings in Chroma DB
        process_and_store_embeddings(msds_doc_path, file.filename)
        return jsonify({'botResponse': 'Document processed and embeddings stored. You can now ask questions related to this document.'}), 200

@app.teardown_appcontext
def close_db_connection(Exception=None):
    processor.close_connection()

def embeddings_exist(filename):
    """ Check if embeddings for the given PDF file already exist in Chroma DB """
    try:
        # Query ChromaDB untuk metadata yang cocok dengan filename
        results = collection.get(where={"filename": filename})
        return len(results["ids"]) > 0
    except Exception as e:
        app.logger.error(f"Error checking embeddings: {e}")
        return False

def process_and_store_embeddings(file_path, filename):
    """ Process the PDF, create embeddings, and store in Chroma DB """
    # Extract text and create embeddings
    text = processor.extract_text_from_pdf(file_path)
    embeddings = processor.create_embeddings(text)

    # Store the embeddings in Chroma DB
    collection.add(
        documents=[text],
        metadatas=[{"filename": filename}],
        ids=[str(uuid.uuid4())],
        embeddings=[embeddings]
    )

def delete_embeddings(filename):
    """ Remove embeddings for the given PDF file from Chroma DB """
    collection.delete(metadata={"filename": filename})

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
