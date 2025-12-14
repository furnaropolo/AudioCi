# AudioCi - Diagrammi di Architettura

## 1. Architettura Generale del Sistema

```mermaid
flowchart TB
    subgraph "Client Devices"
        PC[🖥️ PC Reception<br/>PLAYER Mode]
        PHONE[📱 Smartphone<br/>CONTROLLER Mode]
        MASTER[🎙️ Comandante<br/>MASTER Mode]
    end

    subgraph "AudioCi Server<br/>192.168.1.42:8000"
        subgraph "FastAPI Backend"
            API[REST API]
            WS[WebSocket Server]
            TTS[TTS Engine<br/>edge-tts]
            TRANS[Translator<br/>deep-translator]
        end

        subgraph "Storage"
            DB[(SQLite DB<br/>audioci.db)]
            ANN[📁 /audio/announcements]
            MUS[📁 /audio/music]
        end

        FE[Frontend<br/>Single Page App]
    end

    PC <-->|WSS| WS
    PHONE <-->|WSS| WS
    MASTER <-->|WSS + Audio Stream| WS

    PC -->|HTTPS| API
    PHONE -->|HTTPS| API
    MASTER -->|HTTPS| API

    API <--> DB
    API --> ANN
    API --> MUS
    TTS --> ANN
    TRANS --> TTS

    FE -->|Static Files| PC
    FE -->|Static Files| PHONE
    FE -->|Static Files| MASTER
```

## 2. Schema Database

```mermaid
erDiagram
    USERS {
        int id PK
        string username UK
        string password_hash
        string role "admin|operator|master"
    }

    GROUPS {
        int id PK
        string name
        string color
        string icon
        int position
    }

    ANNOUNCEMENTS {
        int id PK
        string name
        int group_id FK
        string color
        int position
    }

    ANNOUNCEMENT_FILES {
        int id PK
        int announcement_id FK
        string file_path
        int position
    }

    SEQUENCES {
        int id PK
        string name
        int group_id FK
        string color
        int position
    }

    SEQUENCE_ITEMS {
        int id PK
        int sequence_id FK
        int announcement_id FK
        int position
    }

    MUSIC {
        int id PK
        string title
        string artist
        string file_path
        int duration
    }

    PLAYLISTS {
        int id PK
        string name
    }

    PLAYLIST_ITEMS {
        int id PK
        int playlist_id FK
        int music_id FK
        int position
    }

    GROUPS ||--o{ ANNOUNCEMENTS : contains
    GROUPS ||--o{ SEQUENCES : contains
    ANNOUNCEMENTS ||--o{ ANNOUNCEMENT_FILES : has
    SEQUENCES ||--o{ SEQUENCE_ITEMS : contains
    SEQUENCE_ITEMS }o--|| ANNOUNCEMENTS : references
    PLAYLISTS ||--o{ PLAYLIST_ITEMS : contains
    PLAYLIST_ITEMS }o--|| MUSIC : references
```

## 3. Flusso Comunicazione WebSocket

```mermaid
sequenceDiagram
    participant C as Controller
    participant S as Server
    participant P as Player

    Note over C,P: Connessione WebSocket
    C->>S: Connect /ws/controller
    P->>S: Connect /ws/player
    S-->>C: Connection OK
    S-->>P: Connection OK

    Note over C,P: Riproduzione Annuncio
    C->>S: {action: "play_announcement", id: 1, files: ["file.mp3"]}
    S->>P: {type: "play", content: "announcement", files: ["file.mp3"]}
    P->>P: Play audio queue

    Note over C,P: Riproduzione Playlist Musicale
    C->>S: {action: "play_playlist", playlist_id: 1, tracks: [...], loop: true}
    S->>P: {type: "play_playlist", tracks: [...], loop: true}
    P->>P: Play music with loop

    Note over C,P: Controlli Musica
    C->>S: {action: "music_next"}
    S->>P: {type: "music_next"}
    P->>P: Next track

    Note over C,P: Stop
    C->>S: {action: "stop"}
    S->>P: {type: "stop"}
    P->>P: Stop all audio
```

## 4. Flusso Annuncio Master (Emergenza)

```mermaid
sequenceDiagram
    participant M as Master
    participant S as Server
    participant C as Controller
    participant P as Player

    Note over M,P: Master inizia trasmissione
    M->>S: {action: "start_announcement", username: "Comandante"}
    S->>C: {type: "master_start", username: "Comandante"}
    S->>P: {type: "master_start", username: "Comandante"}
    P->>P: Stop audio, show overlay

    Note over M,P: Streaming audio live
    loop Audio chunks
        M->>S: Binary audio data (WebM/Opus)
        S->>P: Binary audio data
        P->>P: Play audio in real-time
    end

    Note over M,P: Master termina
    M->>S: {action: "stop_announcement"}
    S->>C: {type: "master_stop"}
    S->>P: {type: "master_stop"}
    P->>P: Hide overlay, resume normal
```

## 5. API REST Endpoints

```mermaid
flowchart LR
    subgraph "Auth"
        A1[POST /api/auth/login]
        A2[GET /api/auth/me]
    end

    subgraph "Users"
        U1[GET /api/users]
        U2[POST /api/users]
        U3[DELETE /api/users/:id]
    end

    subgraph "Groups"
        G1[GET /api/groups]
        G2[POST /api/groups]
        G3[PUT /api/groups/:id]
        G4[DELETE /api/groups/:id]
    end

    subgraph "Announcements"
        AN1[GET /api/announcements]
        AN2[POST /api/announcements]
        AN3[POST /api/announcements/bulk-upload]
        AN4[PUT /api/announcements/move]
        AN5[DELETE /api/announcements/:id]
        AN6[POST /api/announcements/:id/files]
    end

    subgraph "Sequences"
        S1[GET /api/sequences]
        S2[POST /api/sequences]
        S3[PUT /api/sequences/:id]
        S4[DELETE /api/sequences/:id]
    end

    subgraph "TTS"
        T1[GET /api/tts/languages]
        T2[POST /api/tts/generate]
    end

    subgraph "Music"
        M1[GET /api/music]
        M2[POST /api/music]
        M3[POST /api/music/bulk-upload]
        M4[PUT /api/music/:id]
        M5[DELETE /api/music/:id]
    end

    subgraph "Playlists"
        P1[GET /api/playlists]
        P2[POST /api/playlists]
        P3[PUT /api/playlists/:id]
        P4[DELETE /api/playlists/:id]
        P5[POST /api/playlists/:id/tracks/:music_id]
        P6[DELETE /api/playlists/:id/tracks/:music_id]
    end

    subgraph "Audio Files"
        AF1[GET /audio/announcements/:file]
        AF2[GET /audio/music/:file]
    end

    subgraph "WebSocket"
        WS1[WS /ws/player]
        WS2[WS /ws/controller]
        WS3[WS /ws/master]
    end
```

## 6. Ruoli Utente e Permessi

```mermaid
flowchart TB
    subgraph "Ruoli"
        ADMIN[👑 Admin]
        OPERATOR[👤 Operator]
        MASTERR[🎙️ Master]
    end

    subgraph "Permessi Admin"
        PA1[Gestione Utenti]
        PA2[Gestione Gruppi]
        PA3[Gestione Annunci]
        PA4[Upload Audio]
        PA5[Generazione TTS]
        PA6[Gestione Sequenze]
        PA7[Gestione Musica]
        PA8[Gestione Playlist]
        PA9[Player/Controller]
    end

    subgraph "Permessi Operator"
        PO1[Visualizza Gruppi]
        PO2[Visualizza Annunci]
        PO3[Riproduzione Audio]
        PO4[Player Mode]
        PO5[Controller Mode]
    end

    subgraph "Permessi Master"
        PM1[Tutto Operator]
        PM2[Master Mode]
        PM3[Annunci Emergenza Live]
        PM4[Override su tutti i Player]
    end

    ADMIN --> PA1 & PA2 & PA3 & PA4 & PA5 & PA6 & PA7 & PA8 & PA9
    OPERATOR --> PO1 & PO2 & PO3 & PO4 & PO5
    MASTERR --> PM1 & PM2 & PM3 & PM4
```

## 7. Flusso Generazione TTS Multi-lingua

```mermaid
flowchart TB
    START[Utente inserisce<br/>testo in Italiano] --> INPUT[Testo + Lingue selezionate<br/>+ Voce M/F]

    INPUT --> LOOP{Per ogni lingua}

    LOOP -->|Italiano| IT[Testo originale]
    LOOP -->|Altre lingue| TRANS[deep-translator<br/>Traduzione automatica]

    IT --> TTS1[edge-tts<br/>Genera MP3 IT]
    TRANS --> TTS2[edge-tts<br/>Genera MP3 tradotto]

    TTS1 --> SAVE[Salva file in<br/>/audio/announcements]
    TTS2 --> SAVE

    SAVE --> CREATE[Crea Annuncio<br/>per ogni lingua]
    CREATE --> SEQ{Crea Sequenza?}

    SEQ -->|Sì| SEQC[Crea Sequenza<br/>con tutti gli annunci]
    SEQ -->|No| DONE[Fine]
    SEQC --> DONE

    subgraph "Lingue Supportate"
        L1[🇮🇹 Italiano]
        L2[🇬🇧 English]
        L3[🇫🇷 Français]
        L4[🇩🇪 Deutsch]
        L5[🇪🇸 Español]
        L6[🇬🇷 Ελληνικά]
    end
```

## 8. Struttura Frontend - Navigazione

```mermaid
flowchart TB
    subgraph "Login"
        LOGIN[🔐 Login Screen]
    end

    subgraph "Mode Selection"
        MODE[Selezione Modalità]
        PLAYER_M[🔊 PLAYER]
        CTRL_M[🎛️ CONTROLLER]
        MASTER_M[🎙️ MASTER]
    end

    subgraph "App Screen"
        TABS[Tab Navigation]
        TAB1[📢 Soundboard]
        TAB2[🎵 Musica]
        TAB3[⚙️ Admin]
    end

    subgraph "Soundboard Tab"
        GROUPS[Lista Gruppi]
        ANNS[Lista Annunci/Sequenze]
        PLAY[Riproduzione]
    end

    subgraph "Music Tab"
        MINIP[Mini Player]
        PLAYLIST[Playlist Cards]
        LIBRARY[Libreria Musicale]
    end

    subgraph "Admin Tab"
        UPLOAD[Upload Annunci]
        TTS[Generatore TTS]
        GMAN[Gestione Gruppi]
        AMAN[Gestione Annunci]
        SEQMAN[Gestione Sequenze]
        UMAN[Gestione Utenti]
    end

    subgraph "Master Screen"
        MICBTN[🎙️ Push-to-Talk]
        BROADCAST[Live Broadcast]
    end

    LOGIN --> MODE
    MODE --> PLAYER_M & CTRL_M & MASTER_M
    PLAYER_M & CTRL_M --> TABS
    MASTER_M --> MICBTN --> BROADCAST

    TABS --> TAB1 & TAB2 & TAB3
    TAB1 --> GROUPS --> ANNS --> PLAY
    TAB2 --> MINIP & PLAYLIST & LIBRARY
    TAB3 --> UPLOAD & TTS & GMAN & AMAN & SEQMAN & UMAN
```

## 9. Player Audio - Gestione Code

```mermaid
flowchart TB
    subgraph "Input"
        ANN[Annuncio Singolo]
        SEQ[Sequenza Multi-file]
        MUSIC[Playlist Musicale]
        MASTER[Master Audio Stream]
    end

    subgraph "Audio Queues"
        AQ[Announcement Queue<br/>audioQueue[]]
        MQ[Music Queue<br/>currentPlaylistTracks[]]
    end

    subgraph "Players"
        AP[audioPlayer<br/>Annunci]
        MP[musicPlayer<br/>Musica]
        MAC[masterAudioContext<br/>Emergenza Live]
    end

    subgraph "Controls"
        STOP[⏹️ Stop]
        PREV[⏮️ Prev]
        NEXT[⏭️ Next]
        SHUFFLE[🔀 Shuffle]
        REPEAT[🔂 Repeat Track]
        LOOP[🔁 Loop Playlist]
    end

    ANN --> AQ --> AP
    SEQ --> AQ
    MUSIC --> MQ --> MP
    MASTER --> MAC

    AP -->|onended| AQ
    MP -->|onended| MQ

    STOP --> AP & MP
    PREV & NEXT --> MQ
    SHUFFLE & REPEAT & LOOP --> MQ
```

## 10. Deploy e Servizi

```mermaid
flowchart TB
    subgraph "Server 192.168.1.42"
        subgraph "Systemd Service"
            SVC[audioci.service]
        end

        subgraph "Python Environment"
            VENV[venv]
            UV[uvicorn]
            FA[FastAPI App]
        end

        subgraph "HTTPS/WSS"
            CERT[SSL Certificates<br/>audioci.crt/key]
            PORT[Port 8000]
        end

        subgraph "File System"
            BASE[/home/ies/audioci]
            BE[/backend]
            FEF[/frontend]
            AUDIO[/audio]
            CERTS[/certs]
        end
    end

    SVC --> UV --> FA
    FA --> CERT --> PORT
    FA --> BASE
    BASE --> BE & FEF & AUDIO & CERTS

    subgraph "Comandi"
        C1[sudo systemctl start audioci]
        C2[sudo systemctl stop audioci]
        C3[sudo systemctl restart audioci]
        C4[sudo systemctl status audioci]
    end
```

---

## Note per Lucidchart

Per importare questi diagrammi in Lucidchart:

1. Vai su **Lucidchart** → **File** → **Import**
2. Seleziona **Mermaid** come formato
3. Copia e incolla il codice Mermaid di ogni diagramma
4. Personalizza colori e stili secondo le tue preferenze

In alternativa, puoi usare:
- **draw.io** (diagrams.net) che supporta Mermaid
- **Mermaid Live Editor** (mermaid.live) per preview e export PNG/SVG
