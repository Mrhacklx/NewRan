import re
import time
import math
import logging
import secrets
import mimetypes
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from TechVJ.bot import multi_clients, work_loads, StreamBot
from TechVJ.server.exceptions import FIleNotFound, InvalidHash
from TechVJ import StartTime, __version__
from ..utils.time_format import get_readable_time
from ..utils.custom_dl import ByteStreamer
from TechVJ.utils.render_template import render_page
from plugins.dbusers import db
from config import MULTI_CLIENT, IMAGE_PATH, LOG_CHANNEL, URL 
from pyrogram import Client
import aiohttp


routes = web.RouteTableDef()

@routes.get("/status", allow_head=True)
async def root_route_handler(request):
    html = f"""
    <html>
      <head>
        <title>NewRan Bot Status</title>
        <style>
          body {{ font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }}
          .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0,0,0,0.2); max-width: 600px; margin: auto; }}
          h2 {{ color: #333; }}
          ul {{ padding: 0; list-style: none; }}
          li {{ padding: 4px 0; }}
        </style>
      </head>
      <body>
        <div class="card">
          <h2>🚀 Bot Server Status</h2>
          <p><b>Status:</b> running</p>
          <p><b>Uptime:</b> {get_readable_time(time.time() - StartTime)}</p>
          <p><b>Telegram Bot:</b> @{StreamBot.username}</p>
          <p><b>Connected Bots:</b> {len(multi_clients)}</p>
          <p><b>Version:</b> {__version__}</p>
          <h3>⚡ Workloads</h3>
          <ul>
            {"".join(f"<li>{'bot'+str(c+1)} → {l}</li>" for c, (_, l) in enumerate(sorted(work_loads.items(), key=lambda x: x[1], reverse=True)))}
          </ul>
        </div>
      </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")

@routes.get("/")
async def list_files(request):
    """Return an HTML page showing all file links from MongoDB in responsive card layout."""
    
    # Fetch all file documents
    docs = await db.get_all_file_ids()
    
    # Prepare card data with file link and poster URL
    files_data = []
    poster_base_url = f"{URL}/poster/"
    
    for i, doc in enumerate(docs):
        if "file_id" in doc and "poster_id" in doc:
            file_link = f"https://t.me/NewRan_bot?start={doc['file_id']}"
            poster_url = f"{poster_base_url}{doc['poster_id']}"
            files_data.append({
                "title": f"⭕<b>{i+1}<b>: New Video",
                "url": file_link,
                "poster": poster_url
            })
    
    # Convert to JS array string
    cards_js_array = "[" + ",".join([f'{{"title":"{f["title"]}","url":"{f["url"]}","poster":"{f["poster"]}"}}' for f in files_data]) + "]"

    html = f"""
    <html>
      <head>
        <title>Premium Files</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
          body {{
            font-family: Arial, sans-serif;
            margin: 0;
            background: #121212;
            color: white;
          }}
          .header {{
            background: #1f1f1f;
            padding: 15px;
            font-size: 20px;
            font-weight: bold;
            display: flex;
            align-items: center;
          }}
          .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 15px;
            padding: 20px;
          }}
          @media (min-width: 600px) {{
            .grid {{
              grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            }}
          }}
          @media (min-width: 900px) {{
            .grid {{
              grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            }}
          }}
          @media (min-width: 1200px) {{
            .grid {{
              grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            }}
          }}
          .card {{
            background: #1e1e1e;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.5);
            cursor: pointer;
            transition: transform 0.3s;
          }}
          .card:hover {{
            transform: scale(1.05);
          }}
          .poster {{
            width: 100%;
            padding-top: 150%;
            background-size: cover;
            background-position: center;
          }}
          .info {{
            padding: 10px;
            font-size: 14px;
            text-align: center;
          }}
          .btn {{
            display: block;
            margin: 20px auto;
            padding: 12px 24px;
            background: #e50914;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            transition: 0.3s;
          }}
          .btn:hover {{
            background: #b0060f;
          }}
        </style>
      </head>
      <body>
        <div class="header">🔥 Latest Releases</div>
        <div class="grid" id="file-grid"></div>
        <button class="btn" onclick="loadMore()">Load More</button>

        <script>
          const files = {cards_js_array};
          let currentIndex = 0;
          const perPage = 8;

          function loadMore() {{
            const grid = document.getElementById("file-grid");
            const nextFiles = files.slice(currentIndex, currentIndex + perPage);
            nextFiles.forEach(f => {{
              const card = document.createElement("div");
              card.className = "card";
              card.onclick = () => window.open(f.url, "_blank");
              card.innerHTML = `
                <div class="poster" style="background-image: url('${{f.poster}}')"></div>
                <div class="info">${{f.title}}</div>
              `;
              grid.appendChild(card);
            }});
            currentIndex += perPage;
            if (currentIndex >= files.length) {{
              document.querySelector(".btn").style.display = "none";
            }}
          }}

          loadMore();
        </script>
      </body>
    </html>
    """

    return web.Response(text=html, content_type="text/html")

@routes.get("/poster/{file_id}")
async def get_poster(request: web.Request):
    file_id = request.match_info["file_id"]
    
    try:
        client = StreamBot  # or choose multi_clients[0]
        
        # Download media directly from the file_id
        file_bytes = await client.download_media(file_id, in_memory=True)
        file_bytes.seek(0)
        
        return web.Response(body=file_bytes.read(), content_type="image/jpeg")
    
    except Exception as e:
        logging.error(f"Error fetching poster: {e}")
        raise web.HTTPInternalServerError(text=str(e))

@routes.get(r"/watch/{path:\S+}", allow_head=True)
async def stream_handler(request: web.Request):
    try:
        path = request.match_info["path"]
        match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", path)
        if match:
            secure_hash = match.group(1)
            id = int(match.group(2))
        else:
            id = int(re.search(r"(\d+)(?:\/\S+)?", path).group(1))
            secure_hash = request.rel_url.query.get("hash")
        return web.Response(text=await render_page(id, secure_hash), content_type='text/html')
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:
        logging.critical(e.with_traceback(None))
        raise web.HTTPInternalServerError(text=str(e))

@routes.get(r"/{path:\S+}", allow_head=True)
async def stream_handler(request: web.Request):
    try:
        path = request.match_info["path"]
        match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", path)
        if match:
            secure_hash = match.group(1)
            id = int(match.group(2))
        else:
            id = int(re.search(r"(\d+)(?:\/\S+)?", path).group(1))
            secure_hash = request.rel_url.query.get("hash")
        return await media_streamer(request, id, secure_hash)
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:
        logging.critical(e.with_traceback(None))
        raise web.HTTPInternalServerError(text=str(e))

class_cache = {}

async def media_streamer(request: web.Request, id: int, secure_hash: str):
    range_header = request.headers.get("Range", 0)
    
    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]
    
    if MULTI_CLIENT:
        logging.info(f"Client {index} is now serving {request.remote}")

    if faster_client in class_cache:
        tg_connect = class_cache[faster_client]
        logging.debug(f"Using cached ByteStreamer object for client {index}")
    else:
        logging.debug(f"Creating new ByteStreamer object for client {index}")
        tg_connect = ByteStreamer(faster_client)
        class_cache[faster_client] = tg_connect
    logging.debug("before calling get_file_properties")
    file_id = await tg_connect.get_file_properties(id)
    logging.debug("after calling get_file_properties")
    
    if file_id.unique_id[:6] != secure_hash:
        logging.debug(f"Invalid hash for message with ID {id}")
        raise InvalidHash
    
    file_size = file_id.file_size

    if range_header:
        from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
    else:
        from_bytes = request.http_range.start or 0
        until_bytes = (request.http_range.stop or file_size) - 1

    if (until_bytes > file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
        return web.Response(
            status=416,
            body="416: Range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk_size = 1024 * 1024
    until_bytes = min(until_bytes, file_size - 1)

    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = until_bytes % chunk_size + 1

    req_length = until_bytes - from_bytes + 1
    part_count = math.ceil(until_bytes / chunk_size) - math.floor(offset / chunk_size)
    body = tg_connect.yield_file(
        file_id, index, offset, first_part_cut, last_part_cut, part_count, chunk_size
    )

    mime_type = file_id.mime_type
    file_name = file_id.file_name
    disposition = "attachment"

    if mime_type:
        if not file_name:
            try:
                file_name = f"{secrets.token_hex(2)}.{mime_type.split('/')[1]}"
            except (IndexError, AttributeError):
                file_name = f"{secrets.token_hex(2)}.unknown"
    else:
        if file_name:
            mime_type = mimetypes.guess_type(file_id.file_name)
        else:
            mime_type = "application/octet-stream"
            file_name = f"{secrets.token_hex(2)}.unknown"

    return web.Response(
        status=206 if range_header else 200,
        body=body,
        headers={
            "Content-Type": f"{mime_type}",
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length": str(req_length),
            "Content-Disposition": f'{disposition}; filename="{file_name}"',
            "Accept-Ranges": "bytes",
        },
    )
