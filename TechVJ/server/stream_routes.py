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
    docs = list(reversed(docs))

    # Fixed poster image for all cards - using external URL with fallback
    fixed_poster_url = "https://i.ibb.co/BKTjCkG3/image.png"

    # Prepare card data with file link
    files_data = []
    for i, doc in enumerate(docs):
        if "file_id" in doc:
            file_link = f"https://t.me/NewRan_bot?start={doc['file_id']}"
            files_data.append({
                "title": f"⭕<b>{i+1}</b>: New Video",
                "url": file_link,
                "poster": fixed_poster_url
            })

    # Convert to JS array string
    cards_js_array = "[" + ",".join([f'{{"title":"{f["title"]}","url":"{f["url"]}","poster":"{f["poster"]}"}}' for f in files_data]) + "]"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8">
        <title>⭕ Premium Video Collection</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
          * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
          }}

          body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0c0c0c 0%, #1a1a1a 100%);
            color: #ffffff;
            min-height: 100vh;
            overflow-x: hidden;
          }}

          /* Animated background particles */
          .bg-particles {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: -1;
          }}

          .particle {{
            position: absolute;
            background: rgba(229, 9, 20, 0.1);
            border-radius: 50%;
            animation: float 20s infinite linear;
          }}

          @keyframes float {{
            0% {{ transform: translateY(100vh) rotate(0deg); opacity: 0; }}
            10% {{ opacity: 1; }}
            90% {{ opacity: 1; }}
            100% {{ transform: translateY(-100vh) rotate(360deg); opacity: 0; }}
          }}

          /* Header */
          .header {{
            background: linear-gradient(135deg, #e50914 0%, #b0060f 100%);
            padding: 25px 20px;
            text-align: center;
            box-shadow: 0 4px 20px rgba(229, 9, 20, 0.3);
            position: relative;
            overflow: hidden;
          }}

          .header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            animation: shine 3s infinite;
          }}

          @keyframes shine {{
            0% {{ left: -100%; }}
            100% {{ left: 100%; }}
          }}

          .header h1 {{
            font-size: clamp(24px, 4vw, 32px);
            font-weight: 700;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
            position: relative;
            z-index: 1;
          }}

          .header .subtitle {{
            font-size: 16px;
            opacity: 0.9;
            margin-top: 8px;
            font-weight: 300;
          }}

          /* Stats bar */
          .stats-bar {{
            background: rgba(30, 30, 30, 0.9);
            padding: 15px 20px;
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(229, 9, 20, 0.2);
          }}

          .stat-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            color: #cccccc;
          }}

          .stat-item i {{
            color: #e50914;
            font-size: 16px;
          }}

          /* Grid container */
          .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 30px 20px;
          }}

          .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
          }}

          @media (min-width: 480px) {{
            .grid {{ grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }}
          }}
          @media (min-width: 768px) {{
            .grid {{ grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }}
          }}
          @media (min-width: 1024px) {{
            .grid {{ grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }}
          }}
          @media (min-width: 1200px) {{
            .grid {{ grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }}
          }}

          /* Card styling */
          .card {{
            background: linear-gradient(145deg, #1e1e1e 0%, #2a2a2a 100%);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 
              0 8px 32px rgba(0, 0, 0, 0.3),
              0 0 0 1px rgba(255, 255, 255, 0.05);
            cursor: pointer;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            position: relative;
            transform-origin: center;
          }}

          .card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(229, 9, 20, 0.1) 0%, transparent 50%);
            opacity: 0;
            transition: opacity 0.3s ease;
            z-index: 1;
          }}

          .card:hover {{
            transform: translateY(-12px) scale(1.03);
            box-shadow: 
              0 20px 40px rgba(229, 9, 20, 0.2),
              0 0 0 1px rgba(229, 9, 20, 0.3);
          }}

          .card:hover::before {{
            opacity: 1;
          }}

          .card:active {{
            transform: translateY(-8px) scale(1.01);
          }}

          /* Poster styling */
          .poster {{
            width: 100%;
            height: 200px;
            background-size: cover;
            background-position: center;
            background-color: #333;
            background-repeat: no-repeat;
            position: relative;
            overflow: hidden;
            /* Add fallback for failed image loads */
            background-image: linear-gradient(135deg, #e50914 0%, #b0060f 100%);
          }}

          .poster.loaded {{
            background-image: var(--poster-url);
          }}

          .poster::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 50%;
            background: linear-gradient(transparent, rgba(0,0,0,0.8));
          }}

          .play-overlay {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 60px;
            height: 60px;
            background: rgba(229, 9, 20, 0.9);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: all 0.3s ease;
            z-index: 2;
          }}

          .play-overlay i {{
            color: white;
            font-size: 24px;
            margin-left: 3px;
          }}

          .card:hover .play-overlay {{
            opacity: 1;
            transform: translate(-50%, -50%) scale(1.1);
          }}

          /* Card info */
          .info {{
            padding: 20px;
            text-align: center;
            position: relative;
          }}

          .info h3 {{
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 8px;
            line-height: 1.4;
            color: #ffffff;
          }}

          .info .meta {{
            display: flex;
            justify-content: center;
            gap: 15px;
            font-size: 12px;
            color: #888;
            margin-top: 8px;
          }}

          .info .meta span {{
            display: flex;
            align-items: center;
            gap: 4px;
          }}

          /* Load more button */
          .load-more-container {{
            display: flex;
            justify-content: center;
            margin: 40px 0;
          }}

          .btn {{
            background: linear-gradient(135deg, #e50914 0%, #b0060f 100%);
            color: white;
            border: none;
            padding: 16px 40px;
            border-radius: 50px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(229, 9, 20, 0.3);
            position: relative;
            overflow: hidden;
          }}

          .btn::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
          }}

          .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(229, 9, 20, 0.4);
          }}

          .btn:hover::before {{
            left: 100%;
          }}

          .btn:active {{
            transform: translateY(0);
          }}

          .btn:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
          }}

          /* Loading animation */
          .loading {{
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 1s ease-in-out infinite;
            margin-right: 8px;
          }}

          @keyframes spin {{
            to {{ transform: rotate(360deg); }}
          }}

          /* Responsive adjustments */
          @media (max-width: 480px) {{
            .header {{
              padding: 20px 15px;
            }}
            .container {{
              padding: 20px 15px;
            }}
            .grid {{
              gap: 15px;
              grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            }}
            .card {{
              border-radius: 12px;
            }}
            .poster {{
              height: 150px;
            }}
            .info {{
              padding: 15px;
            }}
            .stats-bar {{
              gap: 20px;
              padding: 12px 15px;
            }}
          }}

          /* Scroll animations */
          .fade-in {{
            opacity: 0;
            transform: translateY(30px);
            transition: all 0.6s ease;
          }}

          .fade-in.visible {{
            opacity: 1;
            transform: translateY(0);
          }}

          /* Custom scrollbar */
          ::-webkit-scrollbar {{
            width: 8px;
          }}

          ::-webkit-scrollbar-track {{
            background: #1a1a1a;
          }}

          ::-webkit-scrollbar-thumb {{
            background: linear-gradient(135deg, #e50914, #b0060f);
            border-radius: 4px;
          }}

          ::-webkit-scrollbar-thumb:hover {{
            background: linear-gradient(135deg, #b0060f, #e50914);
          }}
        </style>
      </head>
      <body>
        <!-- Background particles -->
        <div class="bg-particles" id="particles"></div>

        <!-- Header -->
        <div class="header">
          <h1><i class="fas fa-play-circle"></i> Premium Video Collection</h1>
          <div class="subtitle">Discover amazing content</div>
        </div>

        <!-- Stats bar -->
        <div class="stats-bar">
          <div class="stat-item">
            <i class="fas fa-video"></i>
            <span id="total-videos">0 Videos</span>
          </div>
          <div class="stat-item">
            <i class="fas fa-eye"></i>
            <span>HD Quality</span>
          </div>
          <div class="stat-item">
            <i class="fas fa-clock"></i>
            <span>Updated Daily</span>
          </div>
        </div>

        <!-- Main container -->
        <div class="container">
          <div class="grid" id="file-grid"></div>
          
          <div class="load-more-container">
            <button class="btn" id="load-more-btn" onclick="loadMore()">
              <i class="fas fa-plus"></i> Load More Videos
            </button>
          </div>
        </div>

        <script>
          const files = {cards_js_array};
          let currentIndex = 0;
          const perPage = 12;
          let isLoading = false;

          // Update total videos count
          document.getElementById('total-videos').textContent = `${{files.length}} Videos`;

          // Create background particles
          function createParticles() {{
            const container = document.getElementById('particles');
            const particleCount = 15;
            
            for (let i = 0; i < particleCount; i++) {{
              const particle = document.createElement('div');
              particle.className = 'particle';
              particle.style.left = Math.random() * 100 + '%';
              particle.style.width = particle.style.height = (Math.random() * 4 + 2) + 'px';
              particle.style.animationDelay = Math.random() * 20 + 's';
              particle.style.animationDuration = (Math.random() * 10 + 15) + 's';
              container.appendChild(particle);
            }}
          }}

          // Load more function with animation
          function loadMore() {{
            if (isLoading) return;
            
            isLoading = true;
            const btn = document.getElementById('load-more-btn');
            const originalText = btn.innerHTML;
            btn.innerHTML = '<div class="loading"></div>Loading...';
            btn.disabled = true;

            // Simulate loading delay for better UX
            setTimeout(() => {{
              const grid = document.getElementById("file-grid");
              const nextFiles = files.slice(currentIndex, currentIndex + perPage);
              
              nextFiles.forEach((f, index) => {{
                setTimeout(() => {{
                  const card = document.createElement("div");
                  card.className = "card fade-in";
                  card.onclick = () => window.open(f.url, "_blank");
                  
                  const poster = document.createElement("div");
                  poster.className = "poster";
                  poster.style.setProperty('--poster-url', `url('${{f.poster}}')`);
                  
                  // Test if image loads successfully
                  const img = new Image();
                  img.onload = () => {{
                    poster.classList.add('loaded');
                  }};
                  img.onerror = () => {{
                    // Fallback to gradient background if image fails
                    console.warn('Failed to load poster image:', f.poster);
                    poster.style.backgroundImage = 'linear-gradient(135deg, #e50914 0%, #b0060f 100%)';
                    // Add a video icon as fallback
                    poster.innerHTML = '<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 48px; color: rgba(255,255,255,0.7);"><i class="fas fa-video"></i></div>';
                  }};
                  img.src = f.poster;
                  
                  const playOverlay = document.createElement("div");
                  playOverlay.className = "play-overlay";
                  playOverlay.innerHTML = '<i class="fas fa-play"></i>';
                  
                  poster.appendChild(playOverlay);
                  
                  card.innerHTML = `
                    <div class="info">
                      <h3>${{f.title}}</h3>
                      <div class="meta">
                        <span><i class="fas fa-hd-video"></i> HD</span>
                        <span><i class="fas fa-star"></i> Premium</span>
                      </div>
                    </div>
                  `;
                  
                  card.insertBefore(poster, card.firstChild);
                  grid.appendChild(card);
                  
                  // Trigger animation
                  setTimeout(() => {{
                    card.classList.add('visible');
                  }}, 50);
                }}, index * 100);
              }});

              currentIndex += perPage;
              
              setTimeout(() => {{
                if (currentIndex >= files.length) {{
                  btn.innerHTML = '<i class="fas fa-check"></i> All Videos Loaded';
                  btn.disabled = true;
                }} else {{
                  btn.innerHTML = originalText;
                  btn.disabled = false;
                }}
                isLoading = false;
              }}, nextFiles.length * 100 + 500);
            }}, 800);
          }}

          // Intersection Observer for scroll animations
          const observerOptions = {{
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
          }};

          const observer = new IntersectionObserver((entries) => {{
            entries.forEach(entry => {{
              if (entry.isIntersecting) {{
                entry.target.classList.add('visible');
              }}
            }});
          }}, observerOptions);

          // Initialize
          document.addEventListener('DOMContentLoaded', () => {{
            createParticles();
            loadMore();
          }});

          // Auto-load on scroll (optional)
          let autoLoadEnabled = true;
          window.addEventListener('scroll', () => {{
            if (autoLoadEnabled && !isLoading && currentIndex < files.length) {{
              const scrollPercent = (window.scrollY + window.innerHeight) / document.body.scrollHeight;
              if (scrollPercent > 0.8) {{
                autoLoadEnabled = false;
                setTimeout(() => autoLoadEnabled = true, 2000);
              }}
            }}
          }});
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
