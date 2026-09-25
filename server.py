#!/usr/bin/env python3
import json
import os
import secrets
import hmac
import hashlib
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "menu.db"
ANGULAR_DIST = ROOT / "angular-app" / "dist" / "frontend" / "browser"
TABLE_SECRET = os.environ.get("MENU_SECRET", "smach-grill-local-secret").encode()


def table_token(table_number):
    return hmac.new(TABLE_SECRET, f"mesa-{table_number}".encode(), hashlib.sha256).hexdigest()[:24]


def valid_table_token(table_number, token):
    return table_number in range(1, 7) and hmac.compare_digest(token or "", table_token(table_number))

SEED_CATEGORIES = [
    ("Hamburguesas", 1),
    ("Combos", 2),
    ("Papas y acompañamientos", 3),
    ("Bebidas", 4),
    ("Postres", 5),
]
SEED_PRODUCTS = [
    ("La Clásica", "Carne a la parrilla, queso cheddar, lechuga, tomate y salsa de la casa.", 699000, "🍔", "burger", 1, 0, 1),
    ("Doble Smash", "Doble carne smash, doble cheddar, pepinillos y salsa especial.", 899000, "🍔", "burger", 1, 0, 1),
    ("La BBQ", "Carne a la parrilla, cheddar, tocino crocante, cebolla crispy y BBQ.", 849000, "🍔", "burger", 1, 0, 1),
    ("Veggie Grill", "Hamburguesa vegetal, cheddar, palta, tomate y mayonesa de ajo.", 749000, "🍔", "burger", 1, 1, 1),
    ("Combo Clásico", "La Clásica con papas fritas y bebida en lata.", 949000, "🍔", "combo", 2, 0, 1),
    ("Combo Doble Smash", "Doble Smash con papas fritas y bebida en lata.", 1149000, "🍔", "combo", 2, 0, 1),
    ("Papas clásicas", "Papas fritas doradas con sal de la casa.", 399000, "🍟", "fries", 3, 1, 1),
    ("Papas cheddar y tocino", "Papas fritas con cheddar fundido, tocino y ciboulette.", 599000, "🍟", "fries", 3, 0, 1),
    ("Bebida en lata", "Elige entre Coca-Cola, Sprite o Fanta.", 199000, "🥤", "drink", 4, 1, 1),
    ("Limonada de la casa", "Limón natural, menta y hielo.", 299000, "🍋", "drink", 4, 1, 1),
    ("Brownie con helado", "Brownie de chocolate tibio con helado de vainilla.", 499000, "🍫", "dessert", 5, 1, 1),
    ("Milkshake de vainilla", "Batido cremoso de vainilla con crema.", 449000, "🥤", "dessert", 5, 1, 1),
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
                image TEXT NOT NULL DEFAULT 'burger',
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
                payment_method TEXT NOT NULL DEFAULT 'cash'
                    CHECK (payment_method IN ('cash', 'card', 'transfer')),
                payment_status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (payment_status IN ('pending', 'approved', 'declined')),
                transaction_ref TEXT,
                estimated_minutes INTEGER NOT NULL DEFAULT 20,
                access_token TEXT,
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
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(orders)")}
        if "payment_method" not in columns:
            connection.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'cash'")
        if "payment_status" not in columns:
            connection.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'pending'")
        if "transaction_ref" not in columns:
            connection.execute("ALTER TABLE orders ADD COLUMN transaction_ref TEXT")
        if "estimated_minutes" not in columns:
            connection.execute("ALTER TABLE orders ADD COLUMN estimated_minutes INTEGER NOT NULL DEFAULT 20")
        if "access_token" not in columns:
            connection.execute("ALTER TABLE orders ADD COLUMN access_token TEXT")
        product_columns = {row["name"] for row in connection.execute("PRAGMA table_info(products)")}
        if "image" not in product_columns:
            connection.execute("ALTER TABLE products ADD COLUMN image TEXT NOT NULL DEFAULT 'burger'")
        if connection.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            connection.executemany("INSERT INTO categories (name, sort_order) VALUES (?, ?)", SEED_CATEGORIES)
        if connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            connection.executemany(
                """INSERT INTO products
                (name, description, price_cents, emoji, image, category_id, vegetarian, available)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                SEED_PRODUCTS,
            )
        else:
            connection.execute("UPDATE categories SET name = '__migrating_' || id")
            connection.executemany(
                "UPDATE categories SET name = ?, sort_order = ?, active = 1 WHERE id = ?",
                [(item[0], item[1], index) for index, item in enumerate(SEED_CATEGORIES, 1)],
            )
            connection.executemany(
                """UPDATE products SET name = ?, description = ?, price_cents = ?, emoji = ?,
                   image = ?, category_id = ?, vegetarian = ?, available = ? WHERE id = ?""",
                [(*item, index) for index, item in enumerate(SEED_PRODUCTS, 1)],
            )


def menu_payload(connection):
    rows = connection.execute(
        """SELECT p.id, p.name, p.description, p.price_cents, p.emoji, p.image, p.vegetarian,
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
        if path == "/api/tables":
            origin = f"{self.headers.get('X-Forwarded-Proto', 'http')}://{self.headers.get('Host', 'localhost:8000')}"
            self.send_json(200, {"tables": [{"number": number, "url": f"{origin}/?mesa={number}&token={table_token(number)}"} for number in range(1, 7)]})
            return
        if path == "/api/orders":
            with db() as connection:
                orders = connection.execute(
                    "SELECT id, customer_name, table_number, notes, status, total_cents, payment_method, payment_status, transaction_ref, created_at FROM orders ORDER BY id DESC"
                ).fetchall()
                self.send_json(200, {"orders": [dict(row) for row in orders]})
            return
        if path.startswith("/api/orders/"):
            order_id = path.rsplit("/", 1)[-1]
            access = parse_qs(urlparse(self.path).query).get("access", [None])[0]
            with db() as connection:
                order = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
                if not order:
                    self.send_json(404, {"error": "Pedido no encontrado"})
                    return
                if access is not None and not hmac.compare_digest(access, order["access_token"] or ""):
                    self.send_json(403, {"error": "No tenés acceso a este pedido"})
                    return
                items = connection.execute(
                    "SELECT product_id, product_name, unit_price_cents, quantity, subtotal_cents FROM order_items WHERE order_id = ?",
                    (order_id,),
                ).fetchall()
                self.send_json(200, {"order": dict(order), "items": [dict(row) for row in items]})
            return
        if path == "/" or path == "/index.html":
            if (ANGULAR_DIST / "index.html").is_file():
                self.serve_path(ANGULAR_DIST / "index.html", "text/html; charset=utf-8")
            else:
                self.serve_file("index.html", "text/html; charset=utf-8")
            return
        angular_asset = ANGULAR_DIST / path.lstrip("/")
        if ANGULAR_DIST.is_dir() and angular_asset.is_file():
            content_types = {
                ".css": "text/css; charset=utf-8",
                ".svg": "image/svg+xml",
                ".jpeg": "image/jpeg",
                ".jpg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
            }
            content_type = content_types.get(angular_asset.suffix, "text/javascript; charset=utf-8")
            self.serve_path(angular_asset, content_type)
            return
        if path == "/qr" or path == "/qr.html":
            self.serve_file("qr.html", "text/html; charset=utf-8")
            return
        if path == "/admin" or path == "/admin.html":
            self.serve_file("admin.html", "text/html; charset=utf-8")
            return
        if path == "/admin.js":
            self.serve_file("admin.js", "text/javascript; charset=utf-8")
            return
        if path in ("/styles.css", "/script.js"):
            self.serve_file(path[1:], "text/css; charset=utf-8" if path.endswith("css") else "text/javascript; charset=utf-8")
            return
        self.send_json(404, {"error": "Recurso no encontrado"})

    def serve_file(self, filename, content_type):
        file_path = ROOT / filename
        self.serve_path(file_path, content_type)

    def serve_path(self, file_path, content_type):
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
            table_number = str(data.get("table_number", "")).strip()
            submitted_table = int(table_number) if table_number.isdigit() else 0
            if not valid_table_token(submitted_table, str(data.get("table_token", "")).strip()):
                raise ValueError("Escaneá el QR correspondiente a tu mesa")
            table_number = f"Mesa {submitted_table}"
            notes = str(data.get("notes", "")).strip()[:500]
            payment_method = str(data.get("payment_method", "cash")).strip()
            payment_token = str(data.get("payment_token", "")).strip()
            incoming_items = data.get("items", [])
            if not customer_name or len(customer_name) > 100:
                raise ValueError("Ingresá un nombre válido")
            if not isinstance(incoming_items, list) or not incoming_items:
                raise ValueError("El pedido debe tener al menos un producto")
            if payment_method not in {"cash", "card", "transfer"}:
                raise ValueError("Método de pago no válido")
            if payment_method == "card" and len(payment_token) < 4:
                raise ValueError("Ingresá una tarjeta de prueba válida")
            if payment_method == "transfer" and not payment_token:
                raise ValueError("Ingresá el comprobante de transferencia de prueba")
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
                estimated_minutes = min(55, max(15, 12 + sum(quantities.values()) * 3))
                access_token = secrets.token_urlsafe(24)
                payment_status = "approved"
                transaction_ref = f"SIM-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{connection.total_changes + 1}"
                if payment_method == "card" and payment_token.endswith("0002"):
                    payment_status = "declined"
                    raise ValueError("Pago simulado rechazado. Usá una tarjeta terminada en 4242.")
                cursor = connection.execute(
                    """INSERT INTO orders
                    (customer_name, table_number, notes, total_cents, payment_method, payment_status, transaction_ref, estimated_minutes, access_token, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (customer_name, table_number, notes, total, payment_method, payment_status, transaction_ref, estimated_minutes, access_token, created_at),
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
            self.send_json(201, {"order_id": order_id, "access_token": access_token, "status": "pending", "payment_status": payment_status, "transaction_ref": transaction_ref, "estimated_minutes": estimated_minutes, "total_cents": total})
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
    port = int(os.environ.get("PORT", os.environ.get("MENU_PORT", "8000")))
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
