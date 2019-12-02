from flask import (
    Flask,
    render_template,
    flash,
    redirect,
    url_for,
    session,
    request,
    logging,
)

import locale
import uuid
import random
import config
from datetime import date, timedelta
from collections import namedtuple

locale.setlocale(locale.LC_ALL, "de_DE.UTF-8")

from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators

from wtforms.fields.html5 import DateField
from passlib.hash import sha256_crypt
from functools import wraps

app = Flask(__name__)

# Config MySQL
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = config.MYSQL_USER
app.config["MYSQL_PASSWORD"] = config.MYSQL_PASSWORD
app.config["MYSQL_DB"] = config.MYSQL_DB
# Return Database querries as dict rather than tup
app.config["MYSQL_CURSORCLASS"] = "DictCursor"

# init MySQL
mysql = MySQL(app)

# Articles = Articles()

# Check if user is logged in
def is_logged_in(func):
    @wraps(func)
    def secure_login(*args, **kwargs):
        if "logged_in" in session:
            return func(*args, **kwargs)
        else:
            flash("Zugriff nicht gestattet, bitte einloggen.", "danger")
            return redirect(url_for("login"))

    return secure_login


# Index
@app.route("/")
def index():
    return render_template("index.html")


# Register Form Class
class RegisterForm(Form):
    email = StringField(
        "E-Mail",
        [
            validators.Length(
                min=4,
                max=100,
                message="Bitte eine E-Mail Adresse eingeben (4 bis 100 Zeichen).",
            )
        ],
    )
    username = StringField(
        "Benutzername",
        [
            validators.Length(
                min=4,
                max=30,
                message="Bitte einen Benutzernamen eingeben (4 bis 30 Zeichen).",
            )
        ],
    )
    password = PasswordField(
        "Passwort",
        [
            validators.DataRequired(),
            validators.EqualTo("confirm", message="Passwords do not match"),
        ],
    )
    confirm = PasswordField("Passwort wiederholen")


# User Register
@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm(request.form)
    if request.method == "POST" and form.validate():
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        # Create cursor
        cur = mysql.connection.cursor()

        cur.execute(
            "INSERT INTO users(id, email, username, password) VALUES(%s, %s, %s, %s)",
            (uuid.uuid4(), email, username, password),
        )

        # Comit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

        flash("Du bist jetzt registiert und kannst dich einloggen.", "success")

        return redirect(url_for("index"))

    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Get form fields
        username = request.form["username"]
        password_candidate = request.form["password"]

        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by username
        result = cur.execute("SELECT * FROM users WHERE username = %s", [username])

        if result:
            # Get stored hash
            data = cur.fetchone()
            password = data["password"]

            # Compare passwords
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session["logged_in"] = True
                session["username"] = username
                session["id"] = data["id"]

                flash("Du bist jetzt eingeloggt", "success")
                return redirect(url_for("aufenthalte"))

            else:
                flash("Passwort nicht korrekt.", "danger")
                return render_template("login.html")
            # Close connection
            cur.close()
        else:
            # error = "Username not found"
            flash("Username nicht registiert.", "danger")
            return render_template("login.html")

    return render_template("login.html")


# User logout
@app.route("/logout")
@is_logged_in
def logout():
    session.clear()
    flash("Ciao. Du bist jetzt wieder ausgeloggt.", "success")
    return redirect(url_for("login"))


# Trip Form Class
class TripForm(Form):
    startdate = DateField("Einreisedatum")  # format="%Y-%m-%d")
    enddate = DateField("Ausreisedatum")  # format="%Y-%m-%d")
    comment = StringField("Kommentar")


# Trip overview
@app.route("/aufenthalte")
@is_logged_in
def aufenthalte():
    # Create cursor
    cur = mysql.connection.cursor()

    app.logger.info(session["id"])
    result = cur.execute(
        "SELECT * FROM aufenthalte WHERE owner = %s ORDER BY startdate ASC",
        [session["id"]],
    )

    aufenthalte = cur.fetchall()

    if result:

        aufenthaltstage = 0
        today = date.today()
        planungsart = ""

        letztes_ausreisedatum = max(aufenthalt["enddate"] for aufenthalt in aufenthalte)

        if letztes_ausreisedatum <= today:
            # Festellen ob Datum der letzen Ausreise in der Vergangenheit
            # Berechnet den Stichtag, welcher 180 Tag in der Vergangenheit liegt (von heute)
            aufenthaltstage = calculate_aufenthaltstage(aufenthalte, today)
            stichtag = today - timedelta(days=180)
            planungsart = "Vergangenheit"
            print("Vergangenheit")
        else:
            # Festellen ob Datum der letzen Ausreise in der Zukunft
            # Berechnet den Stichtag, welcher 180 hinter dem letzten Ausreisedatum liegt
            aufenthaltstage = calculate_aufenthaltstage(
                aufenthalte, letztes_ausreisedatum
            )
            stichtag = letztes_ausreisedatum - timedelta(days=180)
            planungsart = "Zukunft"
            print(stichtag)
            print("Zukunft")

        # Berechnet die Anzahl "verbrauchter/verplanter" Tage (von 90 erlaubten Tagen)
        prozent_verbraucht = round((aufenthaltstage / 90) * 100)

        ### Add function that changes the "relevants" of enddates if needed

        # Separate the events into past and future events
        vergangene_aufenthalte = []
        zukuenftige_aufenthalte = []

        for aufenthalt in aufenthalte:
            startdate_heute = (today - aufenthalt["startdate"]).days
            enddate_heute = (today - aufenthalt["enddate"]).days

            if startdate_heute <= 0 and enddate_heute <= 0:
                zukuenftige_aufenthalte.append(aufenthalt)
                duration = (aufenthalt["enddate"] - aufenthalt["startdate"]).days

            else:
                vergangene_aufenthalte.append(aufenthalt)
                duration = (aufenthalt["enddate"] - aufenthalt["startdate"]).days

        cur.close()

        return render_template(
            "aufenthalte.html",
            vergangene_aufenthalte=vergangene_aufenthalte,
            zukuenftige_aufenthalte=zukuenftige_aufenthalte,
            stichtag=stichtag,
            aufenthaltstage=aufenthaltstage,
            prozent_verbraucht=prozent_verbraucht,
            today=today,
            planungsart=planungsart,
            letztes_ausreisedatum=letztes_ausreisedatum,
        )
    else:
        msg = "Keine Aufenthalt gefunden..."
        return render_template("aufenthalte.html", msg=msg)
    # Close connection
    cur.close()


def calculate_aufenthaltstage(aufenthalte, referenztag=date.today()):
    Range = namedtuple("Range", ["startdate", "enddate"])
    aufenthaltstage = 0

    for aufenthalt in aufenthalte:
        range1 = Range(
            startdate=(referenztag - timedelta(days=180)), enddate=referenztag
        )
        range2 = Range(startdate=aufenthalt["startdate"], enddate=aufenthalt["enddate"])
        latest_start = max(range1.startdate, range2.startdate)
        earliest_end = min(range1.enddate, range2.enddate)
        delta = (earliest_end - latest_start).days + 1
        overlap = max(0, delta)
        aufenthaltstage += overlap

    return aufenthaltstage


# Add Aufenthalt
@app.route("/aufenthalt_hinzufuegen", methods=["GET", "POST"])
@is_logged_in
def aufenthalt_hinzufuegen():
    form = TripForm(request.form)
    if request.method == "POST" and form.validate():
        startdate = form.startdate.data
        enddate = form.enddate.data
        comment = form.comment.data

        # Detect backward dates entered
        if startdate > enddate:
            flash("Das Einreisedatum muss vor dem Ausreisedatum liegen.", "danger")
            return redirect(url_for("aufenthalt_hinzufuegen"))

        # Restrict timedelta to max 90 days
        if (enddate - startdate).days > 90:
            flash(
                "Der Zeitraum zwischen den beiden Daten darf nicht mehr als 90 Tage betragen.",
                "danger",
            )
            return redirect(url_for("aufenthalt_hinzufuegen"))

        # Detect if overlap with existing dates

        # Create cursor
        cur = mysql.connection.cursor()

        app.logger.info(session["id"])
        result = cur.execute(
            "SELECT * FROM aufenthalte WHERE owner = %s ORDER BY startdate ASC",
            [session["id"]],
        )

        aufenthalte = cur.fetchall()
        Range = namedtuple("Range", ["startdate", "enddate"])

        overlap = 0
        if result:
            for aufenthalt in aufenthalte:
                range1 = Range(startdate=startdate, enddate=enddate)
                range2 = Range(
                    startdate=aufenthalt["startdate"], enddate=aufenthalt["enddate"]
                )
                latest_start = max(range1.startdate, range2.startdate)
                earliest_end = min(range1.enddate, range2.enddate)
                delta = (earliest_end - latest_start).days + 1
                overlap += max(0, delta)

        if overlap > 0:
            flash(
                "Es exisitert bereits mindestens ein Aufenthalt der sich mit diesem überschneiden würde.",
                "danger",
            )
            return redirect(url_for("aufenthalt_hinzufuegen"))
        # Close connection
        cur.close()

        # Create cursor
        cur = mysql.connection.cursor()

        # Execute
        cur.execute(
            "INSERT INTO aufenthalte(uid, owner, startdate, enddate, comment) VALUES(%s, %s, %s, %s, %s)",
            (IDGenerator().generate_id(), session["id"], startdate, enddate, comment),
        )

        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

        flash("Aufenthalt erfolgreich hinzugefügt", "success")

        return redirect(url_for("aufenthalte"))

    return render_template("aufenthalt_hinzufuegen.html", form=form)


# Delete Aufenthalt
@app.route("/delete_aufenthalt/<string:uid>/", methods=["POST"])
@is_logged_in
def delete_aufenthalt(uid):
    # Create cursor
    cur = mysql.connection.cursor()

    # Delet article by id
    cur.execute("DELETE FROM aufenthalte WHERE uid = %s", [uid])

    # Commit to DB
    mysql.connection.commit()

    # Close connection
    cur.close()

    flash("Aufenthalt erfolgreich gelöscht.", "success")

    return redirect(url_for("aufenthalte"))


# Random ID generator for trip IDs
class IDGenerator(object):
    ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"

    def __init__(self, length=8):
        self._alphabet_length = len(self.ALPHABET)
        self._id_length = length

    def _encode_int(self, n):
        # Adapted from:
        #   Source: https://stackoverflow.com/a/561809/1497596
        #   Author: https://stackoverflow.com/users/50902/kmkaplan

        encoded = ""
        while n > 0:
            n, r = divmod(n, self._alphabet_length)
            encoded = self.ALPHABET[r] + encoded
        return encoded

    def generate_id(self):
        """Generate an ID without leading zeros.

        For example, for an ID that is eight characters in length, the
        returned values will range from '10000000' to 'zzzzzzzz'.
        """

        start = self._alphabet_length ** (self._id_length - 1)
        end = self._alphabet_length ** self._id_length - 1
        return self._encode_int(random.randint(start, end))


if __name__ == "__main__":
    app.secret_key = config.SECRET_KEY
    app.run(debug=True, host="0.0.0.0", port="5050")
