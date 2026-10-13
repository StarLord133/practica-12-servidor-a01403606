"""La sala: un WebSocket por persona conectada, y lo que dice uno le llega a todos.

HTTP es «pregunto y me contestan». Un WebSocket se queda abierto en los dos
sentidos: el servidor puede hablar sin que nadie le pregunte. Eso es lo que
necesita un chat.
"""
import os
import secrets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import datos

router = APIRouter()

# Quien se conecta con esta clave es el dueño de la sala. Viene del .env.
CLAVE_ANFITRION = os.environ["CLAVE_ANFITRION"]
ANFITRION = "anfitrión"

# Quién está conectado ahora mismo. Vive en memoria: una conexión no se puede guardar en disco.
conectados: dict[WebSocket, str] = {}


def quien_es(ws: WebSocket) -> str | None:
    """El nickname de quien abre la conexión, por su token. None = no tiene permiso."""
    token = ws.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not token:
        return None
    # compare_digest tarda lo mismo aunque falle en la primera letra: no regala pistas.
    if secrets.compare_digest(token, CLAVE_ANFITRION):
        return ANFITRION
    return datos.db.nickname_de(token)


async def difundir(evento: dict) -> None:
    """A todos los conectados. Si uno ya se fue, se le quita de la lista."""
    for ws in list(conectados):
        try:
            await ws.send_json(evento)
        except Exception:
            conectados.pop(ws, None)


async def avisar_al_anfitrion(evento: dict) -> None:
    for ws, quien in list(conectados.items()):
        if quien == ANFITRION:
            await ws.send_json(evento)


@router.websocket("/chat")
async def chat(ws: WebSocket):
    yo = quien_es(ws)
    if yo is None:
        # Cerrar ANTES de aceptar: el cliente recibe un 403 y no llega a entrar.
        await ws.close(code=1008)
        return
    await ws.accept()
    conectados[ws] = yo
    await ws.send_json({
        "tipo": "bienvenida",
        "yo": yo,
        "mensajes": datos.db.ultimos_mensajes(),
        "solicitudes": datos.db.pendientes() if yo == ANFITRION else [],
    })
    try:
        while True:
            orden = await ws.receive_json()
            await atender(yo, orden)
    except WebSocketDisconnect:
        pass
    finally:
        conectados.pop(ws, None)


async def atender(yo: str, orden: dict) -> None:
    tipo = orden.get("tipo")
    if tipo == "mensaje":
        texto = str(orden.get("texto", "")).strip()[:500]
        if texto:
            await difundir({"tipo": "mensaje", **datos.db.guardar_mensaje(yo, texto)})
    elif tipo in ("aprobar", "rechazar") and yo == ANFITRION:
        s = datos.db.resolver(str(orden.get("id", "")), aprobar=tipo == "aprobar")
        if s and s["estado"] == "aprobada":
            aviso = datos.db.guardar_mensaje("sala", f"{s['nickname']} entró a la sala")
            await difundir({"tipo": "mensaje", **aviso})