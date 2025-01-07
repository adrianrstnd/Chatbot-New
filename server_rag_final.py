from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import logging
import os
from llm_rag import LLMRAGProcessor
import uuid

app = Flask(__name__)
app.secret_key = 'testing'  # Necessary for session management
cors = CORS(app, resources={r'/*': {'origins': '*'}})
app.logger.setLevel(logging.ERROR)

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
def index_user():
    return render_template('index_user.html')  # For user interaction
@app.route('/process-message', methods=['POST'])
def process_prompt_route():
    user_prompt = request.json.get('userMessage')
    user_id = session['user_id']

    if not user_prompt:
        return jsonify({'error': 'Tolong Masukkan Prompt.'}), 400

    print('user message:', user_prompt)

    # Pass the user_id to the processor to handle user-specific data
    print('mencoba memproses prompt')
    response, msds_source_documents = processor.process_prompt(user_prompt, user_id)

    print('source document:', msds_source_documents)

    return jsonify({'botResponse': response}), 200

@app.route('/admin')
def index_admin():
    return render_template('index_admin.html')  # For admin to upload documents

@app.route('/process-document', methods=['POST'])
def process_document_route():
    if 'file' not in request.files:
        return jsonify({'botResponse': 'Tolong upload file PDF'}), 400

    file = request.files['file']

    # Simpan file langsung di folder 'user_pdf'
    user_pdf_dir = "user_pdf"

    # Buat folder 'user_pdf' jika belum ada
    os.makedirs(user_pdf_dir, exist_ok=True)

    # Simpan file yang diupload langsung dengan nama file aslinya
    msds_doc_path = os.path.join(user_pdf_dir, file.filename)
    file.save(msds_doc_path)

    # Proses dokumen yang diupload
    is_process_ok = processor.process_uploaded_document(msds_doc_path)

    if is_process_ok:
        return jsonify({'botResponse': 'Terima kasih telah mengirimkan PDF, saya telah menganalisis dokumen nya, silahkan bertanya apapun terkait dengan dokumen tersebut'}), 200
    else:
        os.remove(msds_doc_path)
        return jsonify({'botResponse': 'Maaf, saya tidak bisa memproses dokumen ini'}), 400

@app.route('/delete-document', methods=['POST'])
def delete_document_route():
    # Mendapatkan nama dokumen dari request JSON
    document_name = request.json.get('documentName')

    if not document_name:
        return jsonify({'error': 'Tolong masukkan nama file PDF yang ingin dihapus.'}), 400

    try:
        # Path ke folder user_pdf tempat dokumen disimpan
        user_pdf_path = 'user_pdf'
        document_path = os.path.join(user_pdf_path, document_name)

        # Cek apakah file ada, jika ada maka hapus file tersebut
        if os.path.exists(document_path):
            os.remove(document_path)
            print(f"Dokumen {document_name} berhasil dihapus dari folder user_pdf.")
        else:
            return jsonify({'error': f'Dokumen {document_name} tidak ditemukan di folder user_pdf.'}), 400

        # Hapus dokumen dari Chroma DB menggunakan metadata 'source'
        result = processor.delete_document(document_name)
        if result:
            return jsonify({'botResponse': f'Dokumen {document_name} telah dihapus dari folder dan Chroma DB.'}), 200
        else:
            return jsonify({'error': f'Gagal menghapus dokumen {document_name} dari Chroma DB.'}), 400

    except Exception as e:
        print(f"Error deleting document: {e}")
        return jsonify({'error': 'Terjadi kesalahan saat menghapus dokumen.'}), 500
    
@app.route('/view-history')
def view_history():
    return render_template('index_history.html')

@app.route('/history', methods=['GET'])
def get_paginated_chat_history():
    try:
        # Ambil parameter dari query string
        month = request.args.get('month')  # Format: MM
        year = request.args.get('year')    # Format: YYYY
        page = request.args.get('page', 1, type=int)  # Halaman saat ini
        limit = 50  # Data per halaman
        offset = (page - 1) * limit

        # # Validasi: jika salah satu kosong, kembalikan respons kosong
        # if not month or not year:
        #     return jsonify({'history': []}), 200  # Data kosong jika filter tidak lengkap
        
        # Query dasar
        base_query = """
            SELECT user_message, bot_response, timestamp 
            FROM conversation_history
        """
        filters = []
        params = []

        # Tambahkan filter hanya jika bulan dan tahun tersedia
        # if month and year:
        #     filters.append("MONTH(timestamp) = %s AND YEAR(timestamp) = %s")
        #     params.extend([month, year])

        # Kondisi berdasarkan kombinasi filter
        if month and month.lower() != "all":
            filters.append("MONTH(timestamp) = %s")
            params.append(month)

        if year:
            filters.append("YEAR(timestamp) = %s")
            params.append(year)

        # Tambahkan filter jika ada
        if filters:
            base_query += " WHERE " + " AND ".join(filters)

        # Sorting secara ascending dan pagination
        base_query += " ORDER BY timestamp ASC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with processor.connect_to_database() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(base_query, tuple(params))
                history = cursor.fetchall()

        # Response dengan data riwayat chatbot
        return jsonify({'history': history}), 200
    except Exception as e:
        print(f"Error retrieving chat history: {e}")
        return jsonify({'error': 'Gagal mengambil data riwayat chatbot.'}), 500
    
@app.teardown_appcontext
def close_db_connection(Exception=None):
    processor.close_connection()

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
