# AudioCi

Web-based audio announcement system with soundboard UI, real-time sync, and multi-user support.

## Descrizione

AudioCi e un sistema web per la gestione e il broadcast di annunci audio e musica a bordo di navi. Progettato per essere semplice e intuitivo, permette agli operatori di riprodurre messaggi preregistrati e musica di sottofondo attraverso un'interfaccia a soundboard.

## Funzionalita

- **Soundboard UI** - Interfaccia a pulsanti per riproduzione rapida di annunci preregistrati
- **Gestione Playlist** - Organizzazione e riproduzione di musica di sottofondo
- **Sincronizzazione Real-time** - Stato di riproduzione sincronizzato tra tutti i client connessi
- **Multi-utente** - Supporto per piu operatori simultanei con gestione conflitti
- **Upload Audio** - Caricamento di nuovi file audio direttamente dall'interfaccia web
- **Responsive Design** - Utilizzabile da PC, tablet e smartphone

## Tecnologie

- **Frontend**: HTML5, CSS3, JavaScript
- **Audio**: Web Audio API
- **Real-time**: WebSocket per sincronizzazione
- **Backend**: (opzionale) Server per gestione file e sync

## Installazione

```bash
# Clona il repository
git clone https://github.com/furnaropolo/AudioCi.git
cd AudioCi

# Apri index.html nel browser oppure servi con un web server
python3 -m http.server 8080
```

L'applicazione sara disponibile su `http://localhost:8080`

## Utilizzo

1. Apri l'applicazione nel browser
2. Carica i file audio nella sezione dedicata
3. Organizza i pulsanti della soundboard
4. Clicca sui pulsanti per riprodurre gli annunci
5. Usa i controlli playlist per la musica di sottofondo

## Use Case

Sviluppato per l'utilizzo su navi Ro-Pax per:
- Annunci di sicurezza
- Comunicazioni ai passeggeri
- Musica di sottofondo nelle aree comuni
- Avvisi di imbarco/sbarco

## Licenza

Questo progetto e rilasciato con licenza MIT.

## Autore

**Francesco Politano**
- GitHub: [@furnaropolo](https://github.com/furnaropolo)
- LinkedIn: [francesco-politano-b9161920](https://linkedin.com/in/francesco-politano-b9161920)
