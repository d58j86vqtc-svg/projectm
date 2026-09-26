
import os

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

DB_KEY = os.getenv("DB_KEY")
DB_LINK = os.getenv("DB_LINK")

if not DB_KEY or not DB_LINK:
    raise RuntimeError("DB_KEY and DB_LINK must be set in .env")

supabase: Client = create_client(DB_LINK, DB_KEY)

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/messages", methods=["GET"])
def get_messages():
    response = (
        supabase
        .table("messages")
        .select("*")
        .order("created_at", desc=False)
        .execute()
    )

    return jsonify(response.data)


@app.route("/messages", methods=["POST"])
def send_message():
    data = request.get_json()

    username = data.get("username", "").strip()
    message = data.get("message", "").strip()

    if not username:
        return jsonify({"error": "Введи ім'я"}), 400

    if not message:
        return jsonify({"error": "Введи повідомлення"}), 400

    if len(username) > 30:
        return jsonify({"error": "Ім'я занадто довге"}), 400

    if len(message) > 1000:
        return jsonify({"error": "Повідомлення занадто довге"}), 400

    response = (
        supabase
        .table("messages")
        .insert({
            "username": username,
            "message": message
        })
        .execute()
    )

    return jsonify(response.data[0]), 201


if __name__ == "__main__":
    app.run(debug=True)

