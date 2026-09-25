#!/usr/bin/env python3
import json
import os
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "menu.db"

SEED_CATEGORIES = [
    ("Para empezar", 1),
    ("Principales", 2),
    ("Ensaladas", 3),
    ("Dulce final", 4),
    ("Bebidas", 5),
]
SEED_PRODUCTS = [
    ("Pan de masa madre", "Mantequilla de hierbas, oliva y sal marina.", 399000, "🍞", 1, 1, 1),
    ("Burrata cremosa", "Tomates asados, pesto de albahaca y focaccia.", 749000, "🍅", 1, 1, 1),
    ("Papas bravas", "Papas rústicas, alioli de limón y pimentón.", 499000, "🥔", 1, 1, 1),
    ("Pollo a la brasa", "Con papas al romero, ensalada fresca y jugo de cocción.", 1099000, "🍗", 2, 0, 1),
    ("Risotto de estación", "Hongos, zapallo asado, parmesano y tomillo.", 999000, "🍚", 2, 1, 1),
    ("Pesca del día", "Pesca fresca, puré de coliflor y mantequilla de alcaparras.", 1299000, "🐟", 2, 0, 1),
    ("Ensalada de burrata", "Hojas verdes, durazno, nueces y vinagreta de miel.", 799000, "🥗", 3, 1, 1),
    ("Tiramisú de la casa", "Mascarpone, café, cacao y vainillas artesanales.", 499000, "🍰", 4, 1, 1),
    ("Flan de manjar", "Flan casero, crema y crocante de almendras.", 449000, "🍮", 4, 0, 1),
    ("Limonada con menta", "Limón recién exprimido, menta y un toque de jengibre.", 299000, "🍋", 5, 1, 1),
    ("Vino de la casa", "Copa de 150 ml.", 399000, "🍷", 5, 0, 1),
    ("Agua con gas", "Botella de 500 ml.", 199000, "💧", 5, 0, 1),
]


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES categories(id),
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
                emoji TEXT NOT NULL DEFAULT '🍽️',
                vegetarian INTEGER NOT NULL DEFAULT 0 CHECK (vegetarian IN (0, 1)),
                available INTEGER NOT NULL DEFAULT 1 CHECK (available IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                table_number TEXT,
                notes TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'confirmed', 'preparing', 'ready', 'delivered', 'cancelled')),
                total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id),
                product_name TEXT NOT NULL,
                unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                subtotal_cents INTEGER NOT NULL CHECK (subtotal_cents >= 0)
            );
            CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
            CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
            """
        )
        if connection.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            connection.executemany("INSERT INTO categories (name, sort_order) VALUES (?, ?)", SEED_CATEGORIES)
        if connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            connection.executemany(
                """INSERT INTO products
                (name, description, price_cents, emoji, category_id, vegetarian, available)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                SEED_PRODUCTS,
            )
        else:
            # Keep an existing local database aligned with the Chilean menu before deployment.
            connection.executemany(
                "UPDATE products SET name = ?, description = ?, price_cents = ? WHERE id = ?",
                [(item[0], item[1], item[2], index) for index, item in enumerate(SEED_PRODUCTS, 1)],
            )


def menu_payload(connection):
    rows = connection.execute(
        """SELECT p.id, p.name, p.description, p.price_cents, p.emoji, p.vegetarian,
                  c.id AS category_id, c.name AS category
           FROM products p JOIN categories c ON c.id = p.category_id
           WHERE p.available = 1 AND c.active = 1
           ORDER BY c.sort_order, p.id"""
    ).fetchall()
    categories = connection.execute(
        "SELECT id, name FROM categories WHERE active = 1 ORDER BY sort_order, id"
    ).fetchall()
    return {
        "categories": [dict(row) for row in categories],
        "products": [dict(row) for row in rows],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 1_000_000:
            raise ValueError("El pedido es demasiado grande")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self.send_json(200, {"status": "ok"})
            return
        if path == "/api/menu":
            with db() as connection:
                self.send_json(200, menu_payload(connection))
            return
        if path == "/api/orders":
            with db() as connection:
                orders = connection.execute(
                    "SELECT id, customer_name, table_number, notes, status, total_cents, created_at FROM orders ORDER BY id DESC"
                ).fetchall()
                self.send_json(200, {"orders": [dict(row) for row in orders]})
            return
        if path.startswith("/api/orders/"):
            order_id = path.rsplit("/", 1)[-1]
            with db() as connection:
                order = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
                if not order:
                    self.send_json(404, {"error": "Pedido no encontrado"})
                    return
                items = connection.execute(
                    "SELECT product_id, product_name, unit_price_cents, quantity, subtotal_cents FROM order_items WHERE order_id = ?",
                    (order_id,),
                ).fetchall()
                self.send_json(200, {"order": dict(order), "items": [dict(row) for row in items]})
            return
        if path == "/" or path == "/index.html":
            self.serve_file("index.html", "text/html; charset=utf-8")
            return
        if path == "/qr" or path == "/qr.html":
            self.serve_file("qr.html", "text/html; charset=utf-8")
            return
        if path in ("/styles.css", "/script.js"):
            self.serve_file(path[1:], "text/css; charset=utf-8" if path.endswith("css") else "text/javascript; charset=utf-8")
            return
        self.send_json(404, {"error": "Recurso no encontrado"})

    def serve_file(self, filename, content_type):
        file_path = ROOT / filename
        if not file_path.is_file():
            self.send_json(404, {"error": "Archivo no encontrado"})
            return
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if urlparse(self.path).path != "/api/orders":
            self.send_json(404, {"error": "Recurso no encontrado"})
            return
        try:
            data = self.read_json()
            customer_name = str(data.get("customer_name", "")).strip()
            table_number = str(data.get("table_number", "")).strip()[:30]
            notes = str(data.get("notes", "")).strip()[:500]
            incoming_items = data.get("items", [])
            if not customer_name or len(customer_name) > 100:
                raise ValueError("Ingresá un nombre válido")
            if not isinstance(incoming_items, list) or not incoming_items:
                raise ValueError("El pedido debe tener al menos un producto")
            quantities = {}
            for item in incoming_items:
                product_id = int(item["product_id"])
                quantity = int(item["quantity"])
                if quantity < 1 or quantity > 50:
                    raise ValueError("La cantidad de un producto no es válida")
                quantities[product_id] = quantities.get(product_id, 0) + quantity
            with db() as connection:
                placeholders = ",".join("?" for _ in quantities)
                products = connection.execute(
                    f"""SELECT id, name, price_cents FROM products
                        WHERE available = 1 AND id IN ({placeholders})""",
                    tuple(quantities),
                ).fetchall()
                if len(products) != len(quantities):
                    raise ValueError("Uno de los productos ya no está disponible")
                total = sum(row["price_cents"] * quantities[row["id"]] for row in products)
                created_at = datetime.now(timezone.utc).isoformat()
                cursor = connection.execute(
                    "INSERT INTO orders (customer_name, table_number, notes, total_cents, created_at) VALUES (?, ?, ?, ?, ?)",
                    (customer_name, table_number, notes, total, created_at),
                )
                order_id = cursor.lastrowid
                connection.executemany(
                    """INSERT INTO order_items
                    (order_id, product_id, product_name, unit_price_cents, quantity, subtotal_cents)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    [
                        (order_id, row["id"], row["name"], row["price_cents"], quantities[row["id"]], row["price_cents"] * quantities[row["id"]])
                        for row in products
                    ],
                )
            self.send_json(201, {"order_id": order_id, "status": "pending", "total_cents": total})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except sqlite3.Error:
            self.send_json(500, {"error": "No se pudo guardar el pedido"})

    def do_PATCH(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/orders/"):
            self.send_json(404, {"error": "Recurso no encontrado"})
            return
        try:
            order_id = int(path.rsplit("/", 1)[-1])
            status = self.read_json().get("status")
            valid_statuses = {"pending", "confirmed", "preparing", "ready", "delivered", "cancelled"}
            if status not in valid_statuses:
                raise ValueError("Estado de pedido no válido")
            with db() as connection:
                cursor = connection.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
                if cursor.rowcount == 0:
                    self.send_json(404, {"error": "Pedido no encontrado"})
                    return
            self.send_json(200, {"order_id": order_id, "status": status})
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})


if __name__ == "__main__":
    init_db()
    host = os.environ.get("MENU_HOST", "0.0.0.0")
    port = int(os.environ.get("MENU_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Menú disponible en http://localhost:{port}")
    print("Para celulares en la misma red, usar la IP local de esta computadora, por ejemplo:")
    print(f"  http://192.168.1.7:{port}")
    print(f"Base de datos: {DB_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido")
        server.server_close()
