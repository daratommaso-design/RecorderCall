        # ... (dopo il ciclo while del polling) ...

        # 4. Elaborazione Risultati
        text = res.get('text', '')
        summary = res.get('summary', '')
        utterances = res.get('utterances', [])
        
        # LOGICA DI FALLBACK PER IL RIASSUNTO (Se l'AI non lo genera)
        if not summary or len(summary) < 10:
            sentences = [s.strip() for s in text.split('. ') if len(s) > 15]
            if len(sentences) > 3:
                # Crea un mini-riassunto con le prime 2-3 frasi
                summary = ". ".join(sentences[:3]) + "..."
            else:
                summary = text

        # GENERAZIONE MAPPA CONCETTUALE (Estrae concetti chiave dal testo)
        concepts = []
        if text:
            # Dividiamo il testo in frasi e prendiamo quelle più significative (lunghezza media)
            raw_concepts = [s.strip() for s in text.split('. ') if 15 < len(s) < 100]
            # Prendiamo fino a 5 concetti unici
            concepts = list(dict.fromkeys(raw_concepts))[:5]

        return jsonify({
            'id': res['id'],
            'text': text,
            'utterances': utterances,
            'summary': summary,
            'concept_map': concepts
        }), 200
