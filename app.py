from transformers import AutoModelForCausalLM, AutoTokenizer
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import hashlib
import torch
import os
import threading
import json
import shutil
import requests

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

# Hàm tải tệp từ Google Drive
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

# Khởi tạo mô hình
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

# Kiểm tra & tải các tệp cần thiết
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
            download_file_from_google_drive(file_url, output_path)    if tokenizer is None or model is None:
        print("Initializing model...")
        tokenizer = AutoTokenizer.from_pretrained("./qwen_int4_model/tokenizer")
        model = AutoModelForCausalLM.from_pretrained(
            "./qwen_int4_model/model",
            torch_dtype=torch.float16
        )
        print("Model loaded into RAM.")

# Kết nối Google Sheets
def connect_google_sheet(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Lấy thông tin credentials từ biến môi trường
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json is None:
        raise ValueError("GOOGLE_CREDENTIALS_JSON environment variable is not set.")
    
    # Chuyển JSON từ chuỗi (string) thành dictionary
    creds_dict = json.loads(creds_json)
    
    # Kết nối với Google Sheets
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).sheet1
    return sheet

# Hàm hash mật khẩu
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Hàm tạo tài khoản người dùng
def create_account(sheet, username, password):
    users = sheet.get_all_values()
    for row in users:
        if len(row) >= 1 and row[0] == username:
            return False, "Username already exists."
    hashed_password = hash_password(password)
    sheet.append_row([username, hashed_password, "", ""])
    return True, "Account created successfully."

# Hàm xác thực người dùng
def authenticate_user(sheet, username, password):
    users = sheet.get_all_values()
    hashed_password = hash_password(password)
    for row in users:
        if len(row) >= 2 and row[0] == username and row[1] == hashed_password:
            return True
    return False

# Hàm sinh văn bản từ mô hình Qwen2.5-Coder-0.5B-Instruct
def generate_response_qwen(prompt, max_length=5000):
    try:
        # Tạo template chat theo cú pháp của Qwen
        messages = [
            {"role": "system", "content": "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
        # Tạo text từ template
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        # Mã hóa đầu vào
        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
        
        # Sinh văn bản
        generated_ids = model.generate(
            **model_inputs,
            max_new_tokens=max_length
        )
        # Cắt bỏ phần đầu (prompt gốc)
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]
        # Giải mã đầu ra
        response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return response
    except Exception as e:
        return f"Error generating response: {e}"

# Hàm lưu lịch sử hội thoại vào Google Sheets
def save_to_google_sheet(sheet, username, role, content):
    row = [""] * 4  # Tạo hàng trống với 4 cột
    row[0] = username  # Lưu username vào cột 1
    row[2] = role      # Lưu role vào cột 3
    row[3] = content   # Lưu content vào cột 4
    sheet.append_row(row)  # Thêm hàng mới vào Google Sheets

# Hàm lấy hội thoại gần nhất của người dùng
def get_user_conversation(sheet, username, max_rows=88):
    rows = sheet.get_all_values()
    user_rows = [row for row in rows if len(row) >= 3 and row[0] == username]
    return user_rows[-max_rows:] if len(user_rows) > max_rows else user_rows

# Khởi tạo ứng dụng Flask
app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "*"}})

# Route mặc định để render giao diện
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['GET'])
def chat():
    username = request.args.get("username") 
    if not username:
        return "Missing username parameter", 400  
    return render_template("chat.html", username=username)

# API xử lý đăng ký
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    sheet = connect_google_sheet("CodesupporterHistory")
    success, message = create_account(sheet, username, password)
    if success:
        return jsonify({"redirect_url": f"/chat?username={username}"}), 201
    else:
        return jsonify({"error": message}), 400

# API xử lý đăng nhập
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get("username")
        password = data.get("password")
        sheet = connect_google_sheet("CodesupporterHistory")
        if authenticate_user(sheet, username, password):
            return jsonify({"redirect_url": f"/chat?username={username}"}), 200
        else:
            return jsonify({"error": "Invalid username or password."}), 401
    except Exception as e:
        return jsonify({"error": "Internal server error."}), 500

# API xử lý tin nhắn
@app.route('/api', methods=['POST'])
def api():
    try:
        global model, tokenizer
        if model is None or tokenizer is None:
            return "Model is still loading, please try again later.", 503
        
        username = request.args.get('username')
        if not username:
            return jsonify({"error": "Unauthorized. Username is missing."}), 401

        sheet = connect_google_sheet("CodesupporterHistory")
        data = request.json
        user_message = data.get("message")

        memory = get_user_conversation(sheet, username, max_rows=4)
        memory_context = "\n".join([f"{row[2]}: {row[3]}" for row in memory if len(row) >= 4])

        prompt = (
            f"Dữ liệu từ cơ sở dữ liệu:\n{memory_context}\n\n"
            f"Câu hỏi của người dùng: {user_message}\n\n"
        )

        bot_reply = generate_response_qwen(prompt)

        save_to_google_sheet(sheet, username, "user", user_message)
        save_to_google_sheet(sheet, username, "assistant", bot_reply)

        return jsonify({"reply": bot_reply})
    except Exception as e:
        print(f"Lỗi: {e}")
        return jsonify({"error": "Có lỗi xảy ra khi kết nối mô hình."}), 500

# Tải model và tokenizer ngay khi module được import
check_and_download_files()
print("🔄 Loading model into RAM. Please wait...")
initialize_model()
print("🚀 Model loaded.")

if __name__ == '__main__':
    # Chạy ứng dụng Flask
    port = int(os.environ.get("PORT", 5000))  
    app.run(host='0.0.0.0', port=port)


