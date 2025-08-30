from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from dbusers import Database
from plugins.dbusers import db

app = FastAPI()


@app.get("/")
async def home():
    return {"message": "TechVJ"}


@app.get("/files", response_class=HTMLResponse)
async def list_files():
    docs = await db.get_all_file_ids()
    links = [f"https://t.me/NewRan_bot/start={doc['file_id']}" for doc in docs if "file_id" in doc]

    # inline HTML (you can also use Jinja2 templates if needed)
    html = "<h1>Telegram File Links</h1>"
    for link in links:
        html += f'<div style="margin:10px; padding:10px; background:#eee;"><a href="{link}" target="_blank">{link}</a></div>'
    return html
