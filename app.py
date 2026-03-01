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
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    with tempfile.NamedTemporaryFile(delete=False, suffix='.3gp') as tmp:
        file.save(tmp.name)
        temp_file_path = tmp.name
    try:
        # Upload
        with open(temp_file_path, 'rb') as f:
            audio_response = requests.post(UPLOAD_URL, headers=HEADERS, data=f)
        audio_url = audio_response.json()['upload_url']
        
        # Configurazione parametri (Aggiornata per evitare 500)
        json_body = {
            'audio_url': audio_url,
            'speaker_labels': True,
            'summarization': True,
            'summary_type': 'bullets',
            'summary_model': 'informative',
            'speech_models': ['universal-3-pro'], # DEVE ESSERE UNA LISTA
            'language_code': 'it' # Forza italiano per evitare errori su audio brevi
        }
        
        resp = requests.post(TRANSCRIPT_URL, json=json_body, headers=HEADERS).json()
        if 'error' in resp: raise RuntimeError(resp['error'])
        transcript_id = resp['id']
        
        # Polling
        while True:
            res = requests.get(f"{TRANSCRIPT_URL}/{transcript_id}", headers=HEADERS).json()
            if res['status'] == 'completed': break
            elif res['status'] == 'error': raise RuntimeError(res.get('error', 'Processing failed'))
            time.sleep(3)

        # Risultato e Mappa Concettuale
        summary = res.get('summary', '')
        text = res.get('text', '')
        # Fallback concetti se il riassunto è troppo breve
        if summary:
            concepts = [s.strip() for s in summary.split('. ') if len(s) > 5][:5]
        else:
            concepts = [s.strip() for s in text.split('. ') if len(s) > 5][:3]

        return jsonify({
            'id': res['id'],
            'text': text,
            'utterances': res.get('utterances', []),
            'summary': summary or "Audio troppo breve per un riassunto completo.",
            'concept_map': concepts
        }), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(temp_file_path): os.unlink(temp_file_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)))
