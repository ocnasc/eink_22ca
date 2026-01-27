from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, flash
import os
import json
import pytz
import threading
import time
from datetime import datetime, timedelta
from functools import wraps
from picture import picture_frame
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv(override=True)

app = Flask(__name__)
# Configura o Flask para confiar nos headers de proxy (Nginx/Apache)
# Isso corrige os redirecionamentos para usar o domínio correto e HTTPS se disponível
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# --- URGENT: Security Configuration ---
# You MUST change this secret key for production.
# Use a long, random string. You can generate one with:
# python -c "import os; print(os.urandom(24))"
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
API_BEARER_TOKEN = os.getenv("API_BEARER_TOKEN")

# Simple hardcoded credentials.
# For better security, use environment variables in a real deployment.
USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD') # <-- IMPORTANT: Change this password!

# Configurações de diretórios
UPLOAD_FOLDER = "uploads"
IMAGES_FOLDER = "static/images"
DATA_FILE = "data/latest.json"
SCHEDULE_FILE = "data/schedule.json"

# Garantir que diretórios existam
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(IMAGES_FOLDER, exist_ok=True)
os.makedirs("data", exist_ok=True)
os.makedirs("templates", exist_ok=True) # Ensure templates folder exists

# --- Authentication ---

def bearer_token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({
                "ok": False,
                "error": "Missing or invalid Authorization header"
            }), 401

        token = auth_header.replace("Bearer ", "", 1).strip()

        if token != API_BEARER_TOKEN:
            return jsonify({
                "ok": False,
                "error": "Invalid token"
            }), 401

        return f(*args, **kwargs)
    return decorated


def login_required(f):
    """Decorator to protect routes that require a logged-in user."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            # For API requests, return a JSON error instead of redirecting
            if request.path.startswith('/api/'):
                return jsonify({"ok": False, "error": "Authentication required"}), 401
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            next_url = request.args.get('next')
            flash('You were successfully logged in!', 'success')
            return redirect(next_url or url_for('index'))
        else:
            flash('Invalid credentials. Please try again.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

def get_now_gmt3():
    """Retorna data e hora atual em GMT-3"""
    tz = pytz.timezone('America/Sao_Paulo')
    return datetime.now(tz)

def get_next_version(today_str):
    """Calcula a próxima versão baseada no dia atual e histórico"""
    if not os.path.exists(DATA_FILE):
        return f"{today_str}_1"
    
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            last_version = data.get('versao', '')
            
            # Se a última versão for do mesmo dia
            if last_version.startswith(today_str):
                parts = last_version.split('_')
                if len(parts) >= 2:
                    current_idx = int(parts[-1])
                    return f"{today_str}_{current_idx + 1}"
    except Exception as e:
        print(f"Erro ao ler versão anterior: {e}")
        
    # Se mudou o dia ou erro, reinicia contagem para o dia
    return f"{today_str}_1"

def save_metadata(now, version, filename):
    """Salva o estado atual no JSON"""
    data = {
        "dia": now.strftime("%Y-%m-%d"),
        "horario": now.strftime("%H:%M:%S"),
        "versao": version,
        "arquivo": filename
    }
    
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    return data

def process_image_generation_from_path(foto_path, frase_superior, frase_inferior, dark_mode):
    """Lógica central de geração da imagem a partir de um patch já salvo"""
    now = get_now_gmt3()
    today_str = now.strftime("%Y-%m-%d")
    timestamp_str = now.strftime("%Y-%m-%d_%H-%M-%S")
    
    # Nome do arquivo final
    filename = f"{timestamp_str}.png"
    output_path = os.path.join(IMAGES_FOLDER, filename)
    
    # Gerar imagem
    picture_frame(
        foto_path=foto_path,
        frase_superior=frase_superior,
        frase_inferior=frase_inferior,
        dark_mode=dark_mode,
        output_path=output_path
    )
    
    # Determinar versão
    version = get_next_version(today_str)
    
    # Atualizar metadata
    metadata = save_metadata(now, version, filename)
    
    return metadata

def save_schedule(foto_path, frase_superior, frase_inferior, dark_mode, target_time_str):
    """Adiciona um job no agendamento"""
    schedule_data = []
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, 'r') as f:
                schedule_data = json.load(f)
        except:
            schedule_data = []

    job = {
        "foto_path": foto_path,
        "frase_superior": frase_superior,
        "frase_inferior": frase_inferior,
        "dark_mode": dark_mode,
        "target_time": target_time_str, # Formato ISO-ish
        "created_at": get_now_gmt3().isoformat()
    }
    
    schedule_data.append(job)
    
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(schedule_data, f, indent=2)

def scheduler_worker():
    """Background worker para verificar agendamentos"""
    while True:
        try:
            if os.path.exists(SCHEDULE_FILE):
                with open(SCHEDULE_FILE, 'r') as f:
                    jobs = json.load(f)
                
                if not jobs:
                    time.sleep(10)
                    continue

                now_str = get_now_gmt3().strftime("%Y-%m-%dT%H:%M")
                remaining_jobs = []
                job_executed = False

                for job in jobs:
                    # Comparação simples de string ISO (YYYY-MM-DDTHH:MM)
                    # Se target_time <= now_str, executa
                    if job["target_time"] <= now_str:
                        print(f"Executando agendamento: {job['target_time']}")
                        try:
                            process_image_generation_from_path(
                                job["foto_path"],
                                job["frase_superior"],
                                job["frase_inferior"],
                                job["dark_mode"]
                            )
                            job_executed = True
                        except Exception as e:
                            print(f"Erro ao executar job: {e}")
                    else:
                        remaining_jobs.append(job)
                
                if job_executed:
                    with open(SCHEDULE_FILE, 'w') as f:
                        json.dump(remaining_jobs, f, indent=2)

        except Exception as e:
            print(f"Erro no scheduler: {e}")
        
        time.sleep(30) # Verifica a cada 30s

# Iniciar Thread do Scheduler
scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
scheduler_thread.start()

# --- Rotas da Web ---

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    image_url = None
    message = None
    preview_mode = False

    # Valores padrão para o formulário (para manter os dados preenchidos)
    form_data = {
        "frase_superior": "",
        "frase_inferior": "",
        "dark_mode": False,
        "schedule_time": "",
        "cached_foto": ""
    }

    # Calcular horário padrão apenas se for GET (primeiro acesso)
    if request.method == "GET":
        now = get_now_gmt3()
        tomorrow = now + timedelta(days=1)
        default_date = tomorrow.replace(hour=1, minute=30, second=0, microsecond=0)
        form_data["schedule_time"] = default_date.strftime("%Y-%m-%dT%H:%M")

    if request.method == "POST":
        action = request.form.get("action")
        
        # Capturar dados do formulário para repopular a tela
        form_data["frase_superior"] = request.form.get("frase_superior", "")
        form_data["frase_inferior"] = request.form.get("frase_inferior", "")
        form_data["dark_mode"] = "dark_mode" in request.form
        form_data["schedule_time"] = request.form.get("schedule_time", "")
        form_data["cached_foto"] = request.form.get("cached_foto", "")

        # Lógica de Upload de Arquivo (Novo ou Cache)
        foto = request.files.get("foto")
        foto_path = ""

        if foto and foto.filename:
            # Novo upload
            filename = foto.filename
            foto_path = os.path.join(UPLOAD_FOLDER, filename)
            foto.save(foto_path)
            form_data["cached_foto"] = filename # Atualiza cache
        elif form_data["cached_foto"]:
            # Usa foto anterior (cache)
            foto_path = os.path.join(UPLOAD_FOLDER, form_data["cached_foto"])

        # Processar Ações
        if not foto_path or not os.path.exists(foto_path):
            message = "Por favor, envie uma foto."
        
        elif action == "preview":
            # Gera imagem temporária para visualização
            output_path = os.path.join(IMAGES_FOLDER, "preview.png")
            try:
                picture_frame(foto_path, form_data["frase_superior"], form_data["frase_inferior"], 
                              dark_mode=form_data["dark_mode"], output_path=output_path)
                image_url = "/static/images/preview.png"
                preview_mode = True
            except Exception as e:
                message = f"Erro ao gerar preview: {e}"

        elif action == "schedule" and form_data["schedule_time"]:
            save_schedule(foto_path, form_data["frase_superior"], form_data["frase_inferior"], 
                          form_data["dark_mode"], form_data["schedule_time"])
            message = f"Agendado com sucesso para {form_data['schedule_time']}!"
        
        elif action == "instant":
            try:
                metadata = process_image_generation_from_path(foto_path, form_data["frase_superior"], 
                                                              form_data["frase_inferior"], form_data["dark_mode"])
                image_url = f"/static/images/{metadata['arquivo']}"
                message = "Imagem enviada com sucesso!"
            except Exception as e:
                message = f"Erro ao enviar: {e}"

    return render_template("index.html", image_url=image_url, message=message, preview_mode=preview_mode, **form_data)

# --- Endpoints da API ---

@app.route("/api/generate", methods=["POST"])
@login_required
def api_generate():
    if "foto" not in request.files:
        return jsonify({"error": "Nenhuma foto enviada"}), 400
        
    foto = request.files["foto"]
    frase_superior = request.form.get("frase_superior", "")
    frase_inferior = request.form.get("frase_inferior", "")
    dark_mode_val = request.form.get("dark_mode", "false")
    dark_mode = str(dark_mode_val).lower() == "true"
    
    try:
        foto_path = os.path.join(UPLOAD_FOLDER, foto.filename)
        foto.save(foto_path)
        
        metadata = process_image_generation_from_path(foto_path, frase_superior, frase_inferior, dark_mode)
        return jsonify({
            "ok": True,
            "versao": metadata["versao"],
            "data": metadata
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/status", methods=["GET"])
@bearer_token_required
def api_status():
    if not os.path.exists(DATA_FILE):
        return jsonify({"disponivel": False})
    
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        return jsonify({"disponivel": True, **data})
    except Exception as e:
        return jsonify({"disponivel": False, "error": str(e)})

@app.route("/api/image", methods=["GET"])
@bearer_token_required  
def api_image():
    if not os.path.exists(DATA_FILE):
        return jsonify({"error": "Nenhuma imagem disponível"}), 404
        
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        
        filename = data["arquivo"]
        return send_from_directory(IMAGES_FOLDER, filename, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
