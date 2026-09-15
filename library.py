"""Local transcript library: SQLite notes with folders, star and trash. Stdlib only, shared by the bridge and the
transcription worker (jobs.py attaches a live recording's WAV)."""
from collections import Counter
from pathlib import Path
import re
import shutil
import sqlite3
import time

ROOT = Path(__file__).resolve().parent
LIBRARY = ROOT / "library"
DB = LIBRARY / "notes.db"
SCHEMA = """
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    created REAL NOT NULL,
    updated REAL NOT NULL,
    source TEXT NOT NULL,          -- 'audio' | 'live' (a live recording that has not finished cleanly)
    audio TEXT,                    -- copied file name under library/audio, or NULL
    transcript TEXT NOT NULL DEFAULT '',
    duration REAL,                 -- seconds, NULL until a transcription finishes
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    starred INTEGER NOT NULL DEFAULT 0,
    trashed REAL                   -- when it moved to 휴지통, NULL otherwise
);
"""
FIELDS = {"title", "transcript", "duration", "folder_id", "starred", "trashed"}
STOPWORDS = set("""화자 그리고 그래서 그런데 하지만 그러면 그러니까 이제 지금 정말 진짜 그냥 약간 이거 저거 그거 이게 그게
이렇게 저렇게 그렇게 우리 저희 여기 거기 때문 있는 없는 하는 같은 이런 그런 저런 어떤 네네 아니 근데""".split())
PARTICLE = re.compile(r"(으로|에서|에게|까지|부터|은|는|이|가|을|를|에|의|도|로|와|과)$")
ENDINGS = ("니다", "어요", "아요", "해요", "했다", "한다", "하고", "해서")


def connect(path=DB):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(SCHEMA)
    return connection


def keywords(text, limit=3):
    """Most frequent content words of a transcript, for the tag line under a board name."""
    # ponytail: frequency + particle/ending strip, no morphological analyser; swap one in if tags read badly.
    counts = Counter()
    for word in re.findall(r"[가-힣A-Za-z]{2,}", text):
        stem = PARTICLE.sub("", word) if len(word) > 2 else word
        if len(stem) >= 2 and stem not in STOPWORDS and not stem.endswith(ENDINGS):
            counts[stem] += 1
    return [word for word, _ in counts.most_common(limit)]


class Library:
    def __init__(self, path=None):
        self.path = Path(path or DB)  # resolved at call time so tests can point the module at a temporary database
        self.db = connect(self.path)

    def close(self):
        self.db.close()

    # ---- notes ---------------------------------------------------------
    def create(self, title, source, transcript="", audio=None):
        now = time.time()
        name = None
        if audio:
            folder = self.path.parent / "audio"
            folder.mkdir(parents=True, exist_ok=True)
            name = f"{int(now)}-{Path(audio).name}"
            shutil.copy2(audio, folder / name)
        with self.db:
            return self.db.execute("INSERT INTO notes(title, created, updated, source, audio, transcript) VALUES (?,?,?,?,?,?)",
                                   (title.strip() or "제목 없음", now, now, source, name, transcript)).lastrowid

    def update(self, note_id, **fields):
        unknown = set(fields) - FIELDS
        if unknown:
            raise ValueError(f"unknown fields: {unknown}")
        if "trashed" in fields:
            fields["trashed"] = time.time() if fields["trashed"] else None
        if "starred" in fields:
            fields["starred"] = int(bool(fields["starred"]))
        if not fields:
            return
        with self.db:
            sets = ", ".join(f"{name} = ?" for name in fields)
            self.db.execute(f"UPDATE notes SET {sets}, updated = ? WHERE id = ?", (*fields.values(), time.time(), note_id))

    def attach_audio(self, note_id, path):
        """Keep a live recording with its note. A note that already has audio keeps it (the recording is an addition)."""
        note = self.get(note_id)
        if not note or note["audio"]:
            return None
        folder = self.path.parent / "audio"
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{int(time.time())}-{Path(path).name}"
        shutil.copy2(path, folder / name)
        with self.db:
            self.db.execute("UPDATE notes SET audio = ?, source = 'audio', updated = ? WHERE id = ?", (name, time.time(), note_id))
        return name

    def delete(self, note_id):
        note = self.get(note_id)
        with self.db:
            self.db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        if note and note["audio"]:
            target = self.path.parent / "audio" / note["audio"]
            if target.exists():
                target.unlink()

    def get(self, note_id):
        return self.db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()

    def audio_path(self, note):
        return (self.path.parent / "audio" / note["audio"]) if note and note["audio"] else None

    def list(self, view="all", query=""):
        """Rows for one sidebar view, newest first. view: all | starred | live | trash | folder:<id>."""
        where, params = ["n.trashed IS NOT NULL" if view == "trash" else "n.trashed IS NULL"], []
        if view == "starred":
            where.append("n.starred = 1")
        elif view == "live":
            where.append("n.source = 'live'")
        elif view.startswith("folder:"):
            where.append("n.folder_id = ?")
            params.append(int(view.removeprefix("folder:")))
        elif view not in ("all", "trash"):
            raise ValueError(f"unknown view: {view}")
        if query.strip():
            where.append("(n.title LIKE ? OR n.transcript LIKE ?)")
            params += [f"%{query.strip()}%"] * 2
        return self.db.execute(
            "SELECT n.id, n.title, n.created, n.updated, n.source, n.duration, n.starred, n.trashed, n.folder_id, "
            "f.name AS folder, n.transcript FROM notes n LEFT JOIN folders f ON f.id = n.folder_id "
            f"WHERE {' AND '.join(where)} ORDER BY n.created DESC, n.id DESC", params).fetchall()

    # ---- folders -------------------------------------------------------
    def folders(self):
        return self.db.execute("SELECT id, name FROM folders ORDER BY name").fetchall()

    def create_folder(self, name):
        if not name.strip():
            raise ValueError("폴더 이름을 입력해 주세요.")
        with self.db:
            return self.db.execute("INSERT INTO folders(name) VALUES (?)", (name.strip(),)).lastrowid

    def delete_folder(self, folder_id):
        with self.db:  # notes stay; ON DELETE SET NULL clears their folder_id
            self.db.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
