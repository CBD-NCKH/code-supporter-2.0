from transformers import AutoModelForCausalLM, AutoTokenizer
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import hashlib
import torch
import os
import shutil
import requests
import json

model_files = {
    "pytorch_model.bin": "https://drive.google.com/uc?id=1-0BV5iou95zjdb_8Z7i4CjEEV-i-fanq",
    "config.json": "https://drive.google.com/uc?id=1-4rrSduBQZwlN0hx3v4VLH-bBAcrGzxp",
    "generation_config.json": "https://drive.google.com/uc?id=1-4V1REaRUNlKvVxpXwsM8dxxXxHWk2cx"
}

tokenizer_files = {
    "tokenizer.json": "https://drive.google.com/uc?id=1-6ofOPq5hd-yF64bq63kVJSzmNvo9zZK",
    "vocab.json": "https://drive.google.com/uc?id=1-8Bb9A1vPFkD7vv2-VvEd58l-AAAkV8C",
    "merges.txt": "https://drive.google.com/uc?id=1-86WGPueqxTPEapQF7VMkXN73KTrQHXw",
    "tokenizer_config.json": "https://drive.google.com/uc?id=1-FD9bAkuuqTm7KIlL0NGmhNXdF8cm-yD",
    "added_tokens.json": "https://drive.google.com/uc?id=1-EyYAhw8HQOFfJQ0umbqNreL-kfA1BHt",
    "special_tokens_map.json": "https://drive.google.com/uc?id=1-FD4ONSG8jhSxwfmI1b-W5PoHrH6j8YP"
}

tokenizer = None
model = None

def download_file_from_google_drive(file_url, output):
    print(f"Downloading {output} from {file_url}...")
    response = requests.get(file_url, stream=True)
    if response.status_code == 200:
        with open(output, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"✅ Downloaded: {output}")
    else:
        print(f"❌ Failed to download {output}: {response.status_code}")

def check_and_download_files():
    if os.path.exists("./qwen_int4_model"):
        print("⚠️ Clearing existing model directory...")
        shutil.rmtree("./qwen_int4_model")

    print("🔍 Checking and downloading model files if necessary...")
    os.makedirs("./qwen_int4_model/model", exist_ok=True)
    for file_name, file_url in model_files.items():
        output_path = f"./qwen_int4_model/model/{file_name}"
        if not os.path.exists(output_path):
            download_file_from_google_drive(file_url, output_path)

    os.makedirs("./qwen_int4_model/tokenizer", exist_ok=True)
    for file_name, file_url in tokenizer_files.items():
        output_path = f"./qwen_int4_model/tokenizer/{file_name}"
        if not os.path.exists(output_path):
            download_file_from_google_drive(file_url, output_path)

def initialize_model():
    global tokenizer, model
    if tokenizer is None or model is None:
        print("Initializing model...")
        tokenizer = AutoTokenizer.from_pretrained("./qwen_int4_model/tokenizer")
        model = AutoModelForCausalLM.from_pretrained(
            "./qwen_int4_model/model",
            torch_dtype=torch.float16
        )
        print("✅ Model loaded into RAM.")

def connect_google_sheet(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json is None:
        raise ValueError("GOOGLE_CREDENTIALS_JSON environment variable is not set.")
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(sheet_name).sheet1

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_account(sheet, username, password):
    users = sheet.get_all_values()
    for row in users:
        if len(row) >= 1 and row[0] == username:
            return False, "Username already exists."
    sheet.append_row([username, hash_password(password), "", ""])
    return True, "Account created successfully."

def authenticate_user(sheet, username, password):
    users = sheet.get_all_values()
    for row in users:
        if len(row) >= 2 and row[0] == username and row[1] == hash_password(password):
            return True
    return False

def generate_response_qwen(prompt, max_length=5000):
    try:
        messages = [
            {"role": "system", "content": "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
        generated_ids = model.generate(**model_inputs, max_new_tokens=max_length)
        generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)]
        return tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    except Exception as e:
        return f"Error generating response: {e}"

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "*"}})

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['GET'])
def chat():
    username = request.args.get("username")
    if not username:
        return "Missing username parameter", 400  
    return render_template("chat.html", username=username)

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    sheet = connect_google_sheet("CodesupporterHistory")
    success, message = create_account(sheet, data.get("username"), data.get("password"))
    return jsonify({"redirect_url": f"/chat?username={data.get('username')}"}) if success else jsonify({"error": message}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    sheet = connect_google_sheet("CodesupporterHistory")
    return jsonify({"redirect_url": f"/chat?username={data.get('username')}"}) if authenticate_user(sheet, data.get("username"), data.get("password")) else jsonify({"error": "Invalid username or password."}), 401

if __name__ == '__main__':
    check_and_download_files()
    print("🔄 Loading model into RAM. Please wait...")
    initialize_model()
    print("🚀 Model loaded. Starting the application...")
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
