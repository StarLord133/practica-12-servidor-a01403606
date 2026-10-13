"""Charla: el servidor de UNA sala de chat, la tuya. Corre en tu computadora."""
from fastapi import FastAPI

from app import invitacion, sala, solicitudes

app = FastAPI(title="Charla")
app.include_router(sala.router)
app.include_router(solicitudes.router)
app.include_router(invitacion.router)


@app.get("/salud")
def salud():
    return {"ok": True}