"""
app.py
------
Este es el archivo principal del backend. Aquí vive "la recepcionista"
que recibe peticiones desde el navegador y las traduce en acciones
sobre la base de datos (los cajones del archivero).

Cada @app.route(...) de aquí abajo es una "puerta" distinta a la que
el navegador puede tocar. Por ejemplo:
  - GET  /api/ordenes       -> "déjame ver todas las carpetas del cajón 1"
  - POST /api/ordenes       -> "agrega una carpeta nueva al cajón 1"
  - PUT  /api/ordenes/5/surtido -> "marca la carpeta #5 como surtida"

GET = pedir información (leer)
POST = crear algo nuevo
PUT = modificar algo que ya existe
"""

from flask import Flask, jsonify, request
from database import get_connection, init_db
from datetime import datetime

app = Flask(__name__)

# Esto reemplaza al paquete "flask_cors": agregamos manualmente el permiso
# para que el HTML (que vive en otra dirección) pueda hablarle a este backend.
# Sin esto, el navegador bloquearía la comunicación por seguridad.
@app.after_request
def permitir_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response

# Nos aseguramos de que la base de datos y sus cajones existan antes de arrancar
init_db()


def fila_a_diccionario(fila):
    """
    Convierte una fila de la base de datos (que viene en un formato especial
    de sqlite) en un diccionario normal de Python, que es más fácil de
    convertir a JSON para mandarlo de vuelta al navegador.
    """
    return dict(fila)


@app.route("/api/ordenes", methods=["GET"])
def listar_ordenes():
    """
    PUERTA 1: 'Déjame ver todas las carpetas del cajón orders'
    Esto es lo que usa, por ejemplo, la pantalla de Dashboard o de Órdenes
    en tu app para mostrar la tabla completa.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    filas = cursor.fetchall()
    conn.close()

    ordenes = [fila_a_diccionario(f) for f in filas]
    return jsonify(ordenes)


@app.route("/api/ping", methods=["GET"])
def ping():
    """
    PUERTA DE PRUEBA: solo para confirmar que el backend está vivo
    y respondiendo. No toca la base de datos para nada.
    """
    return jsonify({"status": "ok", "mensaje": "El backend está funcionando"})


@app.route("/api/ordenes", methods=["POST"])
def crear_orden():
    """
    PUERTA: 'Agrega una carpeta nueva al cajón orders'
    Esto es lo que usa el botón "Guardar orden" del capturista.

    El navegador manda los datos de la orden en el "cuerpo" de la
    petición (request.json), nosotros los leemos, validamos lo
    mínimo necesario, y los guardamos.
    """
    datos = request.json

    # Validamos que vengan los campos obligatorios (los mismos que
    # ya marcamos como obligatorios con * en el formulario del HTML)
    obligatorios = ["venta", "fecha_venta", "modelo", "plataforma", "razon_social", "cliente", "paqueteria"]
    faltantes = [campo for campo in obligatorios if not datos.get(campo)]
    if faltantes:
        return jsonify({"error": f"Faltan campos obligatorios: {', '.join(faltantes)}"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    ahora = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO orders (ticket, venta, fecha_venta, fecha_envio, modelo, piezas,
                             plataforma, razon_social, cliente, telefono, paqueteria,
                             rastreo, observacion, precio, creado_en)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datos.get("ticket", ""),
        datos["venta"],
        datos["fecha_venta"],
        datos.get("fecha_envio", ""),
        datos["modelo"],
        datos.get("piezas", 1),
        datos["plataforma"],
        datos["razon_social"],
        datos["cliente"],
        datos.get("telefono", ""),
        datos["paqueteria"],
        datos.get("rastreo", ""),
        datos.get("observacion", ""),
        datos.get("precio", 0),
        ahora
    ))

    nueva_orden_id = cursor.lastrowid

    # Dejamos la primera nota en el cajón de historial
    cursor.execute("""
        INSERT INTO historial (orden_id, usuario_rol, accion, fecha)
        VALUES (?, ?, ?, ?)
    """, (nueva_orden_id, "Captura", "Orden registrada", ahora))

    conn.commit()
    conn.close()

    return jsonify({"ok": True, "id": nueva_orden_id, "mensaje": "Orden registrada"}), 201


@app.route("/api/ordenes/<int:orden_id>/surtido", methods=["PUT"])
def marcar_surtido(orden_id):
    """
    PUERTA: 'Marca esta carpeta como surtida'
    Esto es lo que usa el botón "Marcar surtido" del rol Almacén.
    El <int:orden_id> en la dirección de la puerta significa que
    espera un número ahí, por ejemplo /api/ordenes/1/surtido
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Primero confirmamos que la carpeta existe y no está cancelada
    cursor.execute("SELECT surtido, cancelado FROM orders WHERE id = ?", (orden_id,))
    orden = cursor.fetchone()
    if not orden:
        conn.close()
        return jsonify({"error": "Esa orden no existe"}), 404
    if orden["cancelado"]:
        conn.close()
        return jsonify({"error": "No se puede surtir una orden cancelada"}), 400
    if orden["surtido"]:
        conn.close()
        return jsonify({"error": "Esta orden ya estaba marcada como surtida"}), 400

    ahora = datetime.now().isoformat()
    cursor.execute("UPDATE orders SET surtido = 1 WHERE id = ?", (orden_id,))
    cursor.execute("""
        INSERT INTO historial (orden_id, usuario_rol, accion, fecha)
        VALUES (?, ?, ?, ?)
    """, (orden_id, "Almacén", "Surtido físico confirmado", ahora))

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": orden_id, "surtido": True})


@app.route("/api/ordenes/<int:orden_id>/traspaso", methods=["PUT"])
def marcar_traspaso(orden_id):
    """
    PUERTA: 'Marca esta carpeta con traspaso confirmado'
    Usada por el botón "Marcar traspaso" del rol Almacén, tanto en
    envíos de hoy como en envíos posteriores (recuerda: el traspaso
    es independiente del surtido).
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT traspaso, cancelado FROM orders WHERE id = ?", (orden_id,))
    orden = cursor.fetchone()
    if not orden:
        conn.close()
        return jsonify({"error": "Esa orden no existe"}), 404
    if orden["cancelado"]:
        conn.close()
        return jsonify({"error": "No se puede traspasar una orden cancelada"}), 400
    if orden["traspaso"]:
        conn.close()
        return jsonify({"error": "Esta orden ya tenía el traspaso confirmado"}), 400

    ahora = datetime.now().isoformat()
    cursor.execute("UPDATE orders SET traspaso = 1 WHERE id = ?", (orden_id,))
    cursor.execute("""
        INSERT INTO historial (orden_id, usuario_rol, accion, fecha)
        VALUES (?, ?, ?, ?)
    """, (orden_id, "Almacén", "Traspaso en sistema confirmado", ahora))

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": orden_id, "traspaso": True})


@app.route("/api/ordenes/<int:orden_id>/ticket-cobro", methods=["PUT"])
def asentar_ticket(orden_id):
    """
    PUERTA: 'Anota o corrige el ticket de cobro de esta carpeta'
    Usada por cobranza. A diferencia de surtido/traspaso, aquí sí
    permitimos pisar un valor que ya existía (corrección de errores),
    pero dejamos registrado en el historial si fue la primera vez
    o una corrección.
    """
    datos = request.json
    ticket_nuevo = datos.get("ticket_cobro", "").strip()

    if not ticket_nuevo:
        return jsonify({"error": "El número de ticket no puede estar vacío"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT ticket_cobro, traspaso, cancelado FROM orders WHERE id = ?", (orden_id,))
    orden = cursor.fetchone()
    if not orden:
        conn.close()
        return jsonify({"error": "Esa orden no existe"}), 404
    if orden["cancelado"]:
        conn.close()
        return jsonify({"error": "No se puede asentar ticket en una orden cancelada"}), 400
    if not orden["traspaso"]:
        conn.close()
        return jsonify({"error": "Solo se puede cobrar una orden con traspaso confirmado"}), 400

    ticket_anterior = orden["ticket_cobro"]
    ahora = datetime.now().isoformat()

    if ticket_anterior == ticket_nuevo:
        conn.close()
        return jsonify({"ok": True, "sin_cambios": True})

    cursor.execute("UPDATE orders SET ticket_cobro = ? WHERE id = ?", (ticket_nuevo, orden_id))

    if not ticket_anterior:
        nota = f"Ticket de cobro asentado: {ticket_nuevo}"
    else:
        nota = f"Ticket de cobro corregido: {ticket_anterior} → {ticket_nuevo}"

    cursor.execute("""
        INSERT INTO historial (orden_id, usuario_rol, accion, fecha)
        VALUES (?, ?, ?, ?)
    """, (orden_id, "Cobranza", nota, ahora))

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": orden_id, "ticket_cobro": ticket_nuevo})


@app.route("/api/ordenes/<int:orden_id>/cancelar", methods=["PUT"])
def cancelar_orden(orden_id):
    """
    PUERTA: 'Cancela esta carpeta'
    Solo el rol Captura debería usar esta puerta (eso se valida en
    el HTML, pero en una versión con login real, también se valida
    aquí en el backend).

    Antes de cancelar, "tomamos una foto" de cómo estaba la orden:
    si ya tenía surtido, traspaso, o ticket de cobro. Esa foto es la
    que después usa el módulo de Cancelaciones para saber qué
    pendientes generarle a cada equipo.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT surtido, traspaso, ticket_cobro, cancelado FROM orders WHERE id = ?", (orden_id,))
    orden = cursor.fetchone()
    if not orden:
        conn.close()
        return jsonify({"error": "Esa orden no existe"}), 404
    if orden["cancelado"]:
        conn.close()
        return jsonify({"error": "Esta orden ya estaba cancelada"}), 400

    ahora = datetime.now().isoformat()

    cursor.execute("""
        UPDATE orders
        SET cancelado = 1, surtido_previo = ?, traspaso_previo = ?
        WHERE id = ?
    """, (orden["surtido"], orden["traspaso"], orden_id))

    nota = "CANCELADA"
    if orden["surtido"]:
        nota += " — surtido previo: sí"
    if orden["traspaso"]:
        nota += " — traspaso previo: sí"
    if orden["ticket_cobro"]:
        nota += f" — ticket a cancelar: {orden['ticket_cobro']}"

    cursor.execute("""
        INSERT INTO historial (orden_id, usuario_rol, accion, fecha)
        VALUES (?, ?, ?, ?)
    """, (orden_id, "Captura", nota, ahora))

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": orden_id, "cancelado": True})


@app.route("/api/ordenes/<int:orden_id>/historial", methods=["GET"])
def ver_historial(orden_id):
    """
    PUERTA: 'Déjame ver todas las notitas de esta carpeta específica'
    Esto es lo que usa el modal de detalle cuando le das clic a una orden.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT usuario_rol, accion, fecha FROM historial
        WHERE orden_id = ? ORDER BY id ASC
    """, (orden_id,))
    filas = cursor.fetchall()
    conn.close()
    return jsonify([fila_a_diccionario(f) for f in filas])


@app.route("/api/ordenes/<int:orden_id>/editar", methods=["PUT", "OPTIONS"])
def editar_orden(orden_id):
    """
    PUERTA: 'Modifica los datos capturables de una orden existente'.
    Solo el rol Captura usa esta puerta (validación en frontend).
    Requiere el campo 'motivo' obligatorio — queda registrado en historial.
    Bloquea campos de otros roles: surtido, traspaso, ticket_cobro, cancelado.
    """
    if request.method == "OPTIONS":
        return "", 200

    datos = request.json
    motivo = (datos.get("motivo") or "").strip()
    if not motivo:
        return jsonify({"error": "El motivo de la modificación es obligatorio"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT cancelado FROM orders WHERE id = ?", (orden_id,))
    orden = cursor.fetchone()
    if not orden:
        conn.close()
        return jsonify({"error": "Orden no encontrada"}), 404
    if orden["cancelado"]:
        conn.close()
        return jsonify({"error": "No se puede editar una orden cancelada"}), 400

    # Solo estos campos pueden ser modificados por Captura
    campos_editables = [
        "venta", "fecha_venta", "fecha_envio", "modelo", "piezas",
        "plataforma", "razon_social", "cliente", "telefono",
        "paqueteria", "rastreo", "observacion", "precio"
    ]
    sets = ", ".join(f"{campo} = ?" for campo in campos_editables if campo in datos)
    vals = [datos[campo] for campo in campos_editables if campo in datos]
    if not sets:
        conn.close()
        return jsonify({"error": "No se enviaron campos a editar"}), 400

    ahora = datetime.now().isoformat()
    cursor.execute(f"UPDATE orders SET {sets} WHERE id = ?", (*vals, orden_id))
    cursor.execute(
        "INSERT INTO historial (orden_id, usuario_rol, accion, fecha) VALUES (?, ?, ?, ?)",
        (orden_id, "Captura", f"ORDEN MODIFICADA — {motivo}", ahora)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": orden_id})


@app.route("/api/amazon/ordenes/<int:orden_id>/editar", methods=["PUT", "OPTIONS"])
def editar_orden_amazon(orden_id):
    """
    PUERTA: igual que editar_orden pero opera sobre orders_amazon / historial_amazon.
    """
    if request.method == "OPTIONS":
        return "", 200

    datos = request.json
    motivo = (datos.get("motivo") or "").strip()
    if not motivo:
        return jsonify({"error": "El motivo de la modificación es obligatorio"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT cancelado FROM orders_amazon WHERE id = ?", (orden_id,))
    orden = cursor.fetchone()
    if not orden:
        conn.close()
        return jsonify({"error": "Orden no encontrada"}), 404
    if orden["cancelado"]:
        conn.close()
        return jsonify({"error": "No se puede editar una orden cancelada"}), 400

    campos_editables = [
        "venta", "fecha_venta", "fecha_envio", "modelo", "piezas",
        "plataforma", "razon_social", "cliente", "telefono",
        "paqueteria", "rastreo", "observacion", "precio"
    ]
    sets = ", ".join(f"{campo} = ?" for campo in campos_editables if campo in datos)
    vals = [datos[campo] for campo in campos_editables if campo in datos]
    if not sets:
        conn.close()
        return jsonify({"error": "No se enviaron campos a editar"}), 400

    ahora = datetime.now().isoformat()
    cursor.execute(f"UPDATE orders_amazon SET {sets} WHERE id = ?", (*vals, orden_id))
    cursor.execute(
        "INSERT INTO historial_amazon (orden_id, usuario_rol, accion, fecha) VALUES (?, ?, ?, ?)",
        (orden_id, "Captura", f"ORDEN MODIFICADA — {motivo}", ahora)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": orden_id})


# ════════════════════════════════════════════════════════════
# MÓDULO AMAZON — mismo patrón que el módulo General, pero
# tocando el cajón "orders_amazon" en vez de "orders".
# Cada puerta usa el prefijo /api/amazon/ para no chocar nunca
# con las puertas del módulo General.
# ════════════════════════════════════════════════════════════

@app.route("/api/amazon/ordenes", methods=["GET"])
def listar_ordenes_amazon():
    """PUERTA: ver todas las órdenes del cajón orders_amazon"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders_amazon ORDER BY id DESC")
    filas = cursor.fetchall()
    conn.close()
    return jsonify([fila_a_diccionario(f) for f in filas])


@app.route("/api/amazon/ordenes", methods=["POST"])
def crear_orden_amazon():
    """PUERTA: agregar una carpeta nueva al cajón orders_amazon"""
    datos = request.json
    obligatorios = ["venta", "fecha_venta", "modelo", "plataforma", "razon_social", "cliente", "paqueteria"]
    faltantes = [campo for campo in obligatorios if not datos.get(campo)]
    if faltantes:
        return jsonify({"error": f"Faltan campos obligatorios: {', '.join(faltantes)}"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    ahora = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO orders_amazon (ticket, venta, fecha_venta, fecha_envio, modelo, piezas,
                             plataforma, razon_social, cliente, telefono, paqueteria,
                             rastreo, observacion, precio, creado_en)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datos.get("ticket", ""), datos["venta"], datos["fecha_venta"],
        datos.get("fecha_envio", ""), datos["modelo"], datos.get("piezas", 1),
        datos["plataforma"], datos["razon_social"], datos["cliente"],
        datos.get("telefono", ""), datos["paqueteria"], datos.get("rastreo", ""),
        datos.get("observacion", ""), datos.get("precio", 0), ahora
    ))

    nueva_orden_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO historial_amazon (orden_id, usuario_rol, accion, fecha)
        VALUES (?, ?, ?, ?)
    """, (nueva_orden_id, "Captura", "Orden registrada (Amazon)", ahora))

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": nueva_orden_id, "mensaje": "Orden Amazon registrada"}), 201


@app.route("/api/amazon/ordenes/<int:orden_id>/surtido", methods=["PUT"])
def marcar_surtido_amazon(orden_id):
    """PUERTA: marcar surtido en el cajón orders_amazon"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT surtido, cancelado FROM orders_amazon WHERE id = ?", (orden_id,))
    orden = cursor.fetchone()
    if not orden:
        conn.close()
        return jsonify({"error": "Esa orden no existe"}), 404
    if orden["cancelado"]:
        conn.close()
        return jsonify({"error": "No se puede surtir una orden cancelada"}), 400
    if orden["surtido"]:
        conn.close()
        return jsonify({"error": "Esta orden ya estaba marcada como surtida"}), 400

    ahora = datetime.now().isoformat()
    cursor.execute("UPDATE orders_amazon SET surtido = 1 WHERE id = ?", (orden_id,))
    cursor.execute("""
        INSERT INTO historial_amazon (orden_id, usuario_rol, accion, fecha)
        VALUES (?, ?, ?, ?)
    """, (orden_id, "Almacén", "Surtido físico confirmado", ahora))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": orden_id, "surtido": True})


@app.route("/api/amazon/ordenes/<int:orden_id>/traspaso", methods=["PUT"])
def marcar_traspaso_amazon(orden_id):
    """PUERTA: marcar traspaso en el cajón orders_amazon"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT traspaso, cancelado FROM orders_amazon WHERE id = ?", (orden_id,))
    orden = cursor.fetchone()
    if not orden:
        conn.close()
        return jsonify({"error": "Esa orden no existe"}), 404
    if orden["cancelado"]:
        conn.close()
        return jsonify({"error": "No se puede traspasar una orden cancelada"}), 400
    if orden["traspaso"]:
        conn.close()
        return jsonify({"error": "Esta orden ya tenía el traspaso confirmado"}), 400

    ahora = datetime.now().isoformat()
    cursor.execute("UPDATE orders_amazon SET traspaso = 1 WHERE id = ?", (orden_id,))
    cursor.execute("""
        INSERT INTO historial_amazon (orden_id, usuario_rol, accion, fecha)
        VALUES (?, ?, ?, ?)
    """, (orden_id, "Almacén", "Traspaso en sistema confirmado", ahora))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": orden_id, "traspaso": True})


@app.route("/api/amazon/ordenes/<int:orden_id>/ticket-cobro", methods=["PUT"])
def asentar_ticket_amazon(orden_id):
    """PUERTA: asentar o corregir ticket de cobro en orders_amazon"""
    datos = request.json
    ticket_nuevo = datos.get("ticket_cobro", "").strip()
    if not ticket_nuevo:
        return jsonify({"error": "El número de ticket no puede estar vacío"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticket_cobro, traspaso, cancelado FROM orders_amazon WHERE id = ?", (orden_id,))
    orden = cursor.fetchone()
    if not orden:
        conn.close()
        return jsonify({"error": "Esa orden no existe"}), 404
    if orden["cancelado"]:
        conn.close()
        return jsonify({"error": "No se puede asentar ticket en una orden cancelada"}), 400
    if not orden["traspaso"]:
        conn.close()
        return jsonify({"error": "Solo se puede cobrar una orden con traspaso confirmado"}), 400

    ticket_anterior = orden["ticket_cobro"]
    ahora = datetime.now().isoformat()
    if ticket_anterior == ticket_nuevo:
        conn.close()
        return jsonify({"ok": True, "sin_cambios": True})

    cursor.execute("UPDATE orders_amazon SET ticket_cobro = ? WHERE id = ?", (ticket_nuevo, orden_id))
    nota = f"Ticket de cobro asentado: {ticket_nuevo}" if not ticket_anterior else f"Ticket de cobro corregido: {ticket_anterior} → {ticket_nuevo}"
    cursor.execute("""
        INSERT INTO historial_amazon (orden_id, usuario_rol, accion, fecha)
        VALUES (?, ?, ?, ?)
    """, (orden_id, "Cobranza", nota, ahora))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": orden_id, "ticket_cobro": ticket_nuevo})


@app.route("/api/amazon/ordenes/<int:orden_id>/cancelar", methods=["PUT"])
def cancelar_orden_amazon(orden_id):
    """PUERTA: cancelar una orden en orders_amazon, guardando la "foto" previa"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT surtido, traspaso, ticket_cobro, cancelado FROM orders_amazon WHERE id = ?", (orden_id,))
    orden = cursor.fetchone()
    if not orden:
        conn.close()
        return jsonify({"error": "Esa orden no existe"}), 404
    if orden["cancelado"]:
        conn.close()
        return jsonify({"error": "Esta orden ya estaba cancelada"}), 400

    ahora = datetime.now().isoformat()
    cursor.execute("""
        UPDATE orders_amazon
        SET cancelado = 1, surtido_previo = ?, traspaso_previo = ?
        WHERE id = ?
    """, (orden["surtido"], orden["traspaso"], orden_id))

    nota = "CANCELADA"
    if orden["surtido"]: nota += " — surtido previo: sí"
    if orden["traspaso"]: nota += " — traspaso previo: sí"
    if orden["ticket_cobro"]: nota += f" — ticket a cancelar: {orden['ticket_cobro']}"

    cursor.execute("""
        INSERT INTO historial_amazon (orden_id, usuario_rol, accion, fecha)
        VALUES (?, ?, ?, ?)
    """, (orden_id, "Captura", nota, ahora))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": orden_id, "cancelado": True})


@app.route("/api/amazon/ordenes/<int:orden_id>/historial", methods=["GET"])
def ver_historial_amazon(orden_id):
    """PUERTA: ver las notitas de una orden específica del módulo Amazon"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT usuario_rol, accion, fecha FROM historial_amazon
        WHERE orden_id = ? ORDER BY id ASC
    """, (orden_id,))
    filas = cursor.fetchall()
    conn.close()
    return jsonify([fila_a_diccionario(f) for f in filas])


if __name__ == "__main__":
    # Esto arranca el "recepcionista" y lo deja escuchando peticiones
    # en la dirección http://localhost:5000
    app.run(debug=True, port=5000)
