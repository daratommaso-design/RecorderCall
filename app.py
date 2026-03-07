import os, requests, time, traceback, tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configurazione API AssemblyAI
# Assicurati che la chiave sia impostata nelle variabili d'ambiente su Render
ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY')
TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"
UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
HEADERS = {'authorization': ASSEMBLYAI_API_KEY, 'content-type': 'application/json'}

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'file' not in request.files: 
        return jsonify({'error': 'Nessun file inviato'}), 400
    
    file = request.files['file']
    
    # Creazione file temporaneo
    with tempfile.NamedTemporaryFile(delete=False, suffix='.3gp') as tmp:
        file.save(tmp.name)
        temp_file_path = tmp.name
        
    try:
        # 1. Caricamento Audio su server AssemblyAI
        with open(temp_file_path, 'rb') as f:
            audio_response = requests.post(UPLOAD_URL, headers=HEADERS, data=f)
        
        if audio_response.status_code != 200:
            raise RuntimeError(f"Caricamento fallito: {audio_response.text}")
            
        audio_url = audio_response.json()['upload_url']
        
        # 2. Richiesta Trascrizione ULTRA-PULITA (Senza parametri che causano errori 500)
        json_body = {
            'audio_url': audio_url,
            'language_code': 'it',
            'speaker_labels': True
        }
        
        print(f"Inviando richiesta ad AssemblyAI: {json_body}")
        
        resp = requests.post(TRANSCRIPT_URL, json=json_body, headers=HEADERS).json()
        if 'error' in resp: 
            print(f"Errore da AssemblyAI: {resp['error']}")
            return jsonify({'error': f"AI Error: {resp['error']}"}), 500
        
        transcript_id = resp['id']
        
        # 3. Polling (Attesa completamento)
        while True:
            res = requests.get(f"{TRANSCRIPT_URL}/{transcript_id}", headers=HEADERS).json()
            if res['status'] == 'completed': 
                break
            elif res['status'] == 'error': 
                return jsonify({'error': f"Processing failed: {res.get('error')}"}), 500
            time.sleep(3)

        # 4. Elaborazione Risultati
        text = res.get('text', '')
        utterances = res.get('utterances', [])
        
        # 5. GENERAZIONE MANUALE RIASSUNTO E MAPPA (Fallback per Italiano)
        summary = ""
        concepts = []
        
        if text:
            # Creazione Riassunto: prendiamo le prime 3 frasi del testo
            sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 5]
            if len(sentences) > 0:
                summary = ". ".join(sentences[:3])
                if len(sentences) > 3: 
                    summary += "..."
            
            # Creazione Mappa Concettuale: estraiamo frasi chiave medie
            concepts = [s.strip() for s in text.split('.') if 15 < len(s.strip()) < 80][:5]

        # 6. Risposta finale verso l'App
        return jsonify({
            'id': res['id'],
            'text': text,
            'utterances': utterances,
            'summary': summary or "Audio troppo breve per un riassunto.",
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
    # Porta richiesta da Render (default 10000)
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
