"""
AudioCi - Backend API
Sistema annunci nave via web
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import aiosqlite
import os
import json
import asyncio
import re
import tempfile
from pathlib import Path
import edge_tts
from deep_translator import GoogleTranslator

def sanitize_filename(filename):
    """Remove or replace characters that are problematic in filenames"""
    # Get just the filename without path
    filename = os.path.basename(filename)
    # Replace problematic characters with underscore
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove any path traversal attempts
    filename = filename.replace('..', '_')
    return filename

# Configurazione
BASE_DIR = Path("/home/ies/audioci")
AUDIO_DIR = BASE_DIR / "audio"
ANNOUNCEMENTS_DIR = AUDIO_DIR / "announcements"
MUSIC_DIR = AUDIO_DIR / "music"
DB_PATH = BASE_DIR / "audioci.db"

SECRET_KEY = "audioci-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 ore

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

app = FastAPI(title="AudioCi", version="1.0.0")

# CORS per sviluppo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections manager
class ConnectionManager:
    def __init__(self):
        self.players: List[WebSocket] = []
        self.controllers: List[WebSocket] = []
        self.masters: List[WebSocket] = []
        self.master_active = False
        self.master_username = None

    async def connect_player(self, websocket: WebSocket):
        await websocket.accept()
        self.players.append(websocket)
        if self.master_active:
            await websocket.send_json({"type": "master_start", "username": self.master_username})

    async def connect_controller(self, websocket: WebSocket):
        await websocket.accept()
        self.controllers.append(websocket)
        if self.master_active:
            await websocket.send_json({"type": "master_start", "username": self.master_username})

    async def connect_master(self, websocket: WebSocket):
        await websocket.accept()
        self.masters.append(websocket)

    def disconnect_player(self, websocket: WebSocket):
        if websocket in self.players:
            self.players.remove(websocket)

    def disconnect_controller(self, websocket: WebSocket):
        if websocket in self.controllers:
            self.controllers.remove(websocket)

    def disconnect_master(self, websocket: WebSocket):
        if websocket in self.masters:
            self.masters.remove(websocket)

    async def send_to_players(self, message: dict):
        for player in self.players:
            try:
                await player.send_json(message)
            except:
                pass

    async def send_to_controllers(self, message: dict):
        for controller in self.controllers:
            try:
                await controller.send_json(message)
            except:
                pass

    async def send_to_all(self, message: dict):
        for ws in self.players + self.controllers + self.masters:
            try:
                await ws.send_json(message)
            except:
                pass

    async def start_master_announcement(self, username: str):
        self.master_active = True
        self.master_username = username
        await self.send_to_all({"type": "master_start", "username": username})

    async def stop_master_announcement(self):
        self.master_active = False
        self.master_username = None
        await self.send_to_all({"type": "master_stop"})

    async def send_audio_to_players(self, audio_data: bytes):
        for player in self.players:
            try:
                await player.send_bytes(audio_data)
            except:
                pass

manager = ConnectionManager()

# Modelli Pydantic
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "operator"

class UserResponse(BaseModel):
    id: int
    username: str
    role: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str

class GroupCreate(BaseModel):
    name: str
    color: str = "#3B82F6"
    icon: Optional[str] = None

class GroupResponse(BaseModel):
    id: int
    name: str
    color: str
    icon: Optional[str]
    position: int

class AnnouncementCreate(BaseModel):
    name: str
    group_id: int
    color: str = "#10B981"

class AnnouncementResponse(BaseModel):
    id: int
    name: str
    group_id: int
    color: str
    position: int
    files: List[str] = []

class BulkUploadResponse(BaseModel):
    created: int
    announcements: List[AnnouncementResponse]

class PlayCommand(BaseModel):
    type: str
    id: int
    action: str = "play"

class SequenceCreate(BaseModel):
    name: str
    group_id: int
    color: str = "#8B5CF6"
    announcement_ids: List[int] = []

class SequenceUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    announcement_ids: Optional[List[int]] = None

class SequenceResponse(BaseModel):
    id: int
    name: str
    group_id: int
    color: str
    position: int
    announcements: List[AnnouncementResponse] = []

# Music/Playlist Models
class MusicCreate(BaseModel):
    title: str
    artist: Optional[str] = None

class MusicResponse(BaseModel):
    id: int
    title: str
    artist: Optional[str]
    file_path: str
    duration: Optional[int]

class PlaylistCreate(BaseModel):
    name: str

class PlaylistUpdate(BaseModel):
    name: Optional[str] = None
    track_ids: Optional[List[int]] = None

class PlaylistResponse(BaseModel):
    id: int
    name: str
    tracks: List[MusicResponse] = []

# TTS Configuration
TTS_VOICES = {
    "it": {"male": "it-IT-DiegoNeural", "female": "it-IT-ElsaNeural"},
    "en": {"male": "en-GB-RyanNeural", "female": "en-GB-SoniaNeural"},
    "fr": {"male": "fr-FR-HenriNeural", "female": "fr-FR-DeniseNeural"},
    "de": {"male": "de-DE-ConradNeural", "female": "de-DE-KatjaNeural"},
    "es": {"male": "es-ES-AlvaroNeural", "female": "es-ES-ElviraNeural"},
    "el": {"male": "el-GR-NestorasNeural", "female": "el-GR-AthinaNeural"},
}

TTS_LANG_NAMES = {
    "it": "Italiano",
    "en": "English",
    "fr": "Français",
    "de": "Deutsch",
    "es": "Español",
    "el": "Ελληνικά",
}

class TTSRequest(BaseModel):
    text: str
    languages: List[str]  # ["it", "en", "fr"]
    voice_gender: str = "female"  # "male" or "female"
    group_id: int
    announcement_name: str
    create_sequence: bool = True

class TTSResponse(BaseModel):
    success: bool
    announcements: List[AnnouncementResponse] = []
    sequence_id: Optional[int] = None
    message: str = ""

# Database functions
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'operator',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                color TEXT DEFAULT '#3B82F6',
                icon TEXT,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                color TEXT DEFAULT '#10B981',
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS announcement_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                announcement_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                file_order INTEGER DEFAULT 0,
                FOREIGN KEY (announcement_id) REFERENCES announcements(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS music (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT,
                file_path TEXT NOT NULL,
                duration INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS playlist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                music_id INTEGER NOT NULL,
                position INTEGER DEFAULT 0,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY (music_id) REFERENCES music(id) ON DELETE CASCADE
            )
        """)

        # Tabella per le sequenze (sottogruppi di annunci da riprodurre in serie)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sequences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                color TEXT DEFAULT '#8B5CF6',
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS sequence_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sequence_id INTEGER NOT NULL,
                announcement_id INTEGER NOT NULL,
                position INTEGER DEFAULT 0,
                FOREIGN KEY (sequence_id) REFERENCES sequences(id) ON DELETE CASCADE,
                FOREIGN KEY (announcement_id) REFERENCES announcements(id) ON DELETE CASCADE
            )
        """)

        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        count = await cursor.fetchone()
        if count[0] == 0:
            password_hash = pwd_context.hash("admin")
            await db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", password_hash, "admin")
            )

        await db.commit()

# Auth functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token non valido",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = await cursor.fetchone()
        if user is None:
            raise credentials_exception
        return dict(user)

async def get_admin_user(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Accesso riservato agli admin")
    return current_user

# API Routes

@app.on_event("startup")
async def startup():
    ANNOUNCEMENTS_DIR.mkdir(parents=True, exist_ok=True)
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    await init_db()

# Auth
@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE username = ?", (form_data.username,)
        )
        user = await cursor.fetchone()

    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenziali non valide")

    access_token = create_access_token(data={"sub": user["username"]})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user["role"],
        "username": user["username"]
    }

@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(id=current_user["id"], username=current_user["username"], role=current_user["role"])

# Users (admin only)
@app.get("/api/users", response_model=List[UserResponse])
async def get_users(admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, username, role FROM users")
        users = await cursor.fetchall()
        return [UserResponse(**dict(u)) for u in users]

@app.post("/api/users", response_model=UserResponse)
async def create_user(user: UserCreate, admin: dict = Depends(get_admin_user)):
    password_hash = pwd_context.hash(user.password)
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            cursor = await db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (user.username, password_hash, user.role)
            )
            await db.commit()
            return UserResponse(id=cursor.lastrowid, username=user.username, role=user.role)
        except aiosqlite.IntegrityError:
            raise HTTPException(status_code=400, detail="Username gia' esistente")

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE id = ? AND username != 'admin'", (user_id,))
        await db.commit()
    return {"status": "ok"}

# Groups
@app.get("/api/groups", response_model=List[GroupResponse])
async def get_groups(current_user: dict = Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM groups ORDER BY position")
        groups = await cursor.fetchall()
        return [GroupResponse(**dict(g)) for g in groups]

@app.post("/api/groups", response_model=GroupResponse)
async def create_group(group: GroupCreate, admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM groups")
        position = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "INSERT INTO groups (name, color, icon, position) VALUES (?, ?, ?, ?)",
            (group.name, group.color, group.icon, position)
        )
        await db.commit()
        return GroupResponse(id=cursor.lastrowid, name=group.name, color=group.color, icon=group.icon, position=position)

@app.put("/api/groups/{group_id}", response_model=GroupResponse)
async def update_group(group_id: int, group: GroupCreate, admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE groups SET name = ?, color = ?, icon = ? WHERE id = ?",
            (group.name, group.color, group.icon, group_id)
        )
        await db.commit()
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
        g = await cursor.fetchone()
        return GroupResponse(**dict(g))

@app.delete("/api/groups/{group_id}")
async def delete_group(group_id: int, admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        await db.commit()
    return {"status": "ok"}

# Announcements
@app.get("/api/announcements", response_model=List[AnnouncementResponse])
async def get_announcements(group_id: Optional[int] = None, current_user: dict = Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if group_id:
            cursor = await db.execute(
                "SELECT * FROM announcements WHERE group_id = ? ORDER BY position", (group_id,)
            )
        else:
            cursor = await db.execute("SELECT * FROM announcements ORDER BY position")
        announcements = await cursor.fetchall()

        result = []
        for a in announcements:
            cursor = await db.execute(
                "SELECT file_path FROM announcement_files WHERE announcement_id = ? ORDER BY file_order",
                (a["id"],)
            )
            files = [f["file_path"] for f in await cursor.fetchall()]
            result.append(AnnouncementResponse(
                id=a["id"], name=a["name"], group_id=a["group_id"],
                color=a["color"], position=a["position"], files=files
            ))
        return result

@app.post("/api/announcements", response_model=AnnouncementResponse)
async def create_announcement(announcement: AnnouncementCreate, admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM announcements WHERE group_id = ?",
            (announcement.group_id,)
        )
        position = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "INSERT INTO announcements (name, group_id, color, position) VALUES (?, ?, ?, ?)",
            (announcement.name, announcement.group_id, announcement.color, position)
        )
        await db.commit()
        return AnnouncementResponse(
            id=cursor.lastrowid, name=announcement.name, group_id=announcement.group_id,
            color=announcement.color, position=position, files=[]
        )

# Bulk upload - carica file multipli e crea annunci automaticamente
@app.post("/api/announcements/bulk-upload")
async def bulk_upload_announcements(
    group_id: int = Form(...),
    files: List[UploadFile] = File(...),
    admin: dict = Depends(get_admin_user)
):
    """
    Carica multipli file audio e crea automaticamente un annuncio per ognuno.
    Il nome dell'annuncio viene preso dal nome del file (senza estensione).
    """
    created_announcements = []
    
    async with aiosqlite.connect(DB_PATH) as db:
        for file in files:
            # Estrai nome senza estensione e sanitizza
            original_filename = sanitize_filename(file.filename)
            name_without_ext = Path(original_filename).stem
            
            # Crea annuncio
            cursor = await db.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM announcements WHERE group_id = ?",
                (group_id,)
            )
            position = (await cursor.fetchone())[0]
            
            cursor = await db.execute(
                "INSERT INTO announcements (name, group_id, color, position) VALUES (?, ?, ?, ?)",
                (name_without_ext, group_id, "#10B981", position)
            )
            announcement_id = cursor.lastrowid
            
            # Salva file
            safe_filename = f"{announcement_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{original_filename}"
            filepath = ANNOUNCEMENTS_DIR / safe_filename
            
            content = await file.read()
            with open(filepath, "wb") as f:
                f.write(content)
            
            # Registra file in DB
            await db.execute(
                "INSERT INTO announcement_files (announcement_id, file_path, file_order) VALUES (?, ?, ?)",
                (announcement_id, safe_filename, 1)
            )
            
            created_announcements.append(AnnouncementResponse(
                id=announcement_id,
                name=name_without_ext,
                group_id=group_id,
                color="#10B981",
                position=position,
                files=[safe_filename]
            ))
        
        await db.commit()
    
    return {"created": len(created_announcements), "announcements": created_announcements}

# Sposta annunci in un altro gruppo
@app.put("/api/announcements/move")
async def move_announcements(
    announcement_ids: List[int],
    target_group_id: int,
    admin: dict = Depends(get_admin_user)
):
    """Sposta uno o piu' annunci in un altro gruppo"""
    async with aiosqlite.connect(DB_PATH) as db:
        for ann_id in announcement_ids:
            await db.execute(
                "UPDATE announcements SET group_id = ? WHERE id = ?",
                (target_group_id, ann_id)
            )
        await db.commit()
    return {"status": "ok", "moved": len(announcement_ids)}

@app.delete("/api/announcements/{announcement_id}")
async def delete_announcement(announcement_id: int, admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT file_path FROM announcement_files WHERE announcement_id = ?", (announcement_id,)
        )
        files = await cursor.fetchall()
        for f in files:
            filepath = ANNOUNCEMENTS_DIR / f["file_path"]
            if filepath.exists():
                filepath.unlink()

        await db.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
        await db.commit()
    return {"status": "ok"}

# File upload
@app.post("/api/announcements/{announcement_id}/files")
async def upload_announcement_file(
    announcement_id: int,
    file: UploadFile = File(...),
    admin: dict = Depends(get_admin_user)
):
    safe_name = sanitize_filename(file.filename)
    filename = f"{announcement_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
    filepath = ANNOUNCEMENTS_DIR / filename

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(MAX(file_order), 0) + 1 FROM announcement_files WHERE announcement_id = ?",
            (announcement_id,)
        )
        order = (await cursor.fetchone())[0]
        await db.execute(
            "INSERT INTO announcement_files (announcement_id, file_path, file_order) VALUES (?, ?, ?)",
            (announcement_id, filename, order)
        )
        await db.commit()

    return {"filename": filename}

# Sequences API
@app.get("/api/sequences", response_model=List[SequenceResponse])
async def get_sequences(current_user: dict = Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM sequences ORDER BY group_id, position")
        sequences = await cursor.fetchall()

        result = []
        for seq in sequences:
            # Get announcements in this sequence
            cursor = await db.execute("""
                SELECT a.*, si.position as seq_position
                FROM announcements a
                JOIN sequence_items si ON a.id = si.announcement_id
                WHERE si.sequence_id = ?
                ORDER BY si.position
            """, (seq["id"],))
            ann_rows = await cursor.fetchall()

            announcements = []
            for ann in ann_rows:
                # Get files for each announcement
                cursor = await db.execute(
                    "SELECT file_path FROM announcement_files WHERE announcement_id = ? ORDER BY file_order",
                    (ann["id"],)
                )
                files = [row["file_path"] for row in await cursor.fetchall()]
                announcements.append(AnnouncementResponse(
                    id=ann["id"],
                    name=ann["name"],
                    group_id=ann["group_id"],
                    color=ann["color"],
                    position=ann["position"],
                    files=files
                ))

            result.append(SequenceResponse(
                id=seq["id"],
                name=seq["name"],
                group_id=seq["group_id"],
                color=seq["color"],
                position=seq["position"],
                announcements=announcements
            ))
        return result

@app.post("/api/sequences", response_model=SequenceResponse)
async def create_sequence(seq: SequenceCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo admin può creare sequenze")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT MAX(position) FROM sequences WHERE group_id = ?", (seq.group_id,))
        max_pos = await cursor.fetchone()
        position = (max_pos[0] or 0) + 1

        cursor = await db.execute(
            "INSERT INTO sequences (name, group_id, color, position) VALUES (?, ?, ?, ?)",
            (seq.name, seq.group_id, seq.color, position)
        )
        seq_id = cursor.lastrowid

        # Add announcements to sequence
        for i, ann_id in enumerate(seq.announcement_ids):
            await db.execute(
                "INSERT INTO sequence_items (sequence_id, announcement_id, position) VALUES (?, ?, ?)",
                (seq_id, ann_id, i)
            )

        await db.commit()

        # Return full sequence with announcements
        announcements = []
        for ann_id in seq.announcement_ids:
            cursor = await db.execute("SELECT * FROM announcements WHERE id = ?", (ann_id,))
            ann = await cursor.fetchone()
            if ann:
                cursor = await db.execute(
                    "SELECT file_path FROM announcement_files WHERE announcement_id = ? ORDER BY file_order",
                    (ann_id,)
                )
                files = [row["file_path"] for row in await cursor.fetchall()]
                announcements.append(AnnouncementResponse(
                    id=ann["id"],
                    name=ann["name"],
                    group_id=ann["group_id"],
                    color=ann["color"],
                    position=ann["position"],
                    files=files
                ))

        return SequenceResponse(
            id=seq_id,
            name=seq.name,
            group_id=seq.group_id,
            color=seq.color,
            position=position,
            announcements=announcements
        )

@app.put("/api/sequences/{sequence_id}", response_model=SequenceResponse)
async def update_sequence(sequence_id: int, seq: SequenceUpdate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo admin può modificare sequenze")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Update sequence fields
        if seq.name:
            await db.execute("UPDATE sequences SET name = ? WHERE id = ?", (seq.name, sequence_id))
        if seq.color:
            await db.execute("UPDATE sequences SET color = ? WHERE id = ?", (seq.color, sequence_id))

        # Update announcement list if provided
        if seq.announcement_ids is not None:
            await db.execute("DELETE FROM sequence_items WHERE sequence_id = ?", (sequence_id,))
            for i, ann_id in enumerate(seq.announcement_ids):
                await db.execute(
                    "INSERT INTO sequence_items (sequence_id, announcement_id, position) VALUES (?, ?, ?)",
                    (sequence_id, ann_id, i)
                )

        await db.commit()

        # Return updated sequence
        cursor = await db.execute("SELECT * FROM sequences WHERE id = ?", (sequence_id,))
        seq_row = await cursor.fetchone()

        cursor = await db.execute("""
            SELECT a.* FROM announcements a
            JOIN sequence_items si ON a.id = si.announcement_id
            WHERE si.sequence_id = ?
            ORDER BY si.position
        """, (sequence_id,))
        ann_rows = await cursor.fetchall()

        announcements = []
        for ann in ann_rows:
            cursor = await db.execute(
                "SELECT file_path FROM announcement_files WHERE announcement_id = ? ORDER BY file_order",
                (ann["id"],)
            )
            files = [row["file_path"] for row in await cursor.fetchall()]
            announcements.append(AnnouncementResponse(
                id=ann["id"],
                name=ann["name"],
                group_id=ann["group_id"],
                color=ann["color"],
                position=ann["position"],
                files=files
            ))

        return SequenceResponse(
            id=seq_row["id"],
            name=seq_row["name"],
            group_id=seq_row["group_id"],
            color=seq_row["color"],
            position=seq_row["position"],
            announcements=announcements
        )

@app.delete("/api/sequences/{sequence_id}")
async def delete_sequence(sequence_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo admin può eliminare sequenze")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sequence_items WHERE sequence_id = ?", (sequence_id,))
        await db.execute("DELETE FROM sequences WHERE id = ?", (sequence_id,))
        await db.commit()
    return {"status": "deleted"}

# TTS Generation API
@app.get("/api/tts/languages")
async def get_tts_languages(current_user: dict = Depends(get_current_user)):
    """Get available TTS languages"""
    return {
        "languages": [
            {"code": code, "name": name}
            for code, name in TTS_LANG_NAMES.items()
        ],
        "genders": ["male", "female"]
    }

@app.post("/api/tts/generate", response_model=TTSResponse)
async def generate_tts(request: TTSRequest, admin: dict = Depends(get_admin_user)):
    """Generate TTS announcements with translation"""
    try:
        created_announcements = []
        created_announcement_ids = []

        # Get original text (assumed to be in first language or Italian)
        original_text = request.text.strip()
        if not original_text:
            raise HTTPException(status_code=400, detail="Testo vuoto")

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            for lang in request.languages:
                if lang not in TTS_VOICES:
                    continue

                # Translate text if not Italian (source language)
                if lang == "it":
                    text_to_speak = original_text
                else:
                    try:
                        translator = GoogleTranslator(source='it', target=lang)
                        text_to_speak = translator.translate(original_text)
                    except Exception as e:
                        text_to_speak = original_text  # Fallback to original

                # Get voice based on gender
                voice = TTS_VOICES[lang][request.voice_gender]

                # Generate audio using edge-tts
                communicate = edge_tts.Communicate(text_to_speak, voice)

                # Create announcement in database
                cursor = await db.execute(
                    "SELECT COALESCE(MAX(position), 0) + 1 FROM announcements WHERE group_id = ?",
                    (request.group_id,)
                )
                position = (await cursor.fetchone())[0]

                ann_name = f"{request.announcement_name} ({TTS_LANG_NAMES[lang]})"
                cursor = await db.execute(
                    "INSERT INTO announcements (group_id, name, color, position) VALUES (?, ?, ?, ?)",
                    (request.group_id, ann_name, "#8B5CF6", position)
                )
                announcement_id = cursor.lastrowid

                # Save audio file
                filename = f"{announcement_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{lang}.mp3"
                filepath = ANNOUNCEMENTS_DIR / filename

                await communicate.save(str(filepath))

                # Add file to database
                await db.execute(
                    "INSERT INTO announcement_files (announcement_id, file_path, file_order) VALUES (?, ?, ?)",
                    (announcement_id, filename, 1)
                )

                await db.commit()

                created_announcement_ids.append(announcement_id)
                created_announcements.append(AnnouncementResponse(
                    id=announcement_id,
                    name=ann_name,
                    group_id=request.group_id,
                    color="#8B5CF6",
                    position=position,
                    files=[filename]
                ))

            # Create sequence if requested and more than one language
            sequence_id = None
            if request.create_sequence and len(created_announcement_ids) > 1:
                cursor = await db.execute(
                    "SELECT COALESCE(MAX(position), 0) + 1 FROM sequences WHERE group_id = ?",
                    (request.group_id,)
                )
                seq_position = (await cursor.fetchone())[0]

                seq_name = f"{request.announcement_name} ({len(created_announcement_ids)} lingue)"
                cursor = await db.execute(
                    "INSERT INTO sequences (group_id, name, color, position) VALUES (?, ?, ?, ?)",
                    (request.group_id, seq_name, "#8B5CF6", seq_position)
                )
                sequence_id = cursor.lastrowid

                for i, ann_id in enumerate(created_announcement_ids):
                    await db.execute(
                        "INSERT INTO sequence_items (sequence_id, announcement_id, position) VALUES (?, ?, ?)",
                        (sequence_id, ann_id, i)
                    )

                await db.commit()

        return TTSResponse(
            success=True,
            announcements=created_announcements,
            sequence_id=sequence_id,
            message=f"Creati {len(created_announcements)} annunci" +
                    (f" e 1 sequenza" if sequence_id else "")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore generazione TTS: {str(e)}")

# ============== MUSIC API ==============

# Get all music tracks
@app.get("/api/music", response_model=List[MusicResponse])
async def get_music(current_user: dict = Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM music ORDER BY title")
        tracks = await cursor.fetchall()
        return [MusicResponse(**dict(t)) for t in tracks]

# Upload music track
@app.post("/api/music", response_model=MusicResponse)
async def upload_music(
    file: UploadFile = File(...),
    title: str = Form(None),
    artist: str = Form(None),
    admin: dict = Depends(get_admin_user)
):
    original_filename = sanitize_filename(file.filename)

    # Use filename as title if not provided
    if not title:
        title = Path(original_filename).stem

    # Save file
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{original_filename}"
    filepath = MUSIC_DIR / filename

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO music (title, artist, file_path) VALUES (?, ?, ?)",
            (title, artist, filename)
        )
        await db.commit()
        music_id = cursor.lastrowid

    return MusicResponse(id=music_id, title=title, artist=artist, file_path=filename, duration=None)

# Bulk upload music
@app.post("/api/music/bulk-upload")
async def bulk_upload_music(
    files: List[UploadFile] = File(...),
    admin: dict = Depends(get_admin_user)
):
    created_tracks = []

    async with aiosqlite.connect(DB_PATH) as db:
        for file in files:
            original_filename = sanitize_filename(file.filename)
            title = Path(original_filename).stem

            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{original_filename}"
            filepath = MUSIC_DIR / filename

            content = await file.read()
            with open(filepath, "wb") as f:
                f.write(content)

            cursor = await db.execute(
                "INSERT INTO music (title, artist, file_path) VALUES (?, ?, ?)",
                (title, None, filename)
            )
            music_id = cursor.lastrowid
            created_tracks.append(MusicResponse(
                id=music_id, title=title, artist=None, file_path=filename, duration=None
            ))

        await db.commit()

    return {"created": len(created_tracks), "tracks": created_tracks}

# Update music track
@app.put("/api/music/{music_id}", response_model=MusicResponse)
async def update_music(music_id: int, data: MusicCreate, admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE music SET title = ?, artist = ? WHERE id = ?",
            (data.title, data.artist, music_id)
        )
        await db.commit()

        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM music WHERE id = ?", (music_id,))
        track = await cursor.fetchone()
        if not track:
            raise HTTPException(status_code=404, detail="Traccia non trovata")
        return MusicResponse(**dict(track))

# Delete music track
@app.delete("/api/music/{music_id}")
async def delete_music(music_id: int, admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT file_path FROM music WHERE id = ?", (music_id,))
        track = await cursor.fetchone()
        if track:
            filepath = MUSIC_DIR / track["file_path"]
            if filepath.exists():
                filepath.unlink()

        await db.execute("DELETE FROM playlist_items WHERE music_id = ?", (music_id,))
        await db.execute("DELETE FROM music WHERE id = ?", (music_id,))
        await db.commit()
    return {"status": "ok"}

# ============== PLAYLIST API ==============

# Get all playlists
@app.get("/api/playlists", response_model=List[PlaylistResponse])
async def get_playlists(current_user: dict = Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM playlists ORDER BY name")
        playlists = await cursor.fetchall()

        result = []
        for pl in playlists:
            cursor = await db.execute("""
                SELECT m.* FROM music m
                JOIN playlist_items pi ON m.id = pi.music_id
                WHERE pi.playlist_id = ?
                ORDER BY pi.position
            """, (pl["id"],))
            tracks = await cursor.fetchall()
            result.append(PlaylistResponse(
                id=pl["id"],
                name=pl["name"],
                tracks=[MusicResponse(**dict(t)) for t in tracks]
            ))
        return result

# Create playlist
@app.post("/api/playlists", response_model=PlaylistResponse)
async def create_playlist(playlist: PlaylistCreate, admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO playlists (name) VALUES (?)",
            (playlist.name,)
        )
        await db.commit()
        return PlaylistResponse(id=cursor.lastrowid, name=playlist.name, tracks=[])

# Update playlist
@app.put("/api/playlists/{playlist_id}", response_model=PlaylistResponse)
async def update_playlist(playlist_id: int, data: PlaylistUpdate, admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if data.name:
            await db.execute("UPDATE playlists SET name = ? WHERE id = ?", (data.name, playlist_id))

        if data.track_ids is not None:
            await db.execute("DELETE FROM playlist_items WHERE playlist_id = ?", (playlist_id,))
            for i, track_id in enumerate(data.track_ids):
                await db.execute(
                    "INSERT INTO playlist_items (playlist_id, music_id, position) VALUES (?, ?, ?)",
                    (playlist_id, track_id, i)
                )

        await db.commit()

        cursor = await db.execute("SELECT * FROM playlists WHERE id = ?", (playlist_id,))
        pl = await cursor.fetchone()
        if not pl:
            raise HTTPException(status_code=404, detail="Playlist non trovata")

        cursor = await db.execute("""
            SELECT m.* FROM music m
            JOIN playlist_items pi ON m.id = pi.music_id
            WHERE pi.playlist_id = ?
            ORDER BY pi.position
        """, (playlist_id,))
        tracks = await cursor.fetchall()

        return PlaylistResponse(
            id=pl["id"],
            name=pl["name"],
            tracks=[MusicResponse(**dict(t)) for t in tracks]
        )

# Delete playlist
@app.delete("/api/playlists/{playlist_id}")
async def delete_playlist(playlist_id: int, admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM playlist_items WHERE playlist_id = ?", (playlist_id,))
        await db.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        await db.commit()
    return {"status": "ok"}

# Add track to playlist
@app.post("/api/playlists/{playlist_id}/tracks/{music_id}")
async def add_track_to_playlist(playlist_id: int, music_id: int, admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM playlist_items WHERE playlist_id = ?",
            (playlist_id,)
        )
        position = (await cursor.fetchone())[0]
        await db.execute(
            "INSERT INTO playlist_items (playlist_id, music_id, position) VALUES (?, ?, ?)",
            (playlist_id, music_id, position)
        )
        await db.commit()
    return {"status": "ok"}

# Remove track from playlist
@app.delete("/api/playlists/{playlist_id}/tracks/{music_id}")
async def remove_track_from_playlist(playlist_id: int, music_id: int, admin: dict = Depends(get_admin_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM playlist_items WHERE playlist_id = ? AND music_id = ?",
            (playlist_id, music_id)
        )
        await db.commit()
    return {"status": "ok"}

# ============== Audio file serving ==============

@app.get("/audio/announcements/{filename}")
async def get_announcement_audio(filename: str):
    filepath = ANNOUNCEMENTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File non trovato")
    return FileResponse(filepath, media_type="audio/mpeg")

@app.get("/audio/music/{filename}")
async def get_music_audio(filename: str):
    filepath = MUSIC_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File non trovato")
    return FileResponse(filepath, media_type="audio/mpeg")

# WebSocket endpoints
@app.websocket("/ws/player")
async def websocket_player(websocket: WebSocket):
    await manager.connect_player(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.send_to_all({"type": "player_status", "data": data})
    except WebSocketDisconnect:
        manager.disconnect_player(websocket)

@app.websocket("/ws/controller")
async def websocket_controller(websocket: WebSocket):
    await manager.connect_controller(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if manager.master_active:
                await websocket.send_json({"type": "blocked", "reason": "master_active"})
                continue
            if data.get("action") == "play_announcement":
                await manager.send_to_players({
                    "type": "play",
                    "content": "announcement",
                    "id": data.get("id"),
                    "files": data.get("files", [])
                })
            elif data.get("action") == "stop":
                await manager.send_to_players({"type": "stop"})
            elif data.get("action") == "play_music":
                await manager.send_to_players({
                    "type": "play",
                    "content": "music",
                    "file": data.get("file")
                })
            elif data.get("action") == "play_playlist":
                await manager.send_to_players({
                    "type": "play_playlist",
                    "playlist_id": data.get("playlist_id"),
                    "tracks": data.get("tracks", []),
                    "shuffle": data.get("shuffle", False)
                })
            elif data.get("action") == "music_next":
                await manager.send_to_players({"type": "music_next"})
            elif data.get("action") == "music_prev":
                await manager.send_to_players({"type": "music_prev"})
            elif data.get("action") == "music_shuffle":
                await manager.send_to_players({"type": "music_shuffle"})
            elif data.get("action") == "pause":
                await manager.send_to_players({"type": "pause"})
            elif data.get("action") == "resume":
                await manager.send_to_players({"type": "resume"})
    except WebSocketDisconnect:
        manager.disconnect_controller(websocket)

@app.websocket("/ws/master")
async def websocket_master(websocket: WebSocket):
    await manager.connect_master(websocket)
    master_username = None
    try:
        while True:
            message = await websocket.receive()

            if "text" in message:
                data = json.loads(message["text"])
                if data.get("action") == "start_announcement":
                    master_username = data.get("username", "Master")
                    await manager.start_master_announcement(master_username)
                    await manager.send_to_players({"type": "stop"})
                elif data.get("action") == "stop_announcement":
                    await manager.stop_master_announcement()
                    master_username = None
            elif "bytes" in message:
                if manager.master_active:
                    await manager.send_audio_to_players(message["bytes"])
    except WebSocketDisconnect:
        if manager.master_active and manager.master_username == master_username:
            await manager.stop_master_announcement()
        manager.disconnect_master(websocket)

# Stato sistema
@app.get("/api/status")
async def get_status():
    return {
        "players_connected": len(manager.players),
        "controllers_connected": len(manager.controllers),
        "masters_connected": len(manager.masters),
        "master_active": manager.master_active,
        "master_username": manager.master_username,
        "status": "online"
    }

# Serve frontend
FRONTEND_DIR = BASE_DIR / "frontend"

@app.get("/")
async def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/{path:path}")
async def serve_static(path: str):
    file_path = FRONTEND_DIR / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(FRONTEND_DIR / "index.html")

if __name__ == "__main__":
    import uvicorn
    import ssl

    ssl_keyfile = BASE_DIR / "certs" / "audioci.key"
    ssl_certfile = BASE_DIR / "certs" / "audioci.crt"

    if ssl_keyfile.exists() and ssl_certfile.exists():
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            ssl_keyfile=str(ssl_keyfile),
            ssl_certfile=str(ssl_certfile)
        )
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)
