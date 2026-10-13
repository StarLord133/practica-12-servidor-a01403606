import os

# Antes de importar la app: la clave y una base en memoria, no la del volumen.
os.environ.setdefault("CLAVE_ANFITRION", "clave-de-prueba")
os.environ["RUTA_DB"] = ":memory:"

import pytest
from fastapi.testclient import TestClient

from app import datos
from app.main import app


@pytest.fixture
def cliente(monkeypatch):
    # Una base nueva para cada prueba: ninguna depende de lo que dejó la anterior.
    monkeypatch.setattr(datos, "db", datos.Datos(":memory:"))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def clave():
    from app.sala import CLAVE_ANFITRION
    return {"Authorization": f"Bearer {CLAVE_ANFITRION}"}
    