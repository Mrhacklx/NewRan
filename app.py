from flask import Flask, render_template
from pymongo import MongoClient
from plugins.dbusers import db
import os

app = Flask(__name__)

# ---------------- Routes ----------------
@app.route('/')
def home():
    return 'TechVJ'


@app.route('/files')
def list_files():
    """Fetch all file_ids and show them as Telegram links."""
    docs = await db.get_all_file_ids()
    links = [f"https://t.me/NewRan_bot/start={doc['file_id']}" for doc in docs if "file_id" in doc]
    return render_template("files.html", links=links)


# ---------------- Run Server ----------------
if __name__ == "__main__":
    app.run(debug=True)
