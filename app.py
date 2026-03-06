import os

from flask import Flask, abort, g, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
#database_url = os.getenv(
#    "DATABASE_URL",
#    "postgresql+psycopg://shopping:shoppingpass@localhost:5432/shopping",
#)
# Handle older-style URLs used by some tooling/platforms.
#if database_url.startswith("postgres://"):
#    database_url = database_url.replace("postgres://", "postgresql://", 1)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER","shopping")
DB_PASSWORD = os.getenv("DB_PASS", os.getenv("DB_PASSWORD", "shoppingpass"))
DB_NAME = os.getenv("DB_NAME","shopping")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}"

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)


def ensure_default_admin() -> None:
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        return

    admin = User.query.filter_by(username=ADMIN_USERNAME).first()
    if admin is None:
        admin = User(username=ADMIN_USERNAME, is_admin=True)
        db.session.add(admin)

    admin.password_hash = generate_password_hash(ADMIN_PASSWORD)
    admin.is_admin = True
    db.session.commit()


with app.app_context():
    db.create_all()
    ensure_default_admin()


@app.before_request
def require_auth():
    public_endpoints = {"login", "health", "static"}
    if request.endpoint in public_endpoints:
        return None

    user_id = session.get("user_id")
    if request.endpoint and user_id is None:
        return redirect(url_for("login"))

    user = db.session.get(User, user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    g.current_user = user
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            return redirect(url_for("index"))

        error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    items = Item.query.order_by(Item.id.desc()).all()
    return render_template(
        "index.html",
        items=items,
        username=g.current_user.username,
        is_admin=g.current_user.is_admin,
    )


@app.route("/admin/users")
def user_management():
    if not g.current_user.is_admin:
        abort(403)

    users = User.query.order_by(User.username.asc()).all()
    return render_template("users.html", users=users, username=g.current_user.username)


@app.post("/admin/users")
def create_user():
    if not g.current_user.is_admin:
        abort(403)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    is_admin = request.form.get("is_admin") == "on"

    if not username or not password:
        return redirect(url_for("user_management"))

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return redirect(url_for("user_management"))

    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        is_admin=is_admin,
    )
    db.session.add(user)
    db.session.commit()
    return redirect(url_for("user_management"))


@app.post("/admin/users/<int:user_id>/toggle-admin")
def toggle_user_admin(user_id: int):
    if not g.current_user.is_admin:
        abort(403)

    user = User.query.get_or_404(user_id)
    if user.id == g.current_user.id:
        return redirect(url_for("user_management"))

    user.is_admin = not user.is_admin
    db.session.commit()
    return redirect(url_for("user_management"))


@app.post("/admin/users/<int:user_id>/delete")
def delete_user(user_id: int):
    if not g.current_user.is_admin:
        abort(403)

    user = User.query.get_or_404(user_id)
    if user.id == g.current_user.id:
        return redirect(url_for("user_management"))

    db.session.delete(user)
    db.session.commit()
    return redirect(url_for("user_management"))


@app.post("/items")
def create_item():
    name = request.form.get("name", "").strip()
    quantity_raw = request.form.get("quantity", "1").strip()

    if not name:
        return redirect(url_for("index"))

    try:
        quantity = int(quantity_raw)
        if quantity < 1:
            quantity = 1
    except ValueError:
        quantity = 1

    db.session.add(Item(name=name, quantity=quantity))
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/items/<int:item_id>/edit")
def edit_item_page(item_id: int):
    item = Item.query.get_or_404(item_id)
    return render_template("edit.html", item=item)


@app.post("/items/<int:item_id>")
def update_item(item_id: int):
    item = Item.query.get_or_404(item_id)
    name = request.form.get("name", "").strip()
    quantity_raw = request.form.get("quantity", "1").strip()

    if name:
        item.name = name

    try:
        quantity = int(quantity_raw)
        if quantity < 1:
            quantity = 1
    except ValueError:
        quantity = item.quantity

    item.quantity = quantity
    db.session.commit()
    return redirect(url_for("index"))


@app.post("/items/<int:item_id>/delete")
def delete_item(item_id: int):
    item = Item.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
