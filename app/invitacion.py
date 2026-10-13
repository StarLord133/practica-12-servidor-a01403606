"""La dirección pública de la sala: la que va en el QR.

cloudflared inventa una dirección nueva cada vez que arranca y la anuncia en
su puerto de métricas (/quicktunnel). El servidor se la pregunta, así nadie
tiene que copiarla a mano de los logs.
"""
import asyncio
import json
import os
import urllib.request

from fastapi import APIRouter, HTTPException

router = APIRouter()

# `tunel` es el nombre del servicio en docker-compose.yml: dentro de la red de Docker, es su dirección.
METRICAS_TUNEL = os.environ.get("METRICAS_TUNEL", "http://tunel:2000/quicktunnel")


def leer(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=3) as respuesta:
        return respuesta.read()


@router.get("/invitacion")
async def invitacion():
    try:
        # urllib bloquea: se corre en otro hilo para no detener la sala mientras tanto.
        cuerpo = await asyncio.to_thread(leer, METRICAS_TUNEL)
    except OSError:
        raise HTTPException(503, "El túnel no está corriendo")
    host = json.loads(cuerpo).get("hostname")
    if not host:
        raise HTTPException(503, "El túnel todavía no tiene dirección: espera unos segundos")
    return {"url": f"https://{host}"}