import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import quote_plus

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    send_from_directory,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    secrets.token_hex(32)
)

DB_PATH = os.environ.get("DB_PATH", "staik_salon.db")

OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "admin")
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "change-me-now")

GOOGLE_VERIFICATION_FILE = "googledb5e95e36a911af6.html"

@app.get(f"/{GOOGLE_VERIFICATION_FILE}")
def google_verification():
    return send_from_directory(app.static_folder, GOOGLE_VERIFICATION_FILE)

# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            price INTEGER NOT NULL DEFAULT 0,
            duration INTEGER NOT NULL DEFAULT 30,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            service_id INTEGER NOT NULL,
            booking_date TEXT NOT NULL,
            booking_time TEXT NOT NULL,
            notes TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(service_id) REFERENCES services(id)
        );

        CREATE TABLE IF NOT EXISTS owner (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            can_manage_services INTEGER NOT NULL DEFAULT 1,
            can_manage_bookings INTEGER NOT NULL DEFAULT 1,
            can_manage_promotions INTEGER NOT NULL DEFAULT 1,
            can_manage_account INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS promotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            discount TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            price INTEGER NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 0,
            image_url TEXT DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT DEFAULT '',
            pincode TEXT DEFAULT '',
            total INTEGER NOT NULL DEFAULT 0,
            payment_method TEXT NOT NULL DEFAULT 'COD',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS unique_active_booking
        ON bookings(booking_date, booking_time, service_id)
        WHERE status IN ('pending', 'confirmed');
        """
    )

    # Default owner
    existing_owner = db.execute(
        "SELECT id FROM owner WHERE id = 1"
    ).fetchone()

    if not existing_owner:
        db.execute(
            """
            INSERT INTO owner
            (
                id,
                username,
                password_hash,
                can_manage_services,
                can_manage_bookings,
                can_manage_promotions,
                can_manage_account
            )
            VALUES (?, ?, ?, 1, 1, 1, 1)
            """,
            (
                1,
                OWNER_USERNAME,
                generate_password_hash(OWNER_PASSWORD),
            ),
        )

    # Default shop products
    product_count = db.execute(
        "SELECT COUNT(*) AS count FROM products"
    ).fetchone()["count"]

    if product_count == 0:
        products = [
            ("Premium Hair Serum", "Lightweight serum for smooth, shiny hair.", 399, 20, "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=700&q=80"),
            ("Salon Hair Wax", "Easy styling wax for everyday looks.", 299, 25, "https://images.unsplash.com/photo-1598524374912-6b0b0bab0c6a?auto=format&fit=crop&w=700&q=80"),
            ("Face Cleanser", "Gentle cleanser for a fresh salon-style finish.", 349, 18, "https://images.unsplash.com/photo-1556228578-8c89e6adf883?auto=format&fit=crop&w=700&q=80"),
            ("Hair Spa Cream", "Nourishing hair spa cream for home care.", 499, 15, "https://images.unsplash.com/photo-1559599101-f09722fb4948?auto=format&fit=crop&w=700&q=80"),
        ]
        db.executemany(
            """
            INSERT INTO products (name, description, price, stock, image_url)
            VALUES (?, ?, ?, ?, ?)
            """,
            products,
        )

    # Default salon settings
    default_settings = {
        "salon_name": "Staik Salon",
        "address": "Bhopal, Madhya Pradesh, India",
        "phone": "",
        "opening_hours": "10:00 AM - 08:00 PM",
        "about": "Professional salon services with easy online booking.",
    }

    for key, value in default_settings.items():
        db.execute(
            """
            INSERT OR IGNORE INTO settings (key, value)
            VALUES (?, ?)
            """,
            (key, value),
        )

    # Default services
    service_count = db.execute(
        "SELECT COUNT(*) AS count FROM services"
    ).fetchone()["count"]

    if service_count == 0:
        services = [
            (
                "Haircut",
                "Professional haircut",
                200,
                45,
            ),
            (
                "Hair Styling",
                "Modern hair styling",
                300,
                60,
            ),
            (
                "Hair Spa",
                "Relaxing hair spa treatment",
                600,
                60,
            ),
            (
                "Facial",
                "Professional facial treatment",
                500,
                60,
            ),
        ]

        db.executemany(
            """
            INSERT INTO services
            (name, description, price, duration)
            VALUES (?, ?, ?, ?)
            """,
            services,
        )

    db.commit()


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def get_setting(key, default=""):
    row = get_db().execute(
        "SELECT value FROM settings WHERE key = ?",
        (key,),
    ).fetchone()

    return row["value"] if row else default


def set_setting(key, value):
    db = get_db()

    db.execute(
        """
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )

    db.commit()


def owner_required(permission=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("owner_id"):
                return redirect(url_for("owner_login"))

            if permission:
                owner = get_db().execute(
                    "SELECT * FROM owner WHERE id = 1"
                ).fetchone()

                if not owner or not owner[permission]:
                    abort(403)

            return view(*args, **kwargs)

        return wrapped

    return decorator


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)

    return session["csrf_token"]


def validate_csrf():
    token = request.form.get("csrf_token", "")

    if not token or token != session.get("csrf_token"):
        abort(400, description="Invalid CSRF token.")


@app.context_processor
def inject_globals():
    cart = session.get("cart", {})
    cart_count = sum(int(q) for q in cart.values()) if isinstance(cart, dict) else 0

    return {
        "csrf_token": csrf_token,
        "salon_name": get_setting("salon_name", "Staik Salon"),
        "salon_phone": get_setting("phone", ""),
        "cart_count": cart_count,
    }


@app.template_filter("money")
def money_filter(value):
    try:
        return f"₹{int(value):,}"
    except (ValueError, TypeError):
        return value


# ---------------------------------------------------------
# PUBLIC WEBSITE
# ---------------------------------------------------------

@app.route("/")
def home():
    db = get_db()

    services = db.execute(
        """
        SELECT *
        FROM services
        WHERE active = 1
        ORDER BY id DESC
        """
    ).fetchall()

    promotions = db.execute(
        """
        SELECT *
        FROM promotions
        WHERE active = 1
        ORDER BY id DESC
        """
    ).fetchall()

    return render_template(
        "index.html",
        services=services,
        promotions=promotions,
        address=get_setting("address"),
        phone=get_setting("phone"),
        opening_hours=get_setting("opening_hours"),
        about=get_setting("about"),
    )


# ---------------------------------------------------------
# AVAILABLE SLOTS
# ---------------------------------------------------------

@app.route("/slots")
def slots():
    booking_date = request.args.get("date", "").strip()
    service_id = request.args.get("service_id", "").strip()

    if not booking_date:
        return jsonify({"slots": []})

    try:
        datetime.strptime(booking_date, "%Y-%m-%d")
    except ValueError:
        return jsonify({"slots": []})

    db = get_db()

    if service_id:
        try:
            service_id_int = int(service_id)
        except ValueError:
            return jsonify({"slots": []})

        booked_rows = db.execute(
            """
            SELECT booking_time
            FROM bookings
            WHERE booking_date = ?
            AND service_id = ?
            AND status IN ('pending', 'confirmed')
            """,
            (booking_date, service_id_int),
        ).fetchall()
    else:
        booked_rows = db.execute(
            """
            SELECT booking_time
            FROM bookings
            WHERE booking_date = ?
            AND status IN ('pending', 'confirmed')
            """,
            (booking_date,),
        ).fetchall()

    booked = {row["booking_time"] for row in booked_rows}

    slots_list = []

    start = datetime.strptime("10:00", "%H:%M")
    end = datetime.strptime("20:00", "%H:%M")

    current = start

    while current < end:
        time_value = current.strftime("%H:%M")

        if time_value not in booked:
            slots_list.append(time_value)

        current += timedelta(minutes=30)

    return jsonify({"slots": slots_list})


# ---------------------------------------------------------
# BOOKING
# ---------------------------------------------------------

@app.route("/book", methods=["POST"])
def book():
    validate_csrf()

    customer_name = request.form.get("customer_name", "").strip()
    phone = request.form.get("phone", "").strip()
    service_id = request.form.get("service_id", "").strip()
    booking_date = request.form.get("booking_date", "").strip()
    booking_time = request.form.get("booking_time", "").strip()
    notes = request.form.get("notes", "").strip()

    if not all(
        [
            customer_name,
            phone,
            service_id,
            booking_date,
            booking_time,
        ]
    ):
        flash("Please fill all required fields.", "error")
        return redirect(url_for("home") + "#booking")

    try:
        service_id_int = int(service_id)
    except ValueError:
        flash("Invalid service selected.", "error")
        return redirect(url_for("home") + "#booking")

    try:
        selected_date = datetime.strptime(
            booking_date,
            "%Y-%m-%d"
        ).date()

        selected_time = datetime.strptime(
            booking_time,
            "%H:%M"
        ).time()

    except ValueError:
        flash("Invalid date or time.", "error")
        return redirect(url_for("home") + "#booking")

    if selected_date < datetime.now().date():
        flash("Please select a future date.", "error")
        return redirect(url_for("home") + "#booking")

    db = get_db()

    service = db.execute(
        """
        SELECT *
        FROM services
        WHERE id = ?
        AND active = 1
        """,
        (service_id_int,),
    ).fetchone()

    if not service:
        flash("Selected service is not available.", "error")
        return redirect(url_for("home") + "#booking")

    if selected_time < datetime.strptime("10:00", "%H:%M").time():
        flash("Salon opens at 10:00 AM.", "error")
        return redirect(url_for("home") + "#booking")

    if selected_time >= datetime.strptime("20:00", "%H:%M").time():
        flash("Last available time is before 8:00 PM.", "error")
        return redirect(url_for("home") + "#booking")

    existing = db.execute(
        """
        SELECT id
        FROM bookings
        WHERE booking_date = ?
        AND booking_time = ?
        AND service_id = ?
        AND status IN ('pending', 'confirmed')
        """,
        (
            booking_date,
            booking_time,
            service_id_int,
        ),
    ).fetchone()

    if existing:
        flash(
            "This slot is already booked. Please select another slot.",
            "error",
        )
        return redirect(url_for("home") + "#booking")

    try:
        cursor = db.execute(
            """
            INSERT INTO bookings
            (
                customer_name,
                phone,
                service_id,
                booking_date,
                booking_time,
                notes,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                customer_name,
                phone,
                service_id_int,
                booking_date,
                booking_time,
                notes,
            ),
        )

        db.commit()

    except sqlite3.IntegrityError:
        db.rollback()

        flash(
            "That slot was just booked by someone else. Please choose another.",
            "error",
        )

        return redirect(url_for("home") + "#booking")

    return redirect(
        url_for(
            "booking_success",
            booking_id=cursor.lastrowid,
        )
    )


@app.route("/booking/<int:booking_id>/success")
def booking_success(booking_id):
    booking = get_db().execute(
        """
        SELECT
            bookings.*,
            services.name AS service_name,
            services.price,
            services.duration
        FROM bookings
        JOIN services ON services.id = bookings.service_id
        WHERE bookings.id = ?
        """,
        (booking_id,),
    ).fetchone()

    if not booking:
        abort(404)

    return render_template(
        "success.html",
        booking=booking,
    )


# ---------------------------------------------------------
# SHOP / CART / ORDERS
# ---------------------------------------------------------

def cart_items():
    raw_cart = session.get("cart", {})
    if not isinstance(raw_cart, dict):
        raw_cart = {}

    db = get_db()
    items = []
    total = 0
    cleaned = {}

    for product_id, quantity in raw_cart.items():
        try:
            pid = int(product_id)
            qty = int(quantity)
        except (TypeError, ValueError):
            continue

        if qty <= 0:
            continue

        product = db.execute(
            "SELECT * FROM products WHERE id = ? AND active = 1",
            (pid,),
        ).fetchone()
        if not product:
            continue

        qty = min(qty, max(product["stock"], 0))
        if qty <= 0:
            continue

        cleaned[str(pid)] = qty
        line_total = product["price"] * qty
        total += line_total
        items.append({"product": product, "quantity": qty, "line_total": line_total})

    if cleaned != raw_cart:
        session["cart"] = cleaned

    return items, total


@app.get("/shop")
def shop():
    products = get_db().execute(
        "SELECT * FROM products WHERE active = 1 AND stock > 0 ORDER BY id DESC"
    ).fetchall()
    return render_template("shop.html", products=products)


@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    validate_csrf()
    db = get_db()
    product = db.execute(
        "SELECT * FROM products WHERE id = ? AND active = 1",
        (product_id,),
    ).fetchone()
    if not product:
        abort(404)
    if product["stock"] <= 0:
        flash("This product is out of stock.", "error")
        return redirect(url_for("shop"))

    try:
        quantity = max(1, min(int(request.form.get("quantity", "1")), 10))
    except ValueError:
        quantity = 1

    cart = session.get("cart", {})
    if not isinstance(cart, dict):
        cart = {}
    current = int(cart.get(str(product_id), 0))
    cart[str(product_id)] = min(current + quantity, product["stock"], 10)
    session["cart"] = cart
    flash(f"{product['name']} added to cart.", "success")
    return redirect(request.form.get("next") or url_for("shop"))


@app.get("/cart")
def cart():
    items, total = cart_items()
    return render_template("cart.html", items=items, total=total)


@app.post("/cart/update")
def update_cart():
    validate_csrf()
    cart_data = {}
    db = get_db()
    for key, value in request.form.items():
        if not key.startswith("qty_"):
            continue
        try:
            pid = int(key[4:])
            qty = int(value)
        except ValueError:
            continue
        product = db.execute(
            "SELECT stock FROM products WHERE id = ? AND active = 1",
            (pid,),
        ).fetchone()
        if product and qty > 0:
            cart_data[str(pid)] = min(qty, product["stock"], 10)
    session["cart"] = cart_data
    flash("Cart updated.", "success")
    return redirect(url_for("cart"))


@app.post("/cart/remove/<int:product_id>")
def remove_from_cart(product_id):
    validate_csrf()
    cart = session.get("cart", {})
    if isinstance(cart, dict):
        cart.pop(str(product_id), None)
        session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    items, total = cart_items()
    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("shop"))

    if request.method == "POST":
        validate_csrf()
        customer_name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        pincode = request.form.get("pincode", "").strip()

        if not customer_name or not phone or not address or not city or not pincode:
            flash("Please fill all delivery details.", "error")
            return render_template("checkout.html", items=items, total=total)

        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            verified = []
            final_total = 0
            for item in items:
                product = db.execute(
                    "SELECT * FROM products WHERE id = ? AND active = 1",
                    (item["product"]["id"],),
                ).fetchone()
                if not product or product["stock"] < item["quantity"]:
                    raise ValueError(f"{item['product']['name']} is no longer available in the requested quantity.")
                line_total = product["price"] * item["quantity"]
                final_total += line_total
                verified.append((product, item["quantity"], line_total))

            cur = db.execute(
                """INSERT INTO orders (customer_name, phone, address, city, pincode, total, payment_method, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'COD', 'pending')""",
                (customer_name, phone, address, city, pincode, final_total),
            )
            order_id = cur.lastrowid

            for product, qty, line_total in verified:
                db.execute(
                    """INSERT INTO order_items (order_id, product_id, product_name, price, quantity)
                       VALUES (?, ?, ?, ?, ?)""",
                    (order_id, product["id"], product["name"], product["price"], qty),
                )
                db.execute(
                    "UPDATE products SET stock = stock - ? WHERE id = ?",
                    (qty, product["id"]),
                )

            db.commit()
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "error")
            return redirect(url_for("cart"))
        except sqlite3.Error:
            db.rollback()
            flash("Could not place the order. Please try again.", "error")
            return redirect(url_for("cart"))

        session["cart"] = {}
        session["last_order_id"] = order_id
        return redirect(url_for("order_success", order_id=order_id))

    return render_template("checkout.html", items=items, total=total)


@app.get("/order/<int:order_id>")
def order_success(order_id):
    if session.get("last_order_id") != order_id:
        return redirect(url_for("track_order", order_id=order_id))
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    items = db.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)).fetchall()
    if not order:
        abort(404)
    return render_template("order_success.html", order=order, items=items)


@app.route("/orders", methods=["GET", "POST"])
def track_order():
    order = None
    items = []
    searched = False
    if request.method == "POST":
        validate_csrf()
        order_id = request.form.get("order_id", "").strip()
        phone = request.form.get("phone", "").strip()
        searched = True
        if order_id.isdigit() and phone:
            order = get_db().execute(
                "SELECT * FROM orders WHERE id = ? AND phone = ?",
                (int(order_id), phone),
            ).fetchone()
            if order:
                items = get_db().execute(
                    "SELECT * FROM order_items WHERE order_id = ? ORDER BY id",
                    (order["id"],),
                ).fetchall()
        if not order:
            flash("Order not found. Check your order ID and phone number.", "error")
    return render_template("orders.html", order=order, items=items, searched=searched)


# ---------------------------------------------------------
# OWNER SHOP MANAGEMENT
# ---------------------------------------------------------

@app.get("/owner/products")
@owner_required("can_manage_services")
def owner_products():
    products = get_db().execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template("owner_products.html", products=products)


@app.post("/owner/product/add")
@owner_required("can_manage_services")
def add_product():
    validate_csrf()
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    image_url = request.form.get("image_url", "").strip()
    try:
        price = int(request.form.get("price", "0"))
        stock = int(request.form.get("stock", "0"))
        if price < 0 or stock < 0:
            raise ValueError
    except ValueError:
        flash("Price or stock is invalid.", "error")
        return redirect(url_for("owner_products"))
    if not name:
        flash("Product name is required.", "error")
        return redirect(url_for("owner_products"))
    db = get_db()
    db.execute("INSERT INTO products (name, description, price, stock, image_url) VALUES (?, ?, ?, ?, ?)", (name, description, price, stock, image_url))
    db.commit()
    flash("Product added successfully.", "success")
    return redirect(url_for("owner_products"))


@app.post("/owner/product/<int:product_id>/update")
@owner_required("can_manage_services")
def update_product(product_id):
    validate_csrf()
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    image_url = request.form.get("image_url", "").strip()
    try:
        price = int(request.form.get("price", "0"))
        stock = int(request.form.get("stock", "0"))
        if price < 0 or stock < 0 or not name:
            raise ValueError
    except ValueError:
        flash("Please enter valid product details.", "error")
        return redirect(url_for("owner_products"))
    db = get_db()
    if not db.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone():
        abort(404)
    db.execute("UPDATE products SET name=?, description=?, price=?, stock=?, image_url=? WHERE id=?", (name, description, price, stock, image_url, product_id))
    db.commit()
    flash("Product updated.", "success")
    return redirect(url_for("owner_products"))


@app.post("/owner/product/<int:product_id>/toggle")
@owner_required("can_manage_services")
def toggle_product(product_id):
    validate_csrf()
    db = get_db()
    product = db.execute("SELECT active FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        abort(404)
    db.execute("UPDATE products SET active = ? WHERE id = ?", (0 if product["active"] else 1, product_id))
    db.commit()
    flash("Product visibility updated.", "success")
    return redirect(url_for("owner_products"))


@app.post("/owner/product/<int:product_id>/delete")
@owner_required("can_manage_services")
def delete_product(product_id):
    validate_csrf()
    db = get_db()
    db.execute("UPDATE products SET active = 0 WHERE id = ?", (product_id,))
    db.commit()
    flash("Product hidden from shop.", "success")
    return redirect(url_for("owner_products"))


@app.get("/owner/orders")
@owner_required("can_manage_bookings")
def owner_orders():
    db = get_db()
    orders = db.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    order_items = {}
    for order in orders:
        order_items[order["id"]] = db.execute(
            "SELECT * FROM order_items WHERE order_id = ? ORDER BY id",
            (order["id"],),
        ).fetchall()
    return render_template("owner_orders.html", orders=orders, order_items=order_items)


@app.post("/owner/order/<int:order_id>/status")
@owner_required("can_manage_bookings")
def update_order_status(order_id):
    validate_csrf()
    status = request.form.get("status", "").strip().lower()
    allowed = {"pending", "confirmed", "processing", "shipped", "delivered", "cancelled"}
    if status not in allowed:
        abort(400, description="Invalid order status.")
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        abort(404)
    db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    db.commit()
    flash("Order status updated.", "success")
    return redirect(url_for("owner_orders"))


# ---------------------------------------------------------
# OWNER LOGIN
# ---------------------------------------------------------

@app.route("/owner/login", methods=["GET", "POST"])
def owner_login():
    if session.get("owner_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        validate_csrf()

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        owner = get_db().execute(
            """
            SELECT *
            FROM owner
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        if owner and check_password_hash(
            owner["password_hash"],
            password,
        ):
            session.clear()

            session["owner_id"] = owner["id"]
            session["owner_username"] = owner["username"]
            session["csrf_token"] = secrets.token_urlsafe(32)

            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/owner/logout")
def owner_logout():
    session.clear()
    return redirect(url_for("home"))


# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------

@app.route("/owner")
@owner_required()
def dashboard():
    db = get_db()

    stats = {
        "total": db.execute(
            "SELECT COUNT(*) AS c FROM bookings"
        ).fetchone()["c"],

        "pending": db.execute(
            """
            SELECT COUNT(*) AS c
            FROM bookings
            WHERE status = 'pending'
            """
        ).fetchone()["c"],

        "confirmed": db.execute(
            """
            SELECT COUNT(*) AS c
            FROM bookings
            WHERE status = 'confirmed'
            """
        ).fetchone()["c"],

        "cancelled": db.execute(
            """
            SELECT COUNT(*) AS c
            FROM bookings
            WHERE status = 'cancelled'
            """
        ).fetchone()["c"],

        "orders": db.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"],
        "pending_orders": db.execute("SELECT COUNT(*) AS c FROM orders WHERE status = 'pending'").fetchone()["c"],
    }

    bookings = db.execute(
        """
        SELECT
            bookings.*,
            services.name AS service_name,
            services.price
        FROM bookings
        JOIN services ON services.id = bookings.service_id
        ORDER BY
            booking_date DESC,
            booking_time DESC,
            bookings.id DESC
        """
    ).fetchall()

    services = db.execute(
        """
        SELECT *
        FROM services
        ORDER BY id DESC
        """
    ).fetchall()

    promotions = db.execute(
        """
        SELECT *
        FROM promotions
        ORDER BY id DESC
        """
    ).fetchall()

    owner = db.execute(
        "SELECT * FROM owner WHERE id = 1"
    ).fetchone()

    return render_template(
        "dashboard.html",
        stats=stats,
        bookings=bookings,
        services=services,
        promotions=promotions,
        owner=owner,
        address=get_setting("address"),
        phone=get_setting("phone"),
        opening_hours=get_setting("opening_hours"),
        about=get_setting("about"),
    )


# ---------------------------------------------------------
# BOOKING MANAGEMENT
# ---------------------------------------------------------

@app.get("/owner/booking/<int:booking_id>/confirm")
@owner_required("can_manage_bookings")
def confirm_booking_page(booking_id):
    db = get_db()

    booking = db.execute(
        """
        SELECT bookings.*, services.name AS service_name
        FROM bookings
        LEFT JOIN services ON services.id = bookings.service_id
        WHERE bookings.id = ?
        """,
        (booking_id,),
    ).fetchone()

    if not booking:
        abort(404)

    return render_template("confirm.html", booking=booking)


@app.post("/owner/booking/<int:booking_id>/<action>")
@owner_required("can_manage_bookings")
def manage_booking(booking_id, action):
    validate_csrf()

    allowed = {"confirm": "confirmed", "cancel": "cancelled"}

    if action not in allowed:
        abort(404)

    db = get_db()

    booking = db.execute(
        """
        SELECT bookings.*, services.name AS service_name
        FROM bookings
        LEFT JOIN services ON services.id = bookings.service_id
        WHERE bookings.id = ?
        """,
        (booking_id,),
    ).fetchone()

    if not booking:
        abort(404)

    try:
        db.execute(
            "UPDATE bookings SET status = ? WHERE id = ?",
            (allowed[action], booking_id),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        flash("Unable to confirm booking because the slot is already occupied.", "error")
        return redirect(url_for("dashboard") + "#bookings")

    if action == "confirm":
        customer_name = booking["customer_name"]
        phone = "".join(ch for ch in str(booking["phone"]) if ch.isdigit())

        if len(phone) == 10:
            whatsapp_number = "91" + phone
        elif len(phone) == 12 and phone.startswith("91"):
            whatsapp_number = phone
        else:
            whatsapp_number = ""

        if whatsapp_number:
            salon_name = get_setting("salon_name", "Staik Salon")
            message = (
                f"Hello {customer_name},\n\n"
                f"🎉 Your booking at {salon_name} is confirmed.\n\n"
                f"Service: {booking['service_name'] or 'Salon Service'}\n"
                f"Date: {booking['booking_date']}\n"
                f"Time: {booking['booking_time']}\n\n"
                f"Thank you for choosing {salon_name}! 💇"
            )

            whatsapp_url = (
                "https://wa.me/" + whatsapp_number
                + "?text=" + quote_plus(message)
            )
            return redirect(whatsapp_url)

        flash("Booking confirmed, but the customer phone number is invalid.", "error")
    else:
        flash("Booking cancelled successfully.", "success")

    return redirect(url_for("dashboard") + "#bookings")


@app.post("/owner/booking/<int:booking_id>/delete")
@owner_required("can_manage_bookings")
def delete_booking(booking_id):
    validate_csrf()

    db = get_db()

    db.execute(
        "DELETE FROM bookings WHERE id = ?",
        (booking_id,),
    )

    db.commit()

    flash("Booking deleted.", "success")

    return redirect(url_for("dashboard") + "#bookings")


# ---------------------------------------------------------
# SERVICE MANAGEMENT
# ---------------------------------------------------------

@app.post("/owner/service/add")
@owner_required("can_manage_services")
def add_service():
    validate_csrf()

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    price = request.form.get("price", "0").strip()
    duration = request.form.get("duration", "30").strip()

    try:
        price_int = int(price)
        duration_int = int(duration)

        if price_int < 0 or duration_int <= 0:
            raise ValueError

    except ValueError:
        flash("Price or duration is invalid.", "error")
        return redirect(url_for("dashboard") + "#services")

    if not name:
        flash("Service name is required.", "error")
        return redirect(url_for("dashboard") + "#services")

    db = get_db()

    db.execute(
        """
        INSERT INTO services
        (name, description, price, duration)
        VALUES (?, ?, ?, ?)
        """,
        (
            name,
            description,
            price_int,
            duration_int,
        ),
    )

    db.commit()

    flash("Service added successfully.", "success")

    return redirect(url_for("dashboard") + "#services")


@app.post("/owner/service/<int:service_id>/delete")
@owner_required("can_manage_services")
def delete_service(service_id):
    validate_csrf()

    db = get_db()

    active_bookings = db.execute(
        """
        SELECT COUNT(*) AS c
        FROM bookings
        WHERE service_id = ?
        AND status IN ('pending', 'confirmed')
        """,
        (service_id,),
    ).fetchone()["c"]

    if active_bookings:
        flash(
            "This service has active bookings. Cancel those bookings first.",
            "error",
        )

        return redirect(url_for("dashboard") + "#services")

    db.execute(
        "DELETE FROM services WHERE id = ?",
        (service_id,),
    )

    db.commit()

    flash("Service deleted.", "success")

    return redirect(url_for("dashboard") + "#services")


@app.post("/owner/service/<int:service_id>/toggle")
@owner_required("can_manage_services")
def toggle_service(service_id):
    validate_csrf()

    db = get_db()

    service = db.execute(
        """
        SELECT active
        FROM services
        WHERE id = ?
        """,
        (service_id,),
    ).fetchone()

    if not service:
        abort(404)

    db.execute(
        """
        UPDATE services
        SET active = ?
        WHERE id = ?
        """,
        (
            0 if service["active"] else 1,
            service_id,
        ),
    )

    db.commit()

    flash("Service status updated.", "success")

    return redirect(url_for("dashboard") + "#services")


# ---------------------------------------------------------
# PROMOTIONS
# ---------------------------------------------------------

@app.post("/owner/promotion/add")
@owner_required("can_manage_promotions")
def add_promotion():
    validate_csrf()

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    discount = request.form.get("discount", "").strip()

    if not title or not discount:
        flash(
            "Promotion title and discount are required.",
            "error",
        )

        return redirect(url_for("dashboard") + "#promotions")

    db = get_db()

    db.execute(
        """
        INSERT INTO promotions
        (title, description, discount)
        VALUES (?, ?, ?)
        """,
        (
            title,
            description,
            discount,
        ),
    )

    db.commit()

    flash("Promotion added.", "success")

    return redirect(url_for("dashboard") + "#promotions")


@app.post("/owner/promotion/<int:promotion_id>/delete")
@owner_required("can_manage_promotions")
def delete_promotion(promotion_id):
    validate_csrf()

    db = get_db()

    db.execute(
        "DELETE FROM promotions WHERE id = ?",
        (promotion_id,),
    )

    db.commit()

    flash("Promotion deleted.", "success")

    return redirect(url_for("dashboard") + "#promotions")


@app.post("/owner/promotion/<int:promotion_id>/toggle")
@owner_required("can_manage_promotions")
def toggle_promotion(promotion_id):
    validate_csrf()

    db = get_db()

    promotion = db.execute(
        """
        SELECT active
        FROM promotions
        WHERE id = ?
        """,
        (promotion_id,),
    ).fetchone()

    if not promotion:
        abort(404)

    db.execute(
        """
        UPDATE promotions
        SET active = ?
        WHERE id = ?
        """,
        (
            0 if promotion["active"] else 1,
            promotion_id,
        ),
    )

    db.commit()

    flash("Promotion status updated.", "success")

    return redirect(url_for("dashboard") + "#promotions")


# ---------------------------------------------------------
# SALON SETTINGS
# ---------------------------------------------------------

@app.post("/owner/settings")
@owner_required("can_manage_account")
def update_settings():
    validate_csrf()

    fields = [
        "salon_name",
        "address",
        "phone",
        "opening_hours",
        "about",
    ]

    for field in fields:
        value = request.form.get(field, "").strip()
        set_setting(field, value)

    flash("Salon settings updated.", "success")

    return redirect(url_for("dashboard") + "#settings")


# ---------------------------------------------------------
# ACCOUNT
# ---------------------------------------------------------

@app.post("/owner/account")
@owner_required("can_manage_account")
def update_account():
    validate_csrf()

    username = request.form.get("username", "").strip()
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    db = get_db()

    owner = db.execute(
        "SELECT * FROM owner WHERE id = 1"
    ).fetchone()

    if not owner:
        abort(404)

    if not check_password_hash(
        owner["password_hash"],
        current_password,
    ):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("dashboard") + "#account")

    if not username:
        flash("Username cannot be empty.", "error")
        return redirect(url_for("dashboard") + "#account")

    if new_password and new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for("dashboard") + "#account")

    if new_password and len(new_password) < 8:
        flash(
            "New password must be at least 8 characters.",
            "error",
        )

        return redirect(url_for("dashboard") + "#account")

    if new_password:
        db.execute(
            """
            UPDATE owner
            SET username = ?,
                password_hash = ?
            WHERE id = 1
            """,
            (
                username,
                generate_password_hash(new_password),
            ),
        )

    else:
        db.execute(
            """
            UPDATE owner
            SET username = ?
            WHERE id = 1
            """,
            (username,),
        )

    db.commit()

    session["owner_username"] = username

    flash("Account updated successfully.", "success")

    return redirect(url_for("dashboard") + "#account")


# ---------------------------------------------------------
# GOOGLE MAPS DIRECTIONS
# ---------------------------------------------------------

@app.route("/directions")
def directions():
    address = get_setting(
        "address",
        "Bhopal, Madhya Pradesh, India",
    )

    maps_url = (
        "https://www.google.com/maps/dir/?api=1&destination="
        + quote_plus(address)
    )

    return redirect(maps_url)


# ---------------------------------------------------------
# ERROR PAGES
# ---------------------------------------------------------

@app.errorhandler(400)
def bad_request(error):
    return render_template(
        "error.html",
        code=400,
        message=str(error.description),
    ), 400


@app.errorhandler(403)
def forbidden(error):
    return render_template(
        "error.html",
        code=403,
        message="You do not have permission to access this page.",
    ), 403


@app.errorhandler(404)
def not_found(error):
    return render_template(
        "error.html",
        code=404,
        message="Page not found.",
    ), 404


# ---------------------------------------------------------
# STARTUP
# ---------------------------------------------------------

with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True,
    )