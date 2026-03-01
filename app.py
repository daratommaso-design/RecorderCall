import os, requests, time, traceback, tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY')
TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"
UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
HEADERS = {'authorization': ASSEMBLYAI_API_KEY, 'content-type': 'application/json'}

@app.route('/transcribe', methods=['POST'])
def transcribe():
    file = request.files['file']
    with tempfile.NamedTemporaryFile(delete=False, suffix='.3gp') as tmp:
        file.save(tmp.name)
        temp_file_path = tmp.name
    try:
        # Caricamento e Trascrizione
        audio_response = requests.post(UPLOAD_URL, headers=HEADERS, data=open(temp_file_path, 'rb'))
        audio_url = audio_response.json()['upload_url']
        
        json_body = {
            'audio_url': audio_url,
            'speaker_labels': True,
            'summarization': True,
            'summary_type': 'bullets',
            'summary_model': 'informative',
            'speech_model': 'universal-3-pro',
            'language_code': 'it'
        }
        transcript_id = requests.post(TRANSCRIPT_URL, json=json_body, headers=HEADERS).json()['id']
        
        # Polling
        while True:
            res = requests.get(f"{TRANSCRIPT_URL}/{transcript_id}", headers=HEADERS).json()
            if res['status'] == 'completed': break
            elif res['status'] == 'error': raise RuntimeError(res['error'])
            time.sleep(3)

        # Mappa concettuale dai bullet point
        summary = res.get('summary', '')
        concepts = [s.strip() for s in summary.split('. ') if len(s) > 5][:5]

        return jsonify({
            'id': res['id'],
            'text': res.get('text', ''),
            'utterances': res.get('utterances', []),
            'summary': summary,
            'concept_map': concepts
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        os.unlink(temp_file_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)))
