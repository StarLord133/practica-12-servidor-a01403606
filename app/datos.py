"""Lo que la sala recuerda, en un archivo SQLite.

SQLite viene dentro de Python: no hay otro contenedor ni contraseña. El archivo
vive en /datos, un volumen de Docker, así que sobrevive a `docker compose down`
y a cada recarga de --reload. Sin él, cada vez que guardas un .py se borraría
la sala entera: mensajes, invitados y sus tokens.
"""
import os
import secrets
import sqlite3
import time


class Datos:
    def __init__(self, ruta: str):
        # Un solo hilo atiende todo (el del servidor), pero las pruebas lo usan
        # desde otro: check_same_thread=False lo permite.
        self.con = sqlite3.connect(ruta, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(
            """
            CREATE TABLE IF NOT EXISTS solicitudes (
                id       TEXT PRIMARY KEY,
                nickname TEXT NOT NULL,
                estado   TEXT NOT NULL,   -- pendiente | aprobada | rechazada
                token    TEXT UNIQUE      -- solo cuando se aprueba
            );
            CREATE TABLE IF NOT EXISTS mensajes (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                de    TEXT NOT NULL,
                texto TEXT NOT NULL,
                en    REAL NOT NULL       -- segundos desde 1970, como time.time()
            );
            """
        )

    # ---------- solicitudes ----------

    def nickname_ocupado(self, nickname: str) -> bool:
        """Ocupado = alguien lo pidió y no lo rechazaron."""
        fila = self.con.execute(
            "SELECT 1 FROM solicitudes WHERE lower(nickname) = lower(?) AND estado != 'rechazada'",
            (nickname,),
        ).fetchone()
        return fila is not None

    def crear_solicitud(self, nickname: str) -> dict:
        sid = secrets.token_urlsafe(8)
        with self.con:
            self.con.execute(
                "INSERT INTO solicitudes (id, nickname, estado) VALUES (?, ?, 'pendiente')",
                (sid, nickname),
            )
        return self.solicitud(sid)

    def solicitud(self, sid: str) -> dict | None:
        fila = self.con.execute("SELECT * FROM solicitudes WHERE id = ?", (sid,)).fetchone()
        return dict(fila) if fila else None

    def pendientes(self) -> list[dict]:
        filas = self.con.execute(
            "SELECT id, nickname FROM solicitudes WHERE estado = 'pendiente' ORDER BY rowid"
        ).fetchall()
        return [dict(f) for f in filas]

    def resolver(self, sid: str, aprobar: bool) -> dict | None:
        """Aprueba (y genera el token) o rechaza. Solo una vez: lo resuelto no cambia."""
        s = self.solicitud(sid)
        if s is None or s["estado"] != "pendiente":
            return None
        with self.con:
            if aprobar:
                self.con.execute(
                    "UPDATE solicitudes SET estado = 'aprobada', token = ? WHERE id = ?",
                    (secrets.token_urlsafe(24), sid),
                )
            else:
                self.con.execute("UPDATE solicitudes SET estado = 'rechazada' WHERE id = ?", (sid,))
        return self.solicitud(sid)

    def nickname_de(self, token: str) -> str | None:
        fila = self.con.execute(
            "SELECT nickname FROM solicitudes WHERE token = ? AND estado = 'aprobada'", (token,)
        ).fetchone()
        return fila["nickname"] if fila else None

    # ---------- mensajes ----------

    def guardar_mensaje(self, de: str, texto: str) -> dict:
        with self.con:
            cursor = self.con.execute(
                "INSERT INTO mensajes (de, texto, en) VALUES (?, ?, ?)", (de, texto, time.time())
            )
        fila = self.con.execute("SELECT * FROM mensajes WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(fila)

    def ultimos_mensajes(self, cuantos: int = 50) -> list[dict]:
        filas = self.con.execute(
            "SELECT * FROM mensajes ORDER BY id DESC LIMIT ?", (cuantos,)
        ).fetchall()
        return [dict(f) for f in reversed(filas)]


# La base de toda la app. Las pruebas la cambian por una en memoria.
db = Datos(os.environ.get("RUTA_DB", "/datos/charla.db"))