import os
import uuid

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

DB_KEY = os.getenv("DB_KEY")
DB_LINK = os.getenv("DB_LINK")

if not DB_KEY or not DB_LINK:
    raise RuntimeError("DB_KEY and DB_LINK must be set in .env")

supabase: Client = create_client(DB_LINK, DB_KEY)

app = Flask(__name__)


# =========================
# ГОЛОВНА
# =========================

@app.route("/")
def home():
    return render_template("index.html")


# =========================
# РЕЄСТРАЦІЯ
# =========================

@app.route("/register", methods=["POST"])
def register():

    try:
        data = request.get_json()

        username = data.get("username", "").strip()
        password = data.get("password", "")

        # Перевірка
        if not username or not password:
            return jsonify({
                "error": "Введи нік і пароль"
            }), 400

        if len(username) < 3:
            return jsonify({
                "error": "Нік має містити мінімум 3 символи"
            }), 400

        if len(username) > 30:
            return jsonify({
                "error": "Нік може містити максимум 30 символів"
            }), 400

        if len(password) < 6:
            return jsonify({
                "error": "Пароль має містити мінімум 6 символів"
            }), 400

        # Перевіряємо, чи існує нік
        existing = (
            supabase
            .table("profiles")
            .select("id")
            .eq("username", username)
            .execute()
        )

        if existing.data:
            return jsonify({
                "error": "Такий нік уже зайнятий"
            }), 409

        # Створюємо користувача
        user_id = str(uuid.uuid4())

        password_hash = generate_password_hash(password)

        response = (
            supabase
            .table("profiles")
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

        # Створюємо простий токен сесії
        token = str(uuid.uuid4())

        # Для простоти зберігаємо токен у пам'яті Flask
        sessions[token] = user_id

        return jsonify({
            "message": "Реєстрація успішна",
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"]
            }
        }), 201

    except Exception as e:

        print("REGISTER ERROR:", e)

        return jsonify({
            "error": "Помилка під час реєстрації"
        }), 500


# =========================
# ВХІД
# =========================

@app.route("/login", methods=["POST"])
def login():

    try:
        data = request.get_json()

        username = data.get("username", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return jsonify({
                "error": "Введи нік і пароль"
            }), 400

        response = (
            supabase
            .table("profiles")
            .select("*")
            .eq("username", username)
            .execute()
        )

        if not response.data:
            return jsonify({
                "error": "Неправильний нік або пароль"
            }), 401

        user = response.data[0]

        if not check_password_hash(
            user["password_hash"],
            password
        ):
            return jsonify({
                "error": "Неправильний нік або пароль"
            }), 401

        # Створюємо сесію
        token = str(uuid.uuid4())

        sessions[token] = user["id"]

        return jsonify({
            "message": "Вхід успішний",
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"]
            }
        })

    except Exception as e:

        print("LOGIN ERROR:", e)

        return jsonify({
            "error": "Помилка входу"
        }), 500


# =========================
# ПОВІДОМЛЕННЯ
# =========================

@app.route("/messages", methods=["GET"])
def get_messages():

    user = get_current_user()

    if not user:
        return jsonify({
            "error": "Необхідна авторизація"
        }), 401

    try:

        response = (
            supabase
            .table("messages")
            .select("*")
            .order("created_at", desc=False)
            .execute()
        )

        return jsonify(response.data)

    except Exception as e:

        print("GET MESSAGES ERROR:", e)

        return jsonify({
            "error": "Не вдалося отримати повідомлення"
        }), 500


# =========================
# ВІДПРАВКА ПОВІДОМЛЕННЯ
# =========================

@app.route("/messages", methods=["POST"])
def send_message():

    user = get_current_user()

    if not user:
        return jsonify({
            "error": "Необхідна авторизація"
        }), 401

    try:

        data = request.get_json()

        message = data.get("message", "").strip()

        if not message:
            return jsonify({
                "error": "Введи повідомлення"
            }), 400

        if len(message) > 1000:
            return jsonify({
                "error": "Повідомлення занадто довге"
            }), 400

        response = (
            supabase
            .table("messages")
            .insert({
                "user_id": user["id"],
                "username": user["username"],
                "message": message
            })
            .execute()
        )

        return jsonify(response.data[0]), 201

    except Exception as e:

        print("SEND MESSAGE ERROR:", e)

        return jsonify({
            "error": "Не вдалося відправити повідомлення"
        }), 500


# =========================
# СЕСІЇ
# =========================

sessions = {}


def get_current_user():

    authorization = request.headers.get("Authorization")

    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        return None

    token = authorization.replace("Bearer ", "", 1)

    user_id = sessions.get(token)

    if not user_id:
        return None

    response = (
        supabase
        .table("profiles")
        .select("id, username")
        .eq("id", user_id)
        .single()
        .execute()
    )

    if not response.data:
        return None

    return response.data


# =========================
# ЗАПУСК
# =========================

if __name__ == "__main__":
    app.run(debug=True)