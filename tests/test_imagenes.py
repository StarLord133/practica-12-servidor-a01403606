JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100


def subir(cliente, cabeceras, contenido=JPEG, nombre="foto.jpg"):
    return cliente.post("/imagenes", headers=cabeceras, files={"archivo": (nombre, contenido, "image/jpeg")})


def test_sin_token_no_se_sube_ni_se_ve(cliente, clave):
    assert subir(cliente, {}).status_code == 401
    clave_foto = subir(cliente, clave).json()["id"]
    assert cliente.get(f"/imagenes/{clave_foto}").status_code == 401


def test_se_sube_y_se_descarga_igual(cliente, clave):
    r = subir(cliente, clave)
    assert r.status_code == 201
    foto = r.json()
    assert foto["tipo"] == "image/jpeg" and foto["bytes"] == len(JPEG)
    assert foto["id"].endswith(".jpg")

    r = cliente.get(f"/imagenes/{foto['id']}", headers=clave)
    assert r.status_code == 200
    assert r.content == JPEG
    assert "immutable" in r.headers["cache-control"]


def test_lo_que_no_es_foto_se_rechaza_aunque_diga_image_jpeg(cliente, clave):
    assert subir(cliente, clave, contenido=b"#!/bin/sh\nrm -rf /").status_code == 415


def test_una_foto_muy_pesada_se_rechaza(cliente, clave):
    from app import imagenes
    assert subir(cliente, clave, contenido=JPEG + b"\x00" * imagenes.MAX_BYTES).status_code == 413
    assert not any(imagenes.CARPETA.iterdir())  # no queda el pedazo a medias


def test_una_clave_inventada_no_sale_de_la_carpeta(cliente, clave):
    assert cliente.get("/imagenes/..%2F..%2Fcharla.db", headers=clave).status_code == 404


def test_el_mensaje_con_foto_llega_con_su_clave(cliente, clave):
    foto = subir(cliente, clave).json()["id"]
    with cliente.websocket_connect("/chat", headers=clave) as ws:
        ws.receive_json()
        ws.send_json({"tipo": "mensaje", "texto": "", "imagen": foto})
        recibido = ws.receive_json()
        assert (recibido["texto"], recibido["imagen"]) == ("", foto)
        # Y queda en la historia: la bienvenida siguiente la trae.
    with cliente.websocket_connect("/chat", headers=clave) as ws:
        assert ws.receive_json()["mensajes"][-1]["imagen"] == foto


def test_una_clave_que_no_existe_no_se_manda(cliente, clave):
    with cliente.websocket_connect("/chat", headers=clave) as ws:
        ws.receive_json()
        ws.send_json({"tipo": "mensaje", "texto": "", "imagen": "0" * 32 + ".jpg"})
        ws.send_json({"tipo": "mensaje", "texto": "hola"})
        recibido = ws.receive_json()  # el primero no se difundió: llega directo el segundo
        assert (recibido["texto"], recibido["imagen"]) == ("hola", None)
