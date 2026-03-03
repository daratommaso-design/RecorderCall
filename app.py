import os, requests, time, traceback, tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configurazione API AssemblyAI
ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY')
TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"
UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
HEADERS = {'authorization': ASSEMBLYAI_API_KEY, 'content-type': 'application/json'}

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'file' not in request.files: 
        return jsonify({'error': 'Nessun file inviato'}), 400
    
    file = request.files['file']
    # Creazione file temporaneo per gestire l'audio in arrivo
    with tempfile.NamedTemporaryFile(delete=False, suffix='.3gp') as tmp:
        file.save(tmp.name)
        temp_file_path = tmp.name
        
    try:
        # 1. Caricamento del file audio sui server di AssemblyAI
        with open(temp_file_path, 'rb') as f:
            audio_response = requests.post(UPLOAD_URL, headers=HEADERS, data=f)
        
        if audio_response.status_code != 200:
            raise RuntimeError(f"Caricamento fallito: {audio_response.text}")
            
        audio_url = audio_response.json()['upload_url']
        
        # 2. Richiesta di trascrizione ottimizzata per l'Italiano
        # Nota: summarization è False per evitare errori 500 su AssemblyAI
        json_body = {
            'audio_url': audio_url,
            'speaker_labels': True,
            'language_code': 'it'
        }
        
        resp = requests.post(TRANSCRIPT_URL, json=json_body, headers=HEADERS).json()
        if 'error' in resp: 
            raise RuntimeError(f"Errore AssemblyAI: {resp['error']}")
        
        transcript_id = resp['id']
        
        # 3. Polling: attendiamo che l'elaborazione sia completata
        while True:
            res = requests.get(f"{TRANSCRIPT_URL}/{transcript_id}", headers=HEADERS).json()
            if res['status'] == 'completed': 
                break
            elif res['status'] == 'error': 
                raise RuntimeError(res.get('error', 'Elaborazione fallita'))
            time.sleep(3)

        # 4. Recupero dei dati principali
        text = res.get('text', '')
        utterances = res.get('utterances', [])
        
        # 5. LOGICA DI GENERAZIONE RIASSUNTO E MAPPA (Fallback per Italiano)
        # Poiché AssemblyAI non riassume bene in IT, lo facciamo noi via codice
        summary = ""
        concepts = []
        
        if text:
            # Creazione Riassunto: prendiamo le prime 3 frasi del testo
            sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 5]
            if len(sentences) > 0:
                summary = ". ".join(sentences[:3])
                if len(sentences) > 3: 
                    summary += "..."
            
            # Creazione Mappa Concettuale: estraiamo frasi chiave di media lunghezza
            concepts = [s.strip() for s in text.split('.') if 15 < len(s.strip()) < 80][:5]

        # 6. Risposta finale verso l'App Android
        return jsonify({
            'id': res['id'],
            'text': text,
            'utterances': utterances,
            'summary': summary or "Testo troppo breve per generare un riassunto.",
            'concept_map': concepts
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        # Pulizia del file temporaneo sul server
        if os.path.exists(temp_file_path): 
            os.unlink(temp_file_path)

if __name__ == '__main__':
    # Porta dinamica richiesta da Render (default 10000)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
