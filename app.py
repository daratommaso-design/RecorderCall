import os
import requests
import time
import json
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
import tempfile

app = Flask(__name__)
CORS(app)

# Recupera la API Key dalle variabili d'ambiente di Render
ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY')
if not ASSEMBLYAI_API_KEY:
    raise ValueError("No ASSEMBLYAI_API_KEY found in environment variables")

TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"
UPLOAD_URL = "https://api.assemblyai.com/v2/upload"

HEADERS = {
    'authorization': ASSEMBLYAI_API_KEY,
    'content-type': 'application/json'
}

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Crea un file temporaneo per salvare l'audio ricevuto
    with tempfile.NamedTemporaryFile(delete=False, suffix='.3gp') as tmp:
        file.save(tmp.name)
        temp_file_path = tmp.name

    try:
        # 1. Carica il file su AssemblyAI
        print(f"Uploading file: {file.filename}")
        audio_url = upload_file_to_assembly(temp_file_path)
        
        # 2. Richiedi la trascrizione con i parametri corretti
        print(f"Requesting transcription for: {audio_url}")
        transcript_id = request_transcription(audio_url)
        
        # 3. Attendi il completamento (polling)
        result = get_transcription_result(transcript_id)

        # 4. Estrai i concetti chiave dal riassunto (fallback sul testo se manca)
        concepts = []
        if result.get('summary'):
            sentences = result['summary'].split('. ')
            concepts = [s.strip() for s in sentences if s][:5]
        elif result.get('text'):
            # Se l'audio è troppo breve per un riassunto, usiamo le prime frasi
            sentences = result['text'].split('. ')
            concepts = [s.strip() for s in sentences if s][:3]

        output = {
            'id': result['id'],
            'text': result.get('text', ''),
            'utterances': result.get('utterances', []),
            'summary': result.get('summary', 'Riassunto non disponibile per registrazioni molto brevi.'),
            'concept_map': concepts
        }
        
        print("Transcription successful!")
        return jsonify(output), 200

    except Exception as e:
        print("="*50)
        print("ERRORE NEL BACKEND:")
        print(str(e))
        traceback.print_exc()
        print("="*50)
        return jsonify({'error': str(e)}), 500
    finally:
        # Rimuovi sempre il file temporaneo
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

def upload_file_to_assembly(audio_file_path):
    def read_file(file_path):
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(5242880) # 5MB chunks
                if not data:
                    break
                yield data
    
    upload_response = requests.post(
        UPLOAD_URL,
        headers=HEADERS,
        data=read_file(audio_file_path)
    )
    return upload_response.json()['upload_url']

def request_transcription(audio_url):
    # Parametri aggiornati secondo le ultime specifiche AssemblyAI v2
    json_body = {
        'audio_url': audio_url,
        'speaker_labels': True,
        'summarization': True,
        'summary_type': 'bullets',
        'summary_model': 'informative',
        'speech_model': 'universal-3-pro', # Modello più avanzato (stringa, non lista)
        'language_code': 'it' # Forza l'italiano per evitare errori di 'language_detection' su audio brevi
    }
    
    response = requests.post(TRANSCRIPT_URL, json=json_body, headers=HEADERS)
    data = response.json()
    
    if 'error' in data:
        print(f"AssemblyAI API Error: {data}")
        raise RuntimeError(f"AssemblyAI error: {data['error']}")
    
    return data['id']

def get_transcription_result(transcript_id):
    polling_endpoint = f"{TRANSCRIPT_URL}/{transcript_id}"
    while True:
        res = requests.get(polling_endpoint, headers=HEADERS).json()
        if res['status'] == 'completed':
            return res
        elif res['status'] == 'error':
            error_details = res.get('error', 'Unknown processing error')
            raise RuntimeError(f"Errore elaborazione AssemblyAI: {error_details}")
        else:
            print(f"Status: {res['status']}... waiting")
            time.sleep(3)

if __name__ == '__main__':
    # Usa la porta fornita da Render o la 5001 come fallback
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)
