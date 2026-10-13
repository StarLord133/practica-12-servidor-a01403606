import pytest
from starlette.websockets import WebSocketDisconnect

from app import invitacion


def pedir(cliente, nickname):
    return cliente.post("/solicitudes", json={"nickname": nickname})


def test_la_sala_responde(cliente):
    assert cliente.get("/salud").json() == {"ok": True}


def test_un_nickname_de_una_letra_no_se_acepta(cliente):
    assert pedir(cliente, "a").status_code == 422


def test_dos_personas_no_pueden_llamarse_igual(cliente):
    assert pedir(cliente, "dani").status_code == 201
    assert pedir(cliente, "Dani").status_code == 409
    assert pedir(cliente, "anfitrión").status_code == 409


def test_sin_token_no_se_entra_al_chat(cliente):
    with pytest.raises(WebSocketDisconnect) as e:
        with cliente.websocket_connect("/chat") as ws:
            ws.receive_json()
    assert e.value.code == 1008


def test_el_anfitrion_aprueba_y_el_invitado_chatea(cliente, clave):
    with cliente.websocket_connect("/chat", headers=clave) as anfitrion:
        assert anfitrion.receive_json()["yo"] == "anfitrión"

        s = pedir(cliente, "dani").json()
        assert s["estado"] == "pendiente" and s["token"] is None
        assert anfitrion.receive_json() == {"tipo": "solicitud", "id": s["id"], "nickname": "dani"}

        anfitrion.send_json({"tipo": "aprobar", "id": s["id"]})
        assert anfitrion.receive_json()["texto"] == "dani entró a la sala"
        token = cliente.get(f"/solicitudes/{s['id']}").json()["token"]

        with cliente.websocket_connect("/chat", headers={"Authorization": f"Bearer {token}"}) as dani:
            bienvenida = dani.receive_json()
            assert bienvenida["yo"] == "dani"
            assert bienvenida["solicitudes"] == []  # las solicitudes solo las ve el anfitrión
            dani.send_json({"tipo": "mensaje", "texto": "  hola  "})
            recibido = anfitrion.receive_json()
            assert (recibido["de"], recibido["texto"]) == ("dani", "hola")


def test_un_invitado_no_puede_aprobar_a_otro(cliente, clave):
    with cliente.websocket_connect("/chat", headers=clave) as anfitrion:
        anfitrion.receive_json()
        dani = pedir(cliente, "dani").json()
        anfitrion.receive_json()
        anfitrion.send_json({"tipo": "aprobar", "id": dani["id"]})
        anfitrion.receive_json()
        token = cliente.get(f"/solicitudes/{dani['id']}").json()["token"]

        eli = pedir(cliente, "eli").json()
        anfitrion.receive_json()
        with cliente.websocket_connect("/chat", headers={"Authorization": f"Bearer {token}"}) as ws:
            ws.receive_json()
            ws.send_json({"tipo": "aprobar", "id": eli["id"]})
            ws.send_json({"tipo": "mensaje", "texto": "listo"})
            ws.receive_json()  # cuando llega su mensaje, la orden anterior ya se atendió
        assert cliente.get(f"/solicitudes/{eli['id']}").json()["estado"] == "pendiente"


def test_el_historial_llega_al_entrar(cliente, clave):
    with cliente.websocket_connect("/chat", headers=clave) as ws:
        ws.receive_json()
        ws.send_json({"tipo": "mensaje", "texto": "primero"})
        ws.receive_json()
    with cliente.websocket_connect("/chat", headers=clave) as ws:
        assert [m["texto"] for m in ws.receive_json()["mensajes"]] == ["primero"]


def test_sin_tunel_la_invitacion_dice_por_que(cliente, monkeypatch):
    monkeypatch.setattr(invitacion, "METRICAS_TUNEL", "http://127.0.0.1:9/quicktunnel")
    r = cliente.get("/invitacion")
    assert r.status_code == 503
    assert r.json()["detail"] == "El túnel no está corriendo"