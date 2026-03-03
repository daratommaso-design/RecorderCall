import os, requests, time, traceback, tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Recupera la chiave API dalle variabili d'ambiente di Render
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
    
    # Creazione di un file temporaneo per salvare l'audio ricevuto dall'app
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
        
        # 2. Configurazione della trascrizione (Ottimizzata per l'Italiano)
        # Abbiamo rimosso 'summary_model': 'informative' perché non supportato in IT
        json_body = {
            'audio_url': audio_url,
            'speaker_labels': True,
            'summarization': True,
            'summary_type': 'bullets',
            'language_code': 'it' 
        }
        
        # Invio della richiesta di trascrizione
        transcript_response = requests.post(TRANSCRIPT_URL, json=json_body, headers=HEADERS).json()
        
        if 'error' in transcript_response:
            raise RuntimeError(transcript_response['error'])
            
        transcript_id = transcript_response['id']
        
        # 3. Polling: attendiamo che AssemblyAI finisca di elaborare
        while True:
            res = requests.get(f"{TRANSCRIPT_URL}/{transcript_id}", headers=HEADERS).json()
            if res['status'] == 'completed':
                break
            elif res['status'] == 'error':
                raise RuntimeError(res.get('error', 'Elaborazione fallita'))
            time.sleep(3)

        # 4. Elaborazione dei risultati per l'app Android
        summary = res.get('summary', '')
        text = res.get('text', '')
        
        # Generazione automatica dei concetti chiave dai risultati
        concepts = []
        source = summary if summary else text
        if source:
            # Estraiamo alcune frasi significative come 'concetti'
            concepts = [s.strip() for s in source.split('. ') if len(s) > 10][:5]

        return jsonify({
            'id': res['id'],
            'text': text,
            'utterances': res.get('utterances', []),
            'summary': summary or "Audio troppo breve per generare un riassunto automatico.",
            'concept_map': concepts
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        # Pulizia: eliminiamo il file temporaneo dal server
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

if __name__ == '__main__':
    # Render usa la porta 10000 di default
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
