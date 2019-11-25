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

# from data import Articles

from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators

from wtforms.fields.html5 import DateField  # <-- for Datefields
from datetime import date

from passlib.hash import sha256_crypt
from functools import wraps

app = Flask(__name__)

# Config MySQL
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = "########"
app.config["MYSQL_DB"] = "mytripsapp"
# Return Database querries as dict rather than tup
app.config["MYSQL_CURSORCLASS"] = "DictCursor"

# init MySQL
mysql = MySQL(app)

# Articles = Articles()

# Check if user is logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "logged_in" in session:
            return f(*args, **kwargs)
        else:
            flash("Not authorized, please log in", "danger")
            return redirect(url_for("login"))

    return wrap


# Index
@app.route("/")
def index():
    return render_template("index.html")


# About
@app.route("/about")
def about():
    return render_template("about.html")


# Articles overview
@app.route("/articles")
@is_logged_in
def articles():
    # Create cursor
    cur = mysql.connection.cursor()

    result = cur.execute(
        "SELECT * FROM articles WHERE author=%s", [session["username"]]
    )

    articles = cur.fetchall()

    if result > 0:
        return render_template("articles.html", articles=articles)
    else:
        msg = "No articles found"
        return render_template("articles.html", msg=msg)
    # Close connection
    cur.close()


# Single Articles
@app.route("/article/<string:id>/")
def article(id):
    # Create cursor
    cur = mysql.connection.cursor()

    result = cur.execute("SELECT * FROM articles WHERE id=%s", [id])

    article = cur.fetchone()

    # Close connection
    cur.close()

    return render_template("article.html", article=article)


@app.route("/contact")
def contact():
    return render_template("contact.html")


# Register Form Class
class RegisterForm(Form):
    startdate = DateField(
        "DatePicker", format="%Y-%m-%d", default=date.today()
    )  # <-- for Datefields
    name = StringField("Name", [validators.Length(min=1, max=50)])
    username = StringField("Username", [validators.Length(min=4, max=25)])
    email = StringField("Email", [validators.Length(min=6, max=50)])
    password = PasswordField(
        "Password",
        [
            validators.DataRequired(),
            validators.EqualTo("confirm", message="Passwords do not match"),
        ],
    )
    confirm = PasswordField("Confirm Password")


# User Register
@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm(request.form)
    if request.method == "POST" and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        # Create cursor
        cur = mysql.connection.cursor()

        cur.execute(
            "INSERT INTO users(name, email, username, password) VALUES(%s, %s, %s, %s)",
            (name, email, username, password),
        )

        # Comit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

        flash("You are now registered and can log in", "success")

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

        if result > 0:
            # Get stored hash
            data = cur.fetchone()
            password = data["password"]

            # Compare passwords
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session["logged_in"] = True
                session["username"] = username

                flash("You are now logged in", "success")
                return redirect(url_for("index"))

            else:
                error = "Invalid login"
                return render_template("login.html", error=error)
            # Close connection
            cur.close()
        else:
            error = "Username not found"
            return render_template("login.html", error=error)

    return render_template("login.html")


# User logout
@app.route("/logout")
@is_logged_in
def logout():
    session.clear()
    flash("Your are now logged out", "success")
    return redirect(url_for("login"))


# Dashboard
@app.route("/dashboard")
@is_logged_in
def dashboard():
    # Create cursor
    cur = mysql.connection.cursor()

    result = cur.execute(
        "SELECT * FROM articles WHERE author=%s", [session["username"]]
    )

    articles = cur.fetchall()

    if result > 0:
        return render_template("dashboard.html", articles=articles)
    else:
        msg = "No articles found"
        return render_template("dashboard.html", msg=msg)
    # Close connection
    cur.close()


# Article Form Class
class ArticleForm(Form):
    title = StringField("Title", [validators.Length(min=1, max=200)])
    body = TextAreaField("Body", [validators.Length(min=30)])


# Add article
@app.route("/add_article", methods=["GET", "POST"])
@is_logged_in
def add_article():
    form = ArticleForm(request.form)
    if request.method == "POST" and form.validate():
        title = form.title.data
        body = form.body.data

        # Create cursor
        cur = mysql.connection.cursor()

        # Execute
        cur.execute(
            "INSERT INTO articles(title, body, author) VALUES(%s, %s, %s)",
            (title, body, session["username"]),
        )

        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

        flash("Article created", "success")

        return redirect(url_for("dashboard"))

    return render_template("add_article.html", form=form)


# Edit article
@app.route("/edit_article/<string:id>/", methods=["GET", "POST"])
@is_logged_in
def edit_article(id):
    # Create cursor
    cur = mysql.connection.cursor()

    # Get article by id
    result = cur.execute("SELECT * FROM articles WHERE id = %s", [id])

    article = cur.fetchone()

    # Get form
    form = ArticleForm(request.form)

    # Populate article form fields
    form.title.data = article["title"]
    form.body.data = article["body"]

    if request.method == "POST" and form.validate():
        title = request.form["title"]
        body = request.form["body"]

        # Create cursor
        cur = mysql.connection.cursor()

        # Execute
        cur.execute(
            "UPDATE articles SET title=%s, body=%s WHERE id=%s", (title, body, id)
        )

        # Commit to DB
        mysql.connection.commit()

        # Close connection
        cur.close()

        flash("Article updated ", "success")

        return redirect(url_for("dashboard"))

    return render_template("edit_article.html", form=form)


# Delete Articles
@app.route("/delete_article/<string:id>/", methods=["POST"])
@is_logged_in
def delete_article(id):
    # Create cursor
    cur = mysql.connection.cursor()

    # Delet article by id
    cur.execute("DELETE FROM articles WHERE id = %s", [id])

    # Commit to DB
    mysql.connection.commit()

    # Close connection
    cur.close()

    flash("Article deleted ", "success")

    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.secret_key = "secret123"
    app.run(debug=True)
