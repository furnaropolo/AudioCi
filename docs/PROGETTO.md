# AudioCi - Sistema Annunci Nave

## Stato Progetto
**Fase attuale**: MVP + Ruolo MASTER implementato
**Ultimo aggiornamento**: 2025-11-28

---

## Accesso
- **URL**: https://192.168.1.42:8000 (HTTPS richiesto per microfono)
- **Credenziali default**: admin / admin
- **Nota**: Il certificato e' self-signed, accettare l'avviso del browser

---

## Cosa funziona (MVP + MASTER completato)

### Funzionalita' Base
- [x] Login con autenticazione JWT
- [x] Selezione modalita' PLAYER / CONTROLLER / MASTER
- [x] Tasto "Cambia Modalita'" per tornare alla selezione
- [x] Comunicazione WebSocket tra Player e Controller
- [x] Creazione gruppi (con popup modale)
- [x] Creazione annunci (con popup modale)
- [x] Upload file MP3 (con popup modale)
- [x] Riproduzione annunci sul Player
- [x] Barra di progresso con tempo corrente/rimanente
- [x] Click sulla barra per seek audio
- [x] Gestione utenti (admin/operatore/master)
- [x] Tasti adattivi (griglia 2x2, 3x3, 4x4 in base al numero)

### Ruolo MASTER (Annunci Emergenza Live)
- [x] Nuovo ruolo utente: MASTER (Comandante/Ufficiali)
- [x] Interfaccia dedicata: solo icona microfono grande rossa
- [x] Annuncio live via WebSocket + MediaRecorder
- [x] PRIORITA' ASSOLUTA: blocca tutto (annunci, musica, altri controller)
- [x] Indicatore visivo su tutti i device: "ANNUNCIO EMERGENZA IN CORSO"
- [x] Nessun altro puo' interrompere finche' il Master non rilascia
- [x] HTTPS abilitato con certificato self-signed (validita' 10 anni)

#### Flusso Annuncio Master:
1. Master si logga e seleziona modalita' MASTER
2. Vede SOLO icona microfono rossa grande
3. Tiene premuto per parlare (push-to-talk)
4. Tutti i Player ricevono audio in tempo reale
5. Tutti i Controller vedono overlay rosso "ANNUNCIO EMERGENZA IN CORSO"
6. Rilascia → torna alla normalita'

---

## Da implementare (prossime fasi)

### Fase 2 - Funzionalita' Core
- [ ] Sequenze annunci (piu' file in sequenza)
- [ ] Playlist musicale
- [ ] Priorita' audio (annunci interrompono musica)

### Fase 3 - Miglioramenti UI
- [ ] Tuning grafico interfaccia
- [ ] Icone personalizzate per tasti
- [ ] Drag & drop per riordinare tasti

### Fase 4 - Funzionalita' Avanzate
- [ ] Gestione rotte (annunci diversi per rotta)
- [ ] Backup/restore configurazione
- [ ] Log degli annunci Master per sicurezza

---

## Architettura

```
VM Ubuntu (Proxmox)                       PC Reception
┌─────────────────────┐                   ┌─────────────────────┐
│  AudioCi         │                   │  Browser sempre     │
│  Web Server         │◀── comandi ──────│  aperto (PLAYER)    │
│  + tutti gli MP3    │                   │                     │
│                     │─── audio ────────▶│  Riproduce audio    │──▶ Impianto nave
│                     │   (streaming)     │                     │
└─────────────────────┘                   └─────────────────────┘
        ▲
        │ comandi (play, stop, ecc.)
        │
┌───────┴───────┐
│ Altri device  │  (tablet, smartphone, PC ufficiali)
│ CONTROLLER    │
└───────────────┘
```

---

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Backend | Python + FastAPI |
| Frontend | HTML/CSS/JS puro |
| Realtime | WebSocket |
| Database | SQLite |
| Audio | Web Audio API |
| OS | Ubuntu 24.04 |

---

## Struttura File Server

```
/home/ies/audioci/
├── backend/
│   ├── main.py              # API FastAPI
│   └── venv/                # Virtual environment Python
├── frontend/
│   └── index.html           # Interfaccia web
├── audio/
│   ├── announcements/       # File MP3 annunci
│   └── music/               # File MP3 musica
├── certs/
│   ├── audioci.crt       # Certificato SSL self-signed
│   └── audioci.key       # Chiave privata SSL
├── docs/
│   └── PROGETTO.md          # Documentazione
└── audioci.db            # Database SQLite
```

---

## Servizio Systemd

```bash
# Stato
sudo systemctl status audioci

# Riavvio
sudo systemctl restart audioci

# Log
sudo journalctl -u audioci -f
```

---

## Ruoli Utente

| Ruolo | Permessi |
|-------|----------|
| **admin** | Tutto: gestione gruppi, annunci, utenti, upload MP3 |
| **operator** | Solo riproduzione annunci (modalita' Player o Controller) |
| **master** | Solo annuncio live emergenza con priorita' assoluta |

---

## Note per sviluppo futuro

1. Frontend attualmente in HTML/JS puro, possibile migrazione a Vue.js
2. Considerare nginx come reverse proxy per produzione
3. Implementare logging annunci Master per audit sicurezza

---

## Changelog

### 2025-11-28 (pomeriggio)
- Implementato ruolo MASTER per annunci emergenza live
- Interfaccia MASTER con pulsante microfono grande (push-to-talk)
- Sistema priorita' assoluta (blocca tutti i controller durante annuncio Master)
- Overlay rosso "ANNUNCIO EMERGENZA IN CORSO" su tutti i device
- Abilitato HTTPS con certificato SSL self-signed (validita' 10 anni)
- Streaming audio via WebSocket + MediaRecorder

### 2025-11-28 (mattina)
- Progetto inizializzato
- MVP completato con tutte le funzionalita' base
- Sistema PLAYER/CONTROLLER funzionante
- Popup modali per creazione gruppi/annunci/utenti
- Barra progresso audio con seek
