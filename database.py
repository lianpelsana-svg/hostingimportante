import os
import psycopg2
from psycopg2.extras import RealDictCursor
import datetime
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    """Devuelve una conexión a la base de datos PostgreSQL."""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    """Crea las tablas necesarias si no existen."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Tabla de usuarios
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            vidas INTEGER DEFAULT 5,
            es_premium BOOLEAN DEFAULT FALSE,
            fecha_expiracion TIMESTAMP,
            ultima_vez TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tabla de pagos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            metodo TEXT,          -- 'binance', 'mercadopago'
            moneda TEXT,          -- 'USDT', 'ARS'
            monto REAL,
            estado TEXT,           -- 'pendiente', 'aprobado', 'fallido'
            payment_id TEXT,
            pedido_id TEXT UNIQUE,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_aprobacion TIMESTAMP
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Base de datos inicializada correctamente.")

def registrar_usuario(user_id, username, first_name):
    """Guarda o actualiza un usuario en la base de datos."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO usuarios (user_id, username, first_name, ultima_vez)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            ultima_vez = EXCLUDED.ultima_vez
    """, (user_id, username, first_name, datetime.datetime.now()))
    conn.commit()
    cur.close()
    conn.close()

def obtener_usuario(user_id):
    """Devuelve los datos de un usuario o None si no existe."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM usuarios WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user

def obtener_vidas(user_id):
    """Devuelve la cantidad de vidas del usuario."""
    user = obtener_usuario(user_id)
    if user:
        return user['vidas']
    return 5  # Por defecto si no existe

def actualizar_vidas(user_id, nuevas_vidas):
    """Actualiza las vidas de un usuario."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE usuarios SET vidas = %s, ultima_vez = %s
        WHERE user_id = %s
    """, (nuevas_vidas, datetime.datetime.now(), user_id))
    conn.commit()
    cur.close()
    conn.close()

def usar_vida(user_id):
    """
    Intenta usar una vida.
    Retorna (puede_jugar: bool, mensaje: str)
    """
    user = obtener_usuario(user_id)
    if not user:
        # Si no existe, lo creamos con 5 vidas
        registrar_usuario(user_id, None, None)
        user = obtener_usuario(user_id)
    
    # Si es premium, siempre puede jugar
    if user['es_premium']:
        # Verificar si la suscripción expiró
        if user['fecha_expiracion'] and user['fecha_expiracion'] < datetime.datetime.now():
            # Expirado, desactivar premium
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE usuarios SET es_premium = FALSE WHERE user_id = %s", (user_id,))
            conn.commit()
            cur.close()
            conn.close()
        else:
            return True, "premium"
    
    # No premium, restar una vida si tiene
    if user['vidas'] > 0:
        nuevas_vidas = user['vidas'] - 1
        actualizar_vidas(user_id, nuevas_vidas)
        return True, f"Te quedan {nuevas_vidas} vidas"
    else:
        return False, "Sin vidas"

def sumar_vidas(user_id, cantidad):
    """Suma vidas a un usuario (por compra o premio)."""
    vidas_actuales = obtener_vidas(user_id)
    nuevas = vidas_actuales + cantidad
    actualizar_vidas(user_id, nuevas)
    return nuevas

def activar_premium(user_id, dias=30):
    """Activa premium para un usuario."""
    conn = get_connection()
    cur = conn.cursor()
    fecha_exp = datetime.datetime.now() + datetime.timedelta(days=dias)
    cur.execute("""
        UPDATE usuarios SET es_premium = TRUE, fecha_expiracion = %s
        WHERE user_id = %s
    """, (fecha_exp, user_id))
    conn.commit()
    cur.close()
    conn.close()

def guardar_pago(user_id, metodo, moneda, monto, payment_id, pedido_id):
    """Registra un pago pendiente."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO pagos (user_id, metodo, moneda, monto, estado, payment_id, pedido_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (user_id, metodo, moneda, monto, 'pendiente', payment_id, pedido_id))
    pago_id = cur.fetchone()['id']
    conn.commit()
    cur.close()
    conn.close()
    return pago_id

def obtener_pagos_pendientes():
    """Devuelve todos los pagos con estado 'pendiente'."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM pagos WHERE estado = 'pendiente'")
    pagos = cur.fetchall()
    cur.close()
    conn.close()
    return pagos

def actualizar_pago_exitoso(pago_id):
    """Marca un pago como aprobado y registra la fecha."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE pagos SET estado = 'aprobado', fecha_aprobacion = %s
        WHERE id = %s
    """, (datetime.datetime.now(), pago_id))
    conn.commit()
    cur.close()
    conn.close()
