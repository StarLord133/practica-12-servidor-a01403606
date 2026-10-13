"""Pedir entrar a la sala. Es HTTP normal: quien pide todavía no tiene token para el WebSocket."""
from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StringConstraints

from app import datos, sala

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])

Nickname = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=20)]
RESERVADOS = {"anfitrión", "anfitrion", "sala"}


class NuevaSolicitud(BaseModel):
    nickname: Nickname


@router.post("", status_code=201)
async def solicitar(nueva: NuevaSolicitud):
    if nueva.nickname.lower() in RESERVADOS or datos.db.nickname_ocupado(nueva.nickname):
        raise HTTPException(409, "Ese nickname ya está en la sala")
    s = datos.db.crear_solicitud(nueva.nickname)
    # Al anfitrión le llega en vivo, por su WebSocket. Si no está conectado, la
    # verá en la bienvenida la próxima vez que entre.
    await sala.avisar_al_anfitrion({"tipo": "solicitud", "id": s["id"], "nickname": s["nickname"]})
    return s


@router.get("/{sid}")
def consultar(sid: str):
    """Quien pidió entrar pregunta aquí cada par de segundos. Cuando lo aprueban, recibe su token."""
    s = datos.db.solicitud(sid)
    if s is None:
        raise HTTPException(404, "No existe esa solicitud")
    return s