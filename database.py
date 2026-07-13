"""
database.py
------------
Este archivo define la "forma" de nuestra base de datos: qué tablas existen
y qué columnas tiene cada una. Es el equivalente a las pestañas y columnas
de tu Excel, pero en una base de datos real.

No necesitas instalar nada extra: sqlite3 viene incluido en Python.
La base de datos completa va a vivir en un solo archivo: orderflow.db
"""

import sqlite3
from pathlib import Path

# Ruta donde se va a guardar el archivo de la base de datos
DB_PATH = Path(__file__).parent / "orderflow.db"


def get_connection():
    """
    Abre una conexión a la base de datos. Cada vez que el backend
    necesita leer o escribir algo, usa esta función primero.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # permite acceder a columnas por nombre, ej: row["modelo"]
    return conn


def init_db():
    """
    Crea las tablas si no existen todavía. Se ejecuta una sola vez,
    la primera vez que arranca el sistema.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Tabla principal: las órdenes (equivalente a cada fila de tu Excel)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket TEXT DEFAULT '',
            venta TEXT NOT NULL,
            fecha_venta TEXT NOT NULL,
            fecha_envio TEXT,
            modelo TEXT NOT NULL,
            piezas INTEGER NOT NULL DEFAULT 1,
            plataforma TEXT NOT NULL,
            razon_social TEXT NOT NULL,
            cliente TEXT NOT NULL,
            telefono TEXT DEFAULT '',
            paqueteria TEXT NOT NULL,
            rastreo TEXT DEFAULT '',
            observacion TEXT DEFAULT '',
            precio REAL DEFAULT 0,
            surtido INTEGER DEFAULT 0,
            traspaso INTEGER DEFAULT 0,
            ticket_cobro TEXT DEFAULT '',
            cancelado INTEGER DEFAULT 0,
            surtido_previo INTEGER DEFAULT 0,
            traspaso_previo INTEGER DEFAULT 0,
            creado_en TEXT NOT NULL
        )
    """)

    # Tabla de historial: cada cambio que se hace a una orden queda aquí.
    # Esto es lo que reemplaza el "log" que teníamos en JavaScript.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            orden_id INTEGER NOT NULL,
            usuario_rol TEXT NOT NULL,
            accion TEXT NOT NULL,
            fecha TEXT NOT NULL,
            FOREIGN KEY (orden_id) REFERENCES orders (id)
        )
    """)

    # ── MÓDULO AMAZON ──────────────────────────────────────────
    # Cajón completamente aparte del módulo General. Misma estructura
    # de columnas, pero vive en su propia tabla para que nada de lo
    # que pase aquí se mezcle con las órdenes de plataformas generales.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders_amazon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket TEXT DEFAULT '',
            venta TEXT NOT NULL,
            fecha_venta TEXT NOT NULL,
            fecha_envio TEXT,
            modelo TEXT NOT NULL,
            piezas INTEGER NOT NULL DEFAULT 1,
            plataforma TEXT NOT NULL,
            razon_social TEXT NOT NULL,
            cliente TEXT NOT NULL,
            telefono TEXT DEFAULT '',
            paqueteria TEXT NOT NULL,
            rastreo TEXT DEFAULT '',
            observacion TEXT DEFAULT '',
            precio REAL DEFAULT 0,
            surtido INTEGER DEFAULT 0,
            traspaso INTEGER DEFAULT 0,
            ticket_cobro TEXT DEFAULT '',
            cancelado INTEGER DEFAULT 0,
            surtido_previo INTEGER DEFAULT 0,
            traspaso_previo INTEGER DEFAULT 0,
            creado_en TEXT NOT NULL
        )
    """)

    # Su propio cajón de historial, separado del historial general
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_amazon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            orden_id INTEGER NOT NULL,
            usuario_rol TEXT NOT NULL,
            accion TEXT NOT NULL,
            fecha TEXT NOT NULL,
            FOREIGN KEY (orden_id) REFERENCES orders_amazon (id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"Base de datos lista en: {DB_PATH}")


if __name__ == "__main__":
    init_db()
