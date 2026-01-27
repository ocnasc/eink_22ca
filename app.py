from flask import Flask, request, jsonify, send_from_directory
import os
import json
from functools import wraps
from dotenv import load_dotenv

load_dotenv(override=True)

app = Flask(__name__)

# --- Configuration ---
IMAGES_FOLDER = "static/images"
DATA_FILE = "data/latest.json"
BEARER_TOKEN = os.getenv('BEARER_TOKEN')

# --- Authentication ---

def token_required(f):
    """Decorator to protect routes that require a bearer token."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            try:
                auth_header = request.headers['Authorization']
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({"ok": False, "error": "Bearer token malformed"}), 401

        if not token:
            return jsonify({"ok": False, "error": "Token is missing", "headers": request.headers}), 401
        
        if token != BEARER_TOKEN:
            return jsonify({"ok": False, "error": "Token is invalid"}), 401

        return f(*args, **kwargs)
    return decorated_function


# --- API Endpoints ---

@app.route("/api/image/available", methods=["GET"])
@token_required
def api_status():
    """
    Checks if a new image is available by looking for the metadata file.
    Returns the latest image metadata if available.
    """
    if not os.path.exists(DATA_FILE):
        return jsonify({"available": False})
    
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        return jsonify({"available": True, **data})
    except Exception as e:
        return jsonify({"available": False, "error": str(e)})

@app.route("/api/image", methods=["GET"])
@token_required
def api_image():
    """
    Serves the latest image file based on the metadata file.
    """
    if not os.path.exists(DATA_FILE):
        return jsonify({"error": "No image available"}), 404
        
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        
        filename = data["arquivo"]
        return send_from_directory(IMAGES_FOLDER, filename, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Ensure required directories exist
    os.makedirs(IMAGES_FOLDER, exist_ok=True)
    os.makedirs("data", exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)