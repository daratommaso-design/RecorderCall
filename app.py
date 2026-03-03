import os, requests, time, traceback, tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Assicurati di aver impostato questa variabile su Render
ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY')
TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"
UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
HEADERS = {'authorization': ASSEMBLYAI_API_KEY, 'content-type': 'application/json'}

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    
    file = request.files['file']
    # Creazione file temporaneo
    with tempfile.NamedTemporaryFile(delete=False, suffix='.3gp') as tmp:
        file.save(tmp.name)
        temp_file_path = tmp.name
        
    try:
        # 1. Caricamento Audio su AssemblyAI
        with open(temp_file_path, 'rb') as f:
            audio_response = requests.post(UPLOAD_URL, headers=HEADERS, data=f)
        
        if audio_response.status_code != 200:
            raise RuntimeError(f"Upload failed: {audio_response.text}")
            
        audio_url = audio_response.json()['upload_url']
        
        # 2. Configurazione Trascrizione (Ottimizzata per Italiano)
        json_body = {
            'audio_url': audio_url,
            'speaker_labels': True,
            'summarization': True,
            'summary_type': 'bullets',
            'language_code': 'it' # Impostato su italiano
        }
        
        # Invio richiesta di trascrizione
        resp = requests.post(TRANSCRIPT_URL, json=json_body, headers=HEADERS).json()
        if 'error' in resp: raise RuntimeError(resp['error'])
        transcript_id = resp['id']
        
        # 3. Polling (Attesa completamento)
        while True:
            res = requests.get(f"{TRANSCRIPT_URL}/{transcript_id}", headers=HEADERS).json()
            if res['status'] == 'completed': 
                break
            elif res['status'] == 'error': 
                raise RuntimeError(res.get('error', 'Processing failed'))
            time.sleep(3)

        # 4. Elaborazione Risultati
        summary = res.get('summary', '')
        text = res.get('text', '')
        
        # Generazione Concetti Chiave dai risultati
        concepts = []
        source_for_concepts = summary if summary else text
        if source_for_concepts:
            # Prende le prime frasi come concetti
            concepts = [s.strip() for s in source_for_concepts.split('. ') if len(s) > 10][:5]

        return jsonify({
            'id': res['id'],
            'text': text,
            'utterances': res.get('utterances', []),
            'summary': summary or "Audio troppo breve per un riassunto automatico.",
            'concept_map': concepts
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        # Pulizia file temporaneo
        if os.path.exists(temp_file_path): 
            os.unlink(temp_file_path)

if __name__ == '__main__':
    # Porta dinamica per Render
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
