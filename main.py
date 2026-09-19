import os

from flask import Flask, jsonify, render_template
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

DB_KEY = os.getenv("DB_KEY")
DB_LINK = os.getenv("DB_LINK")

if not DB_KEY or not DB_LINK:
    raise RuntimeError("DB_KEY and DB_LINK must be set in .env")

supabase: Client = create_client(DB_LINK, DB_KEY)

app = Flask(__name__)


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/users")
def get_users():
    response = supabase.table("users").select("*").execute()

    return jsonify(response.data)


if __name__ == "__main__":
    app.run(debug=True)
