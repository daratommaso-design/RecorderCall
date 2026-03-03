import os, requests, time, traceback, tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY')
TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"
UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
HEADERS = {
    'authorization': ASSEMBLYAI_API_KEY, 
    'content-type': 'application/json'
}

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'file' not in request.files: 
        return jsonify({'error': 'Nessun file inviato'}), 400
    
    file = request.files['file']
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.3gp') as tmp:
        file.save(tmp.name)
        temp_file_path = tmp.name
        
    try:
        # 1. Caricamento dell'audio su AssemblyAI
        with open(temp_file_path, 'rb') as f:
            audio_response = requests.post(UPLOAD_URL, headers=HEADERS, data=f)
        
        if audio_response.status_code != 200:
            raise RuntimeError(f"Upload fallito: {audio_response.text}")
            
        audio_url = audio_response.json()['upload_url']
        
        # 2. Configurazione della trascrizione (senza summarization per italiano)
        json_body = {
            'audio_url': audio_url,
            'speaker_labels': True,
            'language_code': 'it',
            'speech_models': ['universal-2']  # Modello specificato (richiesto dall'API)
        }
        
        # Invio della richiesta di trascrizione
        transcript_response = requests.post(TRANSCRIPT_URL, json=json_body, headers=HEADERS)
        
        if transcript_response.status_code != 200:
            raise RuntimeError(f"Errore AssemblyAI: {transcript_response.text}")
        
        transcript_data = transcript_response.json()
        
        if 'error' in transcript_data:
            raise RuntimeError(transcript_data['error'])
            
        transcript_id = transcript_data['id']
        
        # 3. Polling: attendiamo che AssemblyAI finisca di elaborare
        while True:
            res = requests.get(f"{TRANSCRIPT_URL}/{transcript_id}", headers=HEADERS).json()
            if res['status'] == 'completed':
                break
            elif res['status'] == 'error':
                raise RuntimeError(res.get('error', 'Elaborazione fallita'))
            time.sleep(3)

        # 4. Elaborazione dei risultati per l'app Android
        text = res.get('text', '')
        # Se vuoi generare un riassunto semplice localmente, puoi farlo qui,
        # altrimenti restituisci solo il testo.
        summary = ""  # Opzionale, potresti creare un riassunto con un altro metodo

        return jsonify({
            'id': res['id'],
            'text': text,
            'utterances': res.get('utterances', []),
            'summary': summary,
            'concept_map': []  # Vuoto, oppure puoi generarlo dal testo
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
