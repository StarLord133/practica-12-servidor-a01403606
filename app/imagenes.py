"""Las fotos de la sala.

Una foto no viaja por el WebSocket: se sube aquí por HTTP (multipart, como un
formulario con archivo) y el servidor contesta una CLAVE. Después el mensaje
lleva solo esa clave, y quien lo recibe pide la foto con ella.

Las fotos viven en /datos/imagenes, el mismo volumen que la base: sobreviven a
`docker compose down`. La base nunca guarda la foto, solo su clave.
"""
import os
import re
import secrets
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app import sala

router = APIRouter(prefix="/imagenes", tags=["imagenes"])

CARPETA = Path(os.environ.get("RUTA_IMAGENES", "/datos/imagenes"))
MAX_BYTES = 5 * 1024 * 1024  # la app ya comprime a ~100 KB; esto frena a quien no use la app
TROZO = 64 * 1024

# El tipo se decide por los primeros bytes del archivo, no por lo que diga el
# cliente: un `Content-Type: image/jpeg` se escribe en cualquier cosa.
FIRMAS = {
    "jpg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "webp": (b"RIFF",),  # y "WEBP" en los bytes 8 a 12, ver tipo_de()
}
MIME = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}

# Una clave es lo que inventa subir(): 32 hex y su extensión. Nada de "../".
CLAVE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")


def tipo_de(inicio: bytes) -> str | None:
    for ext, firmas in FIRMAS.items():
        if any(inicio.startswith(f) for f in firmas):
            if ext == "webp" and inicio[8:12] != b"WEBP":
                continue
            return ext
    return None


def autorizado(authorization: str) -> str:
    """Las fotos de la sala son de la sala: solo entra quien tiene token."""
    token = authorization.removeprefix("Bearer ").strip()
    yo = sala.identificar(token)
    if yo is None:
        raise HTTPException(401, "Necesitas el token de la sala")
    return yo


def existe(clave: str) -> bool:
    return bool(CLAVE.match(clave)) and (CARPETA / clave).is_file()


@router.post("", status_code=201)
async def subir(archivo: UploadFile, authorization: str = Header("")):
    autorizado(authorization)
    inicio = await archivo.read(TROZO)
    ext = tipo_de(inicio)
    if ext is None:
        raise HTTPException(415, "Solo se aceptan fotos JPEG, PNG o WebP")

    CARPETA.mkdir(parents=True, exist_ok=True)
    clave = f"{secrets.token_hex(16)}.{ext}"
    destino = CARPETA / clave
    total = 0
    try:
        with destino.open("wb") as f:
            trozo = inicio
            while trozo:
                total += len(trozo)
                if total > MAX_BYTES:
                    raise HTTPException(413, "La foto pesa más de 5 MB")
                f.write(trozo)
                trozo = await archivo.read(TROZO)
    except HTTPException:
        destino.unlink(missing_ok=True)
        raise
    return {"id": clave, "tipo": MIME[ext], "bytes": total}


@router.get("/{clave}")
def ver(clave: str, authorization: str = Header("")):
    autorizado(authorization)
    if not existe(clave):
        raise HTTPException(404, "No existe esa foto")
    # Una clave nunca cambia de contenido: el teléfono la puede guardar para siempre.
    return FileResponse(
        CARPETA / clave,
        media_type=MIME[clave.rsplit(".", 1)[1]],
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )
