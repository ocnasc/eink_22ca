import os
import json
import uuid
import random
import pytz
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

from picture import picture_frame, resize_cover
from PIL import Image

load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY", "changeme")
API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN", "")
USERNAME = os.getenv("USERNAME", "admin")
PASSWORD = os.getenv("PASSWORD", "admin")

UPLOAD_FOLDER = "uploads"
IMAGES_FOLDER = "static/images"
DATA_FILE = "data/latest.json"
SCHEDULE_FILE = "data/schedule.json"
ALBUM_FILE = "data/album.json"
MESSAGES_FILE = "data/messages.json"
AUTO_SCHEDULER_FILE = "data/auto_scheduler.json"

for d in [UPLOAD_FOLDER, IMAGES_FOLDER, "data", "templates", "static/thumbnails"]:
    os.makedirs(d, exist_ok=True)

# ---------------------------------------------------------------------------
# App FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(title="Picture Frame")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_FOLDER), name="uploads")
templates = Jinja2Templates(directory="templates")

# ---------------------------------------------------------------------------
# Helpers JSON
# ---------------------------------------------------------------------------

def _init_json(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f, indent=2)

_init_json(ALBUM_FILE, [])
_init_json(MESSAGES_FILE, [])
_init_json(SCHEDULE_FILE, [])
_init_json(AUTO_SCHEDULER_FILE, {
    "enabled": False, "interval_hours": 1, "dark_mode": False,
    "last_photo_id": None, "last_message_id": None, "next_run": None
})

def _read_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def _write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Tempo
# ---------------------------------------------------------------------------

def get_now_gmt3():
    tz = pytz.timezone("America/Sao_Paulo")
    return datetime.now(tz)

# ---------------------------------------------------------------------------
# Versionamento
# ---------------------------------------------------------------------------

def get_next_version(today_str: str) -> str:
    if not os.path.exists(DATA_FILE):
        return f"{today_str}_1"
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        last = data.get("versao", "")
        if last.startswith(today_str):
            parts = last.split("_")
            if len(parts) >= 2:
                return f"{today_str}_{int(parts[-1]) + 1}"
    except Exception:
        pass
    return f"{today_str}_1"

def save_metadata(now, version, filename):
    data = {
        "dia": now.strftime("%Y-%m-%d"),
        "horario": now.strftime("%H:%M:%S"),
        "versao": version,
        "arquivo": filename,
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data

# ---------------------------------------------------------------------------
# Geração de imagem
# ---------------------------------------------------------------------------

def process_image_generation_from_path(foto_path, frase_superior, frase_inferior, dark_mode, raw=False):
    now = get_now_gmt3()
    today_str = now.strftime("%Y-%m-%d")
    timestamp_str = now.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{timestamp_str}.png"
    output_path = os.path.join(IMAGES_FOLDER, filename)

    if raw:
        img = Image.open(foto_path).convert("RGB")
        img = resize_cover(img, 800, 480)
        img.save(output_path, "PNG")
    else:
        picture_frame(
            foto_path=foto_path,
            frase_superior=frase_superior,
            frase_inferior=frase_inferior,
            dark_mode=dark_mode,
            output_path=output_path,
        )

    version = get_next_version(today_str)
    metadata = save_metadata(now, version, filename)
    return metadata

# ---------------------------------------------------------------------------
# Álbum de Fotos
# ---------------------------------------------------------------------------

def album_add_photo(foto_path: str, original_filename: str):
    album = _read_json(ALBUM_FILE, [])
    existing_paths = {item["path"] for item in album}
    if foto_path in existing_paths:
        return next(item for item in album if item["path"] == foto_path)
    entry = {
        "id": str(uuid.uuid4()),
        "filename": os.path.basename(foto_path),
        "original_name": original_filename,
        "path": foto_path,
        "created_at": get_now_gmt3().isoformat(),
    }
    album.append(entry)
    _write_json(ALBUM_FILE, album)
    return entry

# ---------------------------------------------------------------------------
# Agendamento manual
# ---------------------------------------------------------------------------

def save_schedule(foto_path, frase_superior, frase_inferior, dark_mode, target_time_str):
    schedule_data = _read_json(SCHEDULE_FILE, [])
    schedule_data.append({
        "foto_path": foto_path,
        "frase_superior": frase_superior,
        "frase_inferior": frase_inferior,
        "dark_mode": dark_mode,
        "target_time": target_time_str,
        "created_at": get_now_gmt3().isoformat(),
    })
    _write_json(SCHEDULE_FILE, schedule_data)

# ---------------------------------------------------------------------------
# Auto Scheduler
# ---------------------------------------------------------------------------

def _get_auto_cfg():
    return _read_json(AUTO_SCHEDULER_FILE, {
        "enabled": False, "interval_hours": 1, "dark_mode": False,
        "last_photo_id": None, "last_message_id": None, "next_run": None,
    })

def _save_auto_cfg(cfg):
    _write_json(AUTO_SCHEDULER_FILE, cfg)

def _pick_next(items, last_id):
    if not items:
        return None
    if len(items) == 1:
        return items[0]
    candidates = [i for i in items if i["id"] != last_id]
    return random.choice(candidates if candidates else items)

def _run_auto_scheduler():
    cfg = _get_auto_cfg()
    album = _read_json(ALBUM_FILE, [])
    messages = _read_json(MESSAGES_FILE, [])
    if not album or not messages:
        print("[Auto Scheduler] Álbum ou mensagens vazios, pulando.")
        return
    photo = _pick_next(album, cfg.get("last_photo_id"))
    message = _pick_next(messages, cfg.get("last_message_id"))
    if not photo or not message:
        return
    foto_path = photo["path"]
    if not os.path.exists(foto_path):
        print(f"[Auto Scheduler] Foto não encontrada: {foto_path}")
        return
    print(f"[Auto Scheduler] Foto: {photo['filename']} | Msg: {message['frase_superior']}")
    try:
        process_image_generation_from_path(
            foto_path, message["frase_superior"], message["frase_inferior"],
            cfg.get("dark_mode", False)
        )
        cfg["last_photo_id"] = photo["id"]
        cfg["last_message_id"] = message["id"]
    except Exception as e:
        print(f"[Auto Scheduler] Erro: {e}")
    now = get_now_gmt3()
    cfg["next_run"] = (now + timedelta(hours=int(cfg.get("interval_hours", 1)))).isoformat()
    _save_auto_cfg(cfg)

def scheduler_worker():
    while True:
        try:
            jobs = _read_json(SCHEDULE_FILE, [])
            if jobs:
                now_str = get_now_gmt3().strftime("%Y-%m-%dT%H:%M")
                remaining, executed = [], False
                for job in jobs:
                    if job["target_time"] <= now_str:
                        try:
                            process_image_generation_from_path(
                                job["foto_path"], job["frase_superior"],
                                job["frase_inferior"], job["dark_mode"]
                            )
                            executed = True
                        except Exception as e:
                            print(f"[Scheduler] Erro no job manual: {e}")
                    else:
                        remaining.append(job)
                if executed:
                    _write_json(SCHEDULE_FILE, remaining)

            cfg = _get_auto_cfg()
            if cfg.get("enabled"):
                next_run_str = cfg.get("next_run")
                now = get_now_gmt3()
                should_run = not next_run_str
                if not should_run:
                    try:
                        if now >= datetime.fromisoformat(next_run_str):
                            should_run = True
                    except Exception:
                        should_run = True
                if should_run:
                    _run_auto_scheduler()
        except Exception as e:
            print(f"[Scheduler Worker] Erro: {e}")
        time.sleep(30)

threading.Thread(target=scheduler_worker, daemon=True).start()

# ---------------------------------------------------------------------------
# Autenticação (sessão para web, bearer para device API)
# ---------------------------------------------------------------------------

def get_session(request: Request):
    return request.session

def require_login(request: Request):
    if not request.session.get("logged_in"):
        raise HTTPException(status_code=307, headers={"Location": "/login"})

def require_bearer(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    if auth.replace("Bearer ", "", 1).strip() != API_BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MessageBody(BaseModel):
    frase_superior: str
    frase_inferior: str = ""

class AutoSchedulerConfigBody(BaseModel):
    interval_hours: Optional[int] = None
    dark_mode: Optional[bool] = None

class SendRawBody(BaseModel):
    photo_id: str

# ---------------------------------------------------------------------------
# ROTAS WEB
# ---------------------------------------------------------------------------

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == USERNAME and password == PASSWORD:
        request.session["logged_in"] = True
        next_url = request.query_params.get("next", "/")
        return RedirectResponse(next_url, status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": "Credenciais inválidas."}, status_code=401)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def index_get(request: Request):
    if not request.session.get("logged_in"):
        return RedirectResponse("/login", status_code=303)
    now = get_now_gmt3()
    tomorrow = now + timedelta(days=1)
    schedule_time = tomorrow.replace(hour=1, minute=30, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")
    return templates.TemplateResponse(request, "index.html", {
        "image_url": None, "message": None, "preview_mode": False,
        "frase_superior": "", "frase_inferior": "",
        "dark_mode": False, "schedule_time": schedule_time, "cached_foto": "",
        "cache_bust": int(get_now_gmt3().timestamp()),
    })

@app.post("/", response_class=HTMLResponse)
async def index_post(
    request: Request,
    action: str = Form(...),
    frase_superior: str = Form(""),
    frase_inferior: str = Form(""),
    dark_mode: bool = Form(False),
    schedule_time: str = Form(""),
    cached_foto: str = Form(""),
    album_photo_id: str = Form(""),
    foto: Optional[UploadFile] = File(None),
):
    if not request.session.get("logged_in"):
        return RedirectResponse("/login", status_code=303)

    image_url = None
    msg = None
    preview_mode = False
    foto_path = ""

    # Resolver foto
    if foto and foto.filename:
        filename = secure_filename(foto.filename)
        foto_path = os.path.join(UPLOAD_FOLDER, filename)
        content = await foto.read()
        with open(foto_path, "wb") as f:
            f.write(content)
        cached_foto = filename
        album_add_photo(foto_path, foto.filename)
    elif album_photo_id:
        album = _read_json(ALBUM_FILE, [])
        found = next((p for p in album if p["id"] == album_photo_id), None)
        if found:
            foto_path = found["path"]
            cached_foto = found["filename"]
    elif cached_foto:
        foto_path = os.path.join(UPLOAD_FOLDER, cached_foto)

    if not foto_path or not os.path.exists(foto_path):
        msg = "Por favor, envie uma foto ou selecione uma do álbum."
    elif action == "preview":
        output_path = os.path.join(IMAGES_FOLDER, "preview.png")
        try:
            picture_frame(foto_path, frase_superior, frase_inferior,
                          dark_mode=dark_mode, output_path=output_path)
            image_url = "/static/images/preview.png"
            preview_mode = True
        except Exception as e:
            msg = f"Erro ao gerar preview: {e}"
    elif action == "schedule" and schedule_time:
        save_schedule(foto_path, frase_superior, frase_inferior, dark_mode, schedule_time)
        msg = f"Agendado para {schedule_time}!"
    elif action == "instant":
        try:
            metadata = process_image_generation_from_path(foto_path, frase_superior, frase_inferior, dark_mode)
            image_url = f"/static/images/{metadata['arquivo']}"
            msg = "Imagem enviada com sucesso!"
        except Exception as e:
            msg = f"Erro ao enviar: {e}"
    elif action == "send_raw":
        try:
            metadata = process_image_generation_from_path(foto_path, "", "", False, raw=True)
            image_url = f"/static/images/{metadata['arquivo']}"
            msg = "Foto enviada diretamente (sem overlay)!"
        except Exception as e:
            msg = f"Erro ao enviar foto direta: {e}"

    return templates.TemplateResponse(request, "index.html", {
        "image_url": image_url, "message": msg, "preview_mode": preview_mode,
        "frase_superior": frase_superior, "frase_inferior": frase_inferior,
        "dark_mode": dark_mode, "schedule_time": schedule_time, "cached_foto": cached_foto,
        "cache_bust": int(get_now_gmt3().timestamp()),
    })

# ---------------------------------------------------------------------------
# API — Álbum de Fotos (RF01)
# ---------------------------------------------------------------------------

@app.get("/api/album")
async def api_album_list(request: Request, _=Depends(require_login)):
    return {"ok": True, "photos": _read_json(ALBUM_FILE, [])}

@app.post("/api/album", status_code=201)
async def api_album_add(request: Request, foto: UploadFile = File(...), _=Depends(require_login)):
    filename = secure_filename(foto.filename)
    foto_path = os.path.join(UPLOAD_FOLDER, filename)
    content = await foto.read()
    with open(foto_path, "wb") as f:
        f.write(content)
    entry = album_add_photo(foto_path, foto.filename)
    return {"ok": True, "photo": entry}

@app.delete("/api/album/{photo_id}")
async def api_album_delete(photo_id: str, request: Request, _=Depends(require_login)):
    album = _read_json(ALBUM_FILE, [])
    entry = next((p for p in album if p["id"] == photo_id), None)
    if not entry:
        raise HTTPException(404, "Foto não encontrada")
    if os.path.exists(entry["path"]):
        try:
            os.remove(entry["path"])
        except Exception:
            pass
    _write_json(ALBUM_FILE, [p for p in album if p["id"] != photo_id])
    return {"ok": True}

# ---------------------------------------------------------------------------
# API — Álbum de Mensagens (RF06)
# ---------------------------------------------------------------------------

@app.get("/api/messages")
async def api_messages_list(request: Request, _=Depends(require_login)):
    return {"ok": True, "messages": _read_json(MESSAGES_FILE, [])}

@app.post("/api/messages", status_code=201)
async def api_messages_add(body: MessageBody, request: Request, _=Depends(require_login)):
    if not body.frase_superior.strip():
        raise HTTPException(400, "frase_superior é obrigatória")
    messages = _read_json(MESSAGES_FILE, [])
    entry = {
        "id": str(uuid.uuid4()),
        "frase_superior": body.frase_superior.strip(),
        "frase_inferior": body.frase_inferior.strip(),
        "created_at": get_now_gmt3().isoformat(),
    }
    messages.append(entry)
    _write_json(MESSAGES_FILE, messages)
    return {"ok": True, "message": entry}

@app.delete("/api/messages/{message_id}")
async def api_messages_delete(message_id: str, request: Request, _=Depends(require_login)):
    messages = _read_json(MESSAGES_FILE, [])
    if not any(m["id"] == message_id for m in messages):
        raise HTTPException(404, "Mensagem não encontrada")
    _write_json(MESSAGES_FILE, [m for m in messages if m["id"] != message_id])
    return {"ok": True}

# ---------------------------------------------------------------------------
# API — Auto Scheduler (RF02 + RF04 + RF07)
# ---------------------------------------------------------------------------

@app.get("/api/auto-scheduler/status")
async def api_auto_scheduler_status(request: Request, _=Depends(require_login)):
    return {"ok": True, "config": _get_auto_cfg()}

@app.post("/api/auto-scheduler/toggle")
async def api_auto_scheduler_toggle(request: Request, _=Depends(require_login)):
    cfg = _get_auto_cfg()
    cfg["enabled"] = not cfg.get("enabled", False)
    if cfg["enabled"] and not cfg.get("next_run"):
        cfg["next_run"] = get_now_gmt3().isoformat()
    _save_auto_cfg(cfg)
    return {"ok": True, "enabled": cfg["enabled"]}

@app.post("/api/auto-scheduler/config")
async def api_auto_scheduler_config(body: AutoSchedulerConfigBody, request: Request, _=Depends(require_login)):
    cfg = _get_auto_cfg()
    if body.interval_hours is not None:
        cfg["interval_hours"] = max(1, body.interval_hours)
    if body.dark_mode is not None:
        cfg["dark_mode"] = body.dark_mode
    _save_auto_cfg(cfg)
    return {"ok": True, "config": cfg}

# ---------------------------------------------------------------------------
# API — Envio direto sem overlay (RF03)
# ---------------------------------------------------------------------------

@app.post("/api/send-raw")
async def api_send_raw_upload(
    request: Request,
    foto: Optional[UploadFile] = File(None),
    _=Depends(require_login),
):
    foto_path = ""
    if foto and foto.filename:
        filename = secure_filename(foto.filename)
        foto_path = os.path.join(UPLOAD_FOLDER, filename)
        content = await foto.read()
        with open(foto_path, "wb") as f:
            f.write(content)
        album_add_photo(foto_path, foto.filename)

    if not foto_path:
        # Tenta ler photo_id do corpo JSON
        try:
            body = await request.json()
            photo_id = body.get("photo_id", "")
        except Exception:
            photo_id = ""
        if photo_id:
            album = _read_json(ALBUM_FILE, [])
            found = next((p for p in album if p["id"] == photo_id), None)
            if found:
                foto_path = found["path"]

    if not foto_path or not os.path.exists(foto_path):
        raise HTTPException(400, "Foto não encontrada")

    try:
        metadata = process_image_generation_from_path(foto_path, "", "", False, raw=True)
        return {"ok": True, "data": metadata}
    except Exception as e:
        raise HTTPException(500, str(e))

# ---------------------------------------------------------------------------
# API — Geração com overlay
# ---------------------------------------------------------------------------

@app.post("/api/generate")
async def api_generate(
    request: Request,
    foto: UploadFile = File(...),
    frase_superior: str = Form(""),
    frase_inferior: str = Form(""),
    dark_mode: str = Form("false"),
    _=Depends(require_login),
):
    filename = secure_filename(foto.filename)
    foto_path = os.path.join(UPLOAD_FOLDER, filename)
    content = await foto.read()
    with open(foto_path, "wb") as f:
        f.write(content)
    try:
        metadata = process_image_generation_from_path(
            foto_path, frase_superior, frase_inferior, dark_mode.lower() == "true"
        )
        return {"ok": True, "versao": metadata["versao"], "data": metadata}
    except Exception as e:
        raise HTTPException(500, str(e))

# ---------------------------------------------------------------------------
# API — Status e Imagem (RF08 — inalteradas)
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def api_status(request: Request, _=Depends(require_bearer)):
    if not os.path.exists(DATA_FILE):
        return {"disponivel": False}
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        return {"disponivel": True, **data}
    except Exception as e:
        return {"disponivel": False, "error": str(e)}

@app.get("/api/image")
async def api_image(request: Request, _=Depends(require_bearer)):
    if not os.path.exists(DATA_FILE):
        raise HTTPException(404, "Nenhuma imagem disponível")
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        filepath = os.path.join(IMAGES_FOLDER, data["arquivo"])
        return FileResponse(filepath, media_type="image/png")
    except Exception as e:
        raise HTTPException(500, str(e))
