"""Charla: el servidor de UNA sala de chat, la tuya. Corre en tu computadora."""
from fastapi import FastAPI

from app import sala, solicitudes

app = FastAPI(title="Charla")
app.include_router(sala.router)
app.include_router(solicitudes.router)


@app.get("/salud")
def salud():
    return {"ok": True}