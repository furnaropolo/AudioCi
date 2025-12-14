# AudioCi

Sistema web-based per la gestione degli annunci audio in qualsiasi ambiente (hotel, negozi, uffici, navi, ecc.).

## Cosa fa

- **Soundboard a tasti** per riprodurre annunci audio
- **Architettura Player/Controller** - il Player riproduce, i Controller comandano
- **Gestione gruppi e annunci** con interfaccia intuitiva
- **Upload MP3** direttamente dal browser
- **Multi-utente** con ruoli Admin e Operatore
- **Comunicazione real-time** via WebSocket

## Architettura

```
VM Ubuntu (Proxmox)                       PC Reception
+---------------------+                   +---------------------+
|  AudioCi         |                   |  Browser sempre     |
|  Web Server         |<-- comandi -------|  aperto (PLAYER)    |
|  + tutti gli MP3    |                   |                     |
|                     |--- audio -------->|  Riproduce audio    |--> Impianto audio
+---------------------+                   +---------------------+
        ^
        | comandi (play, stop, ecc.)
        |
+-------+-------+
| Altri device  |  (tablet, smartphone, PC ufficiali)
| CONTROLLER    |
+---------------+
```

## Requisiti

- Ubuntu Server 24.04
- Python 3.12+
- 2 vCPU, 2-4 GB RAM
- Storage per file MP3

## Installazione

### 1. Clona il repository

```bash
cd /home/ies
git clone https://github.com/youruser/audioci.git audioci
cd audioci
```

### 2. Installa dipendenze sistema

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

### 3. Crea virtual environment e installa dipendenze Python

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn python-multipart aiosqlite python-jose passlib bcrypt==4.0.1 websockets
```

### 4. Crea le directory per gli audio

```bash
mkdir -p /home/ies/audioci/audio/{announcements,music}
```

### 5. Configura il servizio systemd

```bash
sudo tee /etc/systemd/system/audioci.service << 'EOF'
[Unit]
Description=AudioCi Backend
After=network.target

[Service]
Type=simple
User=ies
WorkingDirectory=/home/ies/audioci/backend
ExecStart=/home/ies/audioci/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable audioci
sudo systemctl start audioci
```

### 6. Verifica

```bash
sudo systemctl status audioci
curl http://localhost:8000/api/status
```

## Utilizzo

### Accesso

Apri nel browser: `http://IP_SERVER:8000`

**Credenziali default:**
- Username: `admin`
- Password: `admin`

### Modalita'

1. **PLAYER** - Da usare sul PC Reception collegato all'impianto audio
   - Tieni il browser sempre aperto
   - Riceve i comandi e riproduce l'audio

2. **CONTROLLER** - Da usare su tablet, smartphone o altri PC
   - Invia comandi al Player
   - Naviga tra gruppi e annunci

### Pannello Admin

Solo gli utenti admin possono:
- Creare/eliminare gruppi
- Creare/eliminare annunci
- Caricare file MP3
- Gestire utenti

## Struttura Progetto

```
audioci/
├── backend/
│   ├── main.py              # API FastAPI + WebSocket
│   └── venv/                # Virtual environment
├── frontend/
│   └── index.html           # Interfaccia web
├── audio/
│   ├── announcements/       # File MP3 annunci
│   └── music/               # File MP3 musica (futuro)
├── docs/
│   └── PROGETTO.md          # Documentazione dettagliata
└── audioci.db            # Database SQLite (creato automaticamente)
```

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Backend | Python + FastAPI |
| Frontend | HTML/CSS/JS |
| Realtime | WebSocket |
| Database | SQLite |
| Audio | Web Audio API |

## Porte

| Porta | Servizio |
|-------|----------|
| 8000 | HTTP (Web UI + API) |

## Comandi utili

```bash
# Stato servizio
sudo systemctl status audioci

# Riavvio
sudo systemctl restart audioci

# Log
sudo journalctl -u audioci -f

# Log ultimi errori
sudo journalctl -u audioci --no-pager -n 50
```

## Roadmap

- [x] MVP con soundboard base
- [x] Sistema Player/Controller
- [x] Upload MP3
- [x] Barra progresso audio
- [ ] Sequenze annunci (multi-file)
- [ ] Playlist musicale
- [ ] Annunci live da smartphone (WebRTC)
- [ ] Gestione rotte

## Licenza

MIT License

---

*Open Source Project*
