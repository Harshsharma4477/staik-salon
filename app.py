from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import quote_plus
import sqlite3
import os
import secrets
from datetime import date

app = Flask(**name**)

# =========================================================

# SETTINGS

# =========================================================

app.secret_key = os.environ.get(
"SECRET_KEY",
secrets.token_hex(32)
)

DB = os.environ.get(
"DB_PATH",
"staik_salon.db"
)

DEFAULT_USERNAME = os.environ.get(
"OWNER_USERNAME",
"admin"
)

DEFAULT_PASSWORD = os.environ.get(
"OWNER_PASSWORD",
"change-me-now"
)

# IMPORTANT:

# Is address ko apne actual salon ke Google Maps name/address se replace karo.

SALON_ADDRESS = os.environ.get(
"SALON_ADDRESS",
"Staik Salon, Bhopal, Madhya Pradesh"
)

TIMES = [
"10:00 AM",
"11:00 AM",
"12:00 PM",
"1:00 PM",
"2:00 PM",
"3:00 PM",
"4:00 PM",
"5:00 PM",
"6:00 PM",
"7:00 PM"
]

# =========================================================

# DATABASE

# =========================================================

def db():
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
return con

def init_db():

```
con = db()

con.executescript("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_id INTEGER NOT NULL,
        booking_date TEXT NOT NULL,
        booking_time TEXT NOT NULL,
        customer_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(booking_date, booking_time)
    );

    CREATE TABLE IF NOT EXISTS owner (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL
    );
""")

# Default services
count = con.execute(
    "SELECT COUNT(*) FROM services"
).fetchone()[0]

if count == 0:
    con.executemany(
        "INSERT INTO services(name, price) VALUES(?, ?)",
        [
            ("Haircut", 200),
            ("Hair Styling", 300),
            ("Hair Spa", 600),
            ("Facial", 500)
        ]
    )

# Default owner
owner = con.execute(
    "SELECT id FROM owner WHERE id=1"
).fetchone()

if not owner:
    con.execute(
        """
        INSERT INTO owner(id, username, password_hash)
        VALUES(1, ?, ?)
        """,
        (
            DEFAULT_USERNAME,
            generate_password_hash(DEFAULT_PASSWORD)
        )
    )

con.commit()
con.close()
```

# =========================================================

# HOME

# =========================================================

@app.route("/")
def home():

```
con = db()

services = con.execute(
    "SELECT * FROM services ORDER BY id"
).fetchall()

con.close()

return render_template(
    "index.html",
    services=services,
    today=date.today().isoformat(),
    salon_address=SALON_ADDRESS
)
```

# =========================================================

# AVAILABLE SLOTS

# =========================================================

@app.route("/slots")
def slots():

```
selected_date = request.args.get(
    "date",
    ""
).strip()

con = db()

booked = {
    row["booking_time"]
    for row in con.execute(
        """
        SELECT booking_time
        FROM bookings
        WHERE booking_date=?
        AND status != 'cancelled'
        """,
        (selected_date,)
    )
}

con.close()

return jsonify([
    {
        "time": time,
        "available": time not in booked
    }
    for time in TIMES
])
```

# =========================================================

# CREATE BOOKING

# =========================================================

@app.route("/book", methods=["POST"])
def book():

```
booking_date = request.form.get(
    "booking_date",
    ""
).strip()

booking_time = request.form.get(
    "booking_time",
    ""
).strip()

customer_name = request.form.get(
    "customer_name",
    ""
).strip()

phone = request.form.get(
    "phone",
    ""
).strip()

try:
    service_id = int(
        request.form.get(
            "service_id",
            "0"
        )
    )
except ValueError:
    service_id = 0

# Validation
if not all([
    booking_date,
    booking_time,
    customer_name,
    phone
]):
    flash("Please enter all booking details.")
    return redirect(url_for("home") + "#booking")

if len(phone) != 10 or not phone.isdigit():
    flash("Please enter a valid 10-digit mobile number.")
    return redirect(url_for("home") + "#booking")

if booking_time not in TIMES:
    flash("Please select a valid time slot.")
    return redirect(url_for("home") + "#booking")

if booking_date < date.today().isoformat():
    flash("Please select today or a future date.")
    return redirect(url_for("home") + "#booking")

con = db()

service = con.execute(
    "SELECT id FROM services WHERE id=?",
    (service_id,)
).fetchone()

if not service:
    con.close()
    flash("Please select a valid service.")
    return redirect(url_for("home") + "#booking")

try:

    con.execute(
        """
        INSERT INTO bookings(
            service_id,
            booking_date,
            booking_time,
            customer_name,
            phone
        )
        VALUES(?,?,?,?,?)
        """,
        (
            service_id,
            booking_date,
            booking_time,
            customer_name,
            phone
        )
    )

    con.commit()

    booking_id = con.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

except sqlite3.IntegrityError:

    con.close()

    flash("Sorry, this time slot is already booked.")
    return redirect(url_for("home") + "#booking")

con.close()

return render_template(
    "success.html",
    booking_id=booking_id,
    d=booking_date,
    t=booking_time,
    name=customer_name
)
```

# =========================================================

# OWNER AUTH

# =========================================================

def owner_required():
return session.get("owner") is True

@app.route("/owner/login", methods=["GET", "POST"])
def owner_login():

```
if request.method == "POST":

    username = request.form.get(
        "username",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )

    con = db()

    owner = con.execute(
        "SELECT * FROM owner WHERE id=1"
    ).fetchone()

    con.close()

    if (
        owner
        and username == owner["username"]
        and check_password_hash(
            owner["password_hash"],
            password
        )
    ):

        session.clear()
        session["owner"] = True

        return redirect(url_for("dashboard"))

    flash("Wrong username or password.")

return render_template("login.html")
```

@app.route("/owner/logout")
def owner_logout():

```
session.clear()

return redirect(url_for("home"))
```

# =========================================================

# OWNER DASHBOARD

# =========================================================

@app.route("/owner")
def dashboard():

```
if not owner_required():
    return redirect(url_for("owner_login"))

con = db()

bookings = con.execute(
    """
    SELECT
        b.*,
        s.name AS service,
        s.price AS price
    FROM bookings b
    JOIN services s
        ON s.id = b.service_id
    ORDER BY
        b.booking_date DESC,
        b.booking_time
    """
).fetchall()

services = con.execute(
    "SELECT * FROM services ORDER BY id"
).fetchall()

owner = con.execute(
    "SELECT username FROM owner WHERE id=1"
).fetchone()

con.close()

return render_template(
    "dashboard.html",
    bookings=bookings,
    services=services,
    owner=owner
)
```

# =========================================================

# BOOKING ACTION

# =========================================================

@app.route(
"/owner/booking/[int:bid](int:bid)/<action>",
methods=["POST"]
)
def booking_action(bid, action):

```
if not owner_required():
    return redirect(url_for("owner_login"))

if action not in (
    "confirmed",
    "cancelled"
):
    return redirect(url_for("dashboard"))

con = db()

con.execute(
    """
    UPDATE bookings
    SET status=?
    WHERE id=?
    """,
    (action, bid)
)

con.commit()
con.close()

return redirect(url_for("dashboard"))
```

# =========================================================

# ADD SERVICE

# =========================================================

@app.route(
"/owner/service/add",
methods=["POST"]
)
def service_add():

```
if not owner_required():
    return redirect(url_for("owner_login"))

name = request.form.get(
    "name",
    ""
).strip()

try:
    price = int(
        request.form.get(
            "price",
            "0"
        )
    )
except ValueError:
    price = 0

if not name or price <= 0:
    flash("Enter a valid service name and price.")
    return redirect(url_for("dashboard"))

con = db()

con.execute(
    """
    INSERT INTO services(name, price)
    VALUES(?, ?)
    """,
    (name, price)
)

con.commit()
con.close()

flash("Service added successfully.")

return redirect(url_for("dashboard"))
```

# =========================================================

# UPDATE SERVICE / RATE

# =========================================================

@app.route(
"/owner/service/[int:sid](int:sid)/update",
methods=["POST"]
)
def service_update(sid):

```
if not owner_required():
    return redirect(url_for("owner_login"))

name = request.form.get(
    "name",
    ""
).strip()

try:
    price = int(
        request.form.get(
            "price",
            "0"
        )
    )
except ValueError:
    price = 0

if not name or price <= 0:
    flash("Enter a valid service name and price.")
    return redirect(url_for("dashboard"))

con = db()

con.execute(
    """
    UPDATE services
    SET name=?,
        price=?
    WHERE id=?
    """,
    (name, price, sid)
)

con.commit()
con.close()

flash("Service updated successfully.")

return redirect(url_for("dashboard"))
```

# =========================================================

# DELETE SERVICE

# =========================================================

@app.route(
"/owner/service/[int:sid](int:sid)/delete",
methods=["POST"]
)
def service_delete(sid):

```
if not owner_required():
    return redirect(url_for("owner_login"))

con = db()

con.execute(
    "DELETE FROM services WHERE id=?",
    (sid,)
)

con.commit()
con.close()

flash("Service deleted.")

return redirect(url_for("dashboard"))
```

# =========================================================

# CHANGE OWNER USERNAME + PASSWORD

# =========================================================

@app.route(
"/owner/account",
methods=["POST"]
)
def owner_account():

```
if not owner_required():
    return redirect(url_for("owner_login"))

new_username = request.form.get(
    "username",
    ""
).strip()

new_password = request.form.get(
    "password",
    ""
)

if len(new_username) < 3:
    flash("Username must be at least 3 characters.")
    return redirect(url_for("dashboard"))

if len(new_password) < 8:
    flash("Password must be at least 8 characters.")
    return redirect(url_for("dashboard"))

con = db()

con.execute(
    """
    UPDATE owner
    SET username=?,
        password_hash=?
    WHERE id=1
    """,
    (
        new_username,
        generate_password_hash(new_password)
    )
)

con.commit()
con.close()

session.clear()

flash(
    "Username and password changed. Please login again."
)

return redirect(url_for("owner_login"))
```

# =========================================================

# GOOGLE MAPS

# =========================================================

@app.route("/directions")
def directions():

```
maps_url = (
    "https://www.google.com/maps/dir/?api=1"
    "&destination="
    + quote_plus(SALON_ADDRESS)
)

return redirect(maps_url)
```

# =========================================================

# START

# =========================================================

init_db()

if **name** == "**main**":

```
app.run(
    host="0.0.0.0",
    port=int(
        os.environ.get(
            "PORT",
            5000
        )
    ),
    debug=False
)
```
