from flask import Flask, render_template
from pymongo import MongoClient
import os

app = Flask(__name__)

# ---------------- Routes ----------------
@app.route('/')
def home():
    return 'TechVJ'


# ---------------- Run Server ----------------
if __name__ == "__main__":
    app.run(debug=True)
