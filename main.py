
import os
import uuid

from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

DB_KEY = os.getenv("DB_KEY")
DB_LINK = os.getenv("DB_LINK")

if not DB_KEY or not DB_LINK:
    raise RuntimeError("DB_KEY та DB_LINK потрібно вказати у .env")

supabase: Client = create_client(DB_LINK, DB_KEY)

app = Flask(__name__)

# Демонстраційні сесії в пам'яті.
# Після перезапуску сервера користувачі мають увійти повторно.
sessions = {}

SESSION_LIFETIME = timedelta(days=7)


def create_session(user_id):
    token = str(uuid.uuid4())

    sessions[token] = {
        "user_id": user_id,
        "expires_at": datetime.now(timezone.utc) + SESSION_LIFETIME
    }

    return token


def get_current_user():
    authorization = request.headers.get("Authorization", "")

    if not authorization.startswith("Bearer "):
        return None

    token = authorization[7:].strip()
    session = sessions.get(token)

    if not session:
        return None

    if datetime.now(timezone.utc) >= session["expires_at"]:
        sessions.pop(token, None)
        return None

    try:
        response = (
            supabase.table("profiles")
            .select("id, username")
            .eq("id", session["user_id"])
            .limit(1)
            .execute()
        )

        if not response.data:
            sessions.pop(token, None)
            return None

        return response.data[0]

    except Exception as error:
        app.logger.error("GET USER ERROR: %s", error)
        raise


@app.route("/")
def home():
    return render_template("index.html")


# РЕЄСТРАЦІЯ

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    username = data.get("username", "")
    password = data.get("password", "")

    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "Неправильні дані"}), 400

    username = username.strip()

    if not 3 <= len(username) <= 30:
        return jsonify({
            "error": "Нік має містити від 3 до 30 символів"
        }), 400

    if len(password) < 6:
        return jsonify({
            "error": "Пароль має містити щонайменше 6 символів"
        }), 400

    try:
        existing = (
            supabase.table("profiles")
            .select("id")
            .eq("username", username)
            .limit(1)
            .execute()
        )

        if existing.data:
            return jsonify({
                "error": "Такий нік уже зайнятий"
            }), 409

        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password)

        response = (
            supabase.table("profiles")
            .insert({
                "id": user_id,
                "username": username,
                "password_hash": password_hash
            })
            .execute()
        )

        if not response.data:
            return jsonify({
                "error": "Не вдалося створити акаунт"
            }), 500

        user = response.data[0]
        token = create_session(user["id"])

        return jsonify({
            "message": "Реєстрація успішна",
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"]
            }
        }), 201

    except Exception:
        app.logger.exception("REGISTER ERROR")

        return jsonify({
            "error": "Помилка під час реєстрації"
        }), 500


# ВХІД

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    username = data.get("username", "")
    password = data.get("password", "")

    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "Неправильні дані"}), 400

    username = username.strip()

    if not username or not password:
        return jsonify({
            "error": "Введи нік і пароль"
        }), 400

    try:
        response = (
            supabase.table("profiles")
            .select("id, username, password_hash")
            .eq("username", username)
            .limit(1)
            .execute()
        )

        if not response.data:
            return jsonify({
                "error": "Неправильний нік або пароль"
            }), 401

        user = response.data[0]

        if not check_password_hash(user["password_hash"], password):
            return jsonify({
                "error": "Неправильний нік або пароль"
            }), 401

        token = create_session(user["id"])

        return jsonify({
            "message": "Вхід успішний",
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"]
            }
        })

    except Exception:
        app.logger.exception("LOGIN ERROR")

        return jsonify({
            "error": "Помилка входу"
        }), 500


# ОТРИМАННЯ ПОВІДОМЛЕНЬ

@app.route("/messages", methods=["GET"])
def get_messages():
    try:
        user = get_current_user()

        if not user:
            return jsonify({
                "error": "Необхідна авторизація"
            }), 401

        response = (
            supabase.table("messages")
            .select("id, user_id, username, message, created_at")
            .order("created_at", desc=False)
            .limit(500)
            .execute()
        )

        return jsonify(response.data)

    except Exception:
        app.logger.exception("GET MESSAGES ERROR")

        return jsonify({
            "error": "Не вдалося отримати повідомлення"
        }), 500


# ВІДПРАВЛЕННЯ ПОВІДОМЛЕННЯ

@app.route("/messages", methods=["POST"])
def send_message():
    try:
        user = get_current_user()

        if not user:
            return jsonify({
                "error": "Необхідна авторизація"
            }), 401

        data = request.get_json(silent=True) or {}
        message = data.get("message", "")

        if not isinstance(message, str):
            return jsonify({
                "error": "Повідомлення має бути текстом"
            }), 400

        message = message.strip()

        if not message:
            return jsonify({
                "error": "Введи повідомлення"
            }), 400

        if len(message) > 1000:
            return jsonify({
                "error": "Повідомлення не може бути довшим за 1000 символів"
            }), 400

        response = (
            supabase.table("messages")
            .insert({
                "user_id": user["id"],
                "username": user["username"],
                "message": message
            })
            .execute()
        )

        if not response.data:
            return jsonify({
                "error": "Не вдалося зберегти повідомлення"
            }), 500

        return jsonify(response.data[0]), 201

    except Exception:
        app.logger.exception("SEND MESSAGE ERROR")

        return jsonify({
            "error": "Не вдалося відправити повідомлення"
        }), 500


if __name__ == "__main__":
    app.run(debug=True)