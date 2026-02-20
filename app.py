import os
import requests
import time
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import tempfile

app = Flask(__name__)
CORS(app)

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

    with tempfile.NamedTemporaryFile(delete=False, suffix='.3gp') as tmp:
        file.save(tmp.name)
        temp_file_path = tmp.name

    try:
        audio_url = upload_file_to_assembly(temp_file_path)
        transcript_id = request_transcription(audio_url)
        result = get_transcription_result(transcript_id)

        # Estrai concetti (primi 5 bullet del riassunto)
        concepts = []
        if result.get('summary'):
            sentences = result['summary'].split('. ')
            concepts = [s.strip() for s in sentences if s][:5]

        output = {
            'id': result['id'],
            'text': result['text'],
            'utterances': result.get('utterances'),
            'summary': result.get('summary'),
            'concept_map': concepts,
            # Rimossa la parte prodotti per semplicità (puoi reinserirla dopo)
        }
        return jsonify(output), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        os.unlink(temp_file_path)

def upload_file_to_assembly(audio_file_path):
    def read_file(file_path):
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(5242880)
                if not data:
                    break
                yield data
    upload_response = requests.post(UPLOAD_URL, headers=HEADERS, data=read_file(audio_file_path))
    return upload_response.json()['upload_url']

def request_transcription(audio_url):
    json_body = {
        'audio_url': audio_url,
        'speaker_labels': True,
        'summarization': True,
        'summary_type': 'bullets'
    }
    response = requests.post(TRANSCRIPT_URL, json=json_body, headers=HEADERS)
    return response.json()['id']

def get_transcription_result(transcript_id):
    polling_endpoint = f"{TRANSCRIPT_URL}/{transcript_id}"
    while True:
        res = requests.get(polling_endpoint, headers=HEADERS).json()
        if res['status'] == 'completed':
            return res
        elif res['status'] == 'error':
            raise RuntimeError(f"Errore: {res['error']}")
        else:
            time.sleep(3)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
