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

# Tải mô hình StarCoder
device = "cpu"
print(f"Using device: {device}")

# Tải tokenizer
tokenizer = AutoTokenizer.from_pretrained('replit/replit-code-v1-3b', trust_remote_code=True)

# Hàm tải mô hình
def load_model():
    global model
    if model is None:  # Kiểm tra tránh tải lại
        print("Loading model with quantization...")
        model = AutoModelForCausalLM.from_pretrained('replit/replit-code-v1-3b', trust_remote_code=True)
        print("Model loaded successfully.")

model = None
# Tải mô hình trong luồng riêng
threading.Thread(target=load_model).start()

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

# Hàm sinh văn bản từ mô hình Replit Code V1-3B
def generate_response_replit(prompt, max_length=500, temperature=0.7, top_p=0.95, top_k=4):
    try:
        # Mã hóa đầu vào
        inputs = tokenizer.encode(prompt, return_tensors="pt")        
        # Sinh văn bản
        outputs = model.generate(
            inputs,
            max_length=max_length,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            eos_token_id=tokenizer.eos_token_id,
            num_return_sequences=1  # Trả về 1 chuỗi đầu ra
        )        
        # Giải mã kết quả đầu ra
        return tokenizer.decode(outputs[0], skip_special_tokens=True, clean_up_tokenization_spaces=False)
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
def get_user_conversation(sheet, username, max_rows=4):
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
        # Kiểm tra nếu mô hình chưa tải xong
        if model is None:
            return jsonify({"error": "Model is still loading. Please try again later."}), 503
        
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

        bot_reply = generate_response_star_coder(prompt)

        save_to_google_sheet(sheet, username, "user", user_message)
        save_to_google_sheet(sheet, username, "assistant", bot_reply)

        return jsonify({"reply": bot_reply})
    except Exception as e:
        print(f"Lỗi: {e}")
        return jsonify({"error": "Có lỗi xảy ra khi kết nối mô hình."}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  
    app.run(host='0.0.0.0', port=port)
