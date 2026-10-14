import os
import re
import time

import psycopg2
import psycopg2.extras
from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = "prototyp-nie-pre-produkciu"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://parking:parking@localhost:5432/parking")


def db():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """Počká na databázu a vytvorí tabuľky."""
    for _ in range(30):
        try:
            with db() as conn, conn.cursor() as cur:
                cur.execute(open(os.path.join(os.path.dirname(__file__), "schema.sql")).read())
            return
        except psycopg2.OperationalError:
            time.sleep(1)
    raise RuntimeError("Databáza nie je dostupná")


def db_info():
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute("SELECT version()")
            ver = cur.fetchone()[0].split(",")[0]
        return True, ver
    except Exception as e:  # noqa
        return False, str(e)


@app.route("/", methods=["GET", "POST"])
def registracia():
    if request.method == "POST":
        meno = request.form.get("meno", "").strip()
        email = request.form.get("email", "").strip().lower()
        telefon = request.form.get("telefon", "").strip()
        heslo = request.form.get("heslo", "")
        evc = re.sub(r"\s+", "", request.form.get("evc", "")).upper()

        chyby = []
        if not meno:
            chyby.append("Zadajte meno.")
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            chyby.append("Zadajte platnú e-mailovú adresu.")
        if not telefon:
            chyby.append("Zadajte telefónne číslo.")
        if len(heslo) < 8:
            chyby.append("Heslo musí mať minimálne 8 znakov.")
        if not evc:
            chyby.append("Zadajte aspoň jednu poznávaciu značku.")

        if not chyby:
            try:
                with db() as conn, conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO pouzivatel (meno, email, telefon, heslo_hash) "
                        "VALUES (%s,%s,%s,%s) RETURNING id",
                        (meno, email, telefon, generate_password_hash(heslo)),
                    )
                    uid = cur.fetchone()[0]
                    cur.execute("INSERT INTO vozidlo (pouzivatel_id, evc) VALUES (%s,%s)", (uid, evc))
                flash(f"Registrácia úspešná. Používateľ „{meno}“ bol uložený do databázy (ID {uid}).", "ok")
                return redirect(url_for("pouzivatelia"))
            except psycopg2.errors.UniqueViolation:
                chyby.append("Používateľ s týmto e-mailom už existuje.")
        for c in chyby:
            flash(c, "err")
    ok, info = db_info()
    return render_template("registracia.html", db_ok=ok, db_info=info)


@app.route("/pouzivatelia")
def pouzivatelia():
    with db() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT p.id, p.meno, p.email, p.telefon, p.kredit, p.vytvoreny, "
            "string_agg(v.evc, ', ') AS evc "
            "FROM pouzivatel p LEFT JOIN vozidlo v ON v.pouzivatel_id = p.id "
            "GROUP BY p.id ORDER BY p.id DESC"
        )
        rows = cur.fetchall()
    ok, info = db_info()
    return render_template("pouzivatelia.html", rows=rows, db_ok=ok, db_info=info)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
