```python
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash
import sqlite3
import os
import secrets
from datetime import date

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    app.secret_key = secrets.token_hex(32)

DB = os.environ.get("DB_PATH", "staik_salon.db")

OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "harsh47")
OWNER_PASSWORD_HASH = os.environ.get("OWNER_PASSWORD_HASH", "harsh@1234")

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


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()

    con.executescript("""
    CREATE TABLE IF NOT EXISTS services(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      price INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS bookings(
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
    """)

    if con.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
        con.executemany(
            "INSERT INTO services(name,price) VALUES(?,?)",
            [
                ("Haircut", 200),
                ("Hair Styling", 300),
                ("Hair Spa", 600),
                ("Facial", 500)
            ]
        )

    con.commit()
    con.close()


@app.route("/")
def home():
    con = db()

    services = con.execute(
        "SELECT * FROM services ORDER BY id"
    ).fetchall()

    con.close()

    return render_template(
        "index.html",
        services=services,
        today=date.today().isoformat()
    )


@app.route("/slots")
def slots():
    d = request.args.get("date", "").strip()

    con = db()

    booked = {
        r["booking_time"]
        for r in con.execute(
            """
            SELECT booking_time
            FROM bookings
            WHERE booking_date=?
            AND status!='cancelled'
            """,
            (d,)
        )
    }

    con.close()

    return jsonify([
        {
            "time": t,
            "available": t not in booked
        }
        for t in TIMES
    ])


@app.route("/book", methods=["POST"])
def book():
    data = request.form

    d = data.get("booking_date", "").strip()
    t = data.get("booking_time", "").strip()
    name = data.get("customer_name", "").strip()
    phone = data.get("phone", "").strip()

    try:
        sid = int(data.get("service_id", "0"))
    except ValueError:
        sid = 0

    if not all([d, t, name, phone]):
        flash("Please enter all booking details.")
        return redirect(url_for("home") + "#booking")

    if len(phone) != 10 or not phone.isdigit():
        flash("Please enter a valid 10-digit mobile number.")
        return redirect(url_for("home") + "#booking")

    if t not in TIMES:
        flash("Please select a valid time slot.")
        return redirect(url_for("home") + "#booking")

    if d < date.today().isoformat():
        flash("Please select today or a future date.")
        return redirect(url_for("home") + "#booking")

    con = db()

    service = con.execute(
        "SELECT id FROM services WHERE id=?",
        (sid,)
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
            (sid, d, t, name, phone)
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
        d=d,
        t=t,
        name=name
    )


def owner_required():
    return session.get("owner") is True


@app.route("/owner/login", methods=["GET", "POST"])
def owner_login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not OWNER_PASSWORD_HASH:
            flash("Owner login is not configured.")
            return render_template("login.html")

        if (
            username == OWNER_USERNAME
            and check_password_hash(
                OWNER_PASSWORD_HASH,
                password
            )
        ):
            session.clear()
            session["owner"] = True

            return redirect(url_for("dashboard"))

        flash("Wrong username or password.")

    return render_template("login.html")


@app.route("/owner/logout")
def owner_logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/owner")
def dashboard():

    if not owner_required():
        return redirect(url_for("owner_login"))

    con = db()

    bookings = con.execute(
        """
        SELECT
            b.*,
            s.name service,
            s.price
        FROM bookings b
        JOIN services s ON s.id=b.service_id
        ORDER BY b.booking_date DESC, b.booking_time
        """
    ).fetchall()

    services = con.execute(
        "SELECT * FROM services ORDER BY id"
    ).fetchall()

    con.close()

    return render_template(
        "dashboard.html",
        bookings=bookings,
        services=services
    )


@app.route("/owner/booking/<int:bid>/<action>", methods=["POST"])
def booking_action(bid, action):

    if not owner_required():
        return redirect(url_for("owner_login"))

    if action not in ("confirmed", "cancelled"):
        return redirect(url_for("dashboard"))

    con = db()

    con.execute(
        "UPDATE bookings SET status=? WHERE id=?",
        (action, bid)
    )

    con.commit()
    con.close()

    return redirect(url_for("dashboard"))


# ==============================
# ADD NEW SERVICE
# ==============================

@app.route("/owner/service/add", methods=["POST"])
def service_add():

    if not owner_required():
        return redirect(url_for("owner_login"))

    name = request.form.get("name", "").strip()

    try:
        price = int(request.form.get("price", "0"))
    except ValueError:
        price = 0

    if name and price > 0:

        con = db()

        con.execute(
            "INSERT INTO services(name,price) VALUES(?,?)",
            (name, price)
        )

        con.commit()
        con.close()

        flash("Service added successfully.")

    return redirect(url_for("dashboard"))


# ==============================
# EDIT SERVICE / CHANGE RATE
# ==============================

@app.route("/owner/service/<int:sid>/edit", methods=["POST"])
def service_edit(sid):

    if not owner_required():
        return redirect(url_for("owner_login"))

    name = request.form.get("name", "").strip()

    try:
        price = int(request.form.get("price", "0"))
    except ValueError:
        price = 0

    if not name or price <= 0:
        flash("Please enter a valid service name and price.")
        return redirect(url_for("dashboard"))

    con = db()

    service = con.execute(
        "SELECT id FROM services WHERE id=?",
        (sid,)
    ).fetchone()

    if not service:
        con.close()
        flash("Service not found.")
        return redirect(url_for("dashboard"))

    con.execute(
        """
        UPDATE services
        SET name=?, price=?
        WHERE id=?
        """,
        (name, price, sid)
    )

    con.commit()
    con.close()

    flash("Service updated successfully.")

    return redirect(url_for("dashboard"))


# ==============================
# DELETE SERVICE
# ==============================

@app.route("/owner/service/<int:sid>/delete", methods=["POST"])
def service_delete(sid):

    if not owner_required():
        return redirect(url_for("owner_login"))

    con = db()

    con.execute(
        "DELETE FROM services WHERE id=?",
        (sid,)
    )

    con.commit()
    con.close()

    flash("Service deleted successfully.")

    return redirect(url_for("dashboard"))


init_db()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
```


