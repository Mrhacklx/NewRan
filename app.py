from flask import Flask, render_template, request
from pymongo import MongoClient
import os

app = Flask(__name__)

# ----------------- MongoDB Setup -----------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "videodb")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
col_links = db["links"]   # collection where links are stored


# ----------------- Routes -----------------
@app.route("/")
def hello_world():
    return "TechVJ"


@app.route("/videos")
def videos_page():
    # pagination params
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 6))
    skip = (page - 1) * size

    total = col_links.count_documents({})
    cursor = col_links.find().skip(skip).limit(size)

    links = [doc.get("link") for doc in cursor if doc.get("link")]

    # calculate prev/next
    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if skip + size < total else None

    return render_template(
        "videos.html",
        videos=links,
        page=page,
        size=size,
        prev_page=prev_page,
        next_page=next_page,
    )


# ----------------- Main -----------------
if __name__ == "__main__":
    app.run(debug=True)
