from together import Together
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import hashlib
import os
import json

# 🔹 Khởi tạo Together AI Client
client = Together(api_key=os.getenv("KEY"))

# 🔹 Hàm gọi API của Meta Llama 3.3 70B
def generate_response_llama(prompt):
    try:
        system_prompt = (
            "Bạn là một trợ lý viết code hỗ trợ học sinh với các bài tập lập trình được điều chỉnh và thay đổi bởi Châu Phúc Khang, học sinh chuyên toán khóa 2023-2026 của trường Phổ thông Năng Khiếu, ĐHQG - TPHCM dựa trên mô hình gốc là mô hình mã nguồn mở Meta Llama 3.3 70B. "
            "Trước khi đưa ra code cụ thể cho học sinh, hãy mô tả logic của code và giải thích cách hoạt động. Lưu ý, chỉ đưa code trực tiếp khi và chỉ khi học sinh yêu cầu rõ ràng trong tin nhắn, nếu không thì tập trung vào giải thích logic và ý tưởng giải giúp học sinh phát triển tư duy lập trình. "
            "Ngoài việc sinh code, bạn cũng có thể giải thích các thắc mắc liên quan đến lập trình và nếu người dùng có hỏi điều gì ngoài lập trình thì bạn vẫn đối thoại được như bình thường"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        print(f"🔍 Sending request to Meta Llama: {messages}")  
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=messages,
            max_tokens=1024,
            temperature=0.7,
            top_p=0.7,
            top_k=50,
            repetition_penalty=1,
            stop=["<|eot_id|>", "<|eom_id|>"],
            stream=False  
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"❌ Error in Meta Llama API: {e}")
        return f"Error generating response: {e}"

# Kết nối Google Sheets
def connect_google_sheet(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client_gs = gspread.authorize(creds)
    sheet = client_gs.open(sheet_name).sheet1
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
    sheet.append_row([username, hashed_password])
    return True, "Account created successfully."

# Hàm xác thực người dùng
def authenticate_user(sheet, username, password):
    users = sheet.get_all_values()
    hashed_password = hash_password(password)
    for row in users:
        if len(row) >= 2 and row[0] == username and row[1] == hashed_password:
            return True
    return False

# Hàm lưu lịch sử hội thoại vào Google Sheets
def save_to_google_sheet(sheet, username, role, content):
    row = [""] * 3  
    row[0] = username
    row[1] = role
    row[2] = content
    sheet.append_row(row)  

# Hàm lấy hội thoại gần nhất của người dùng
def get_user_conversation(sheet, username, max_rows=8):
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

# API xử lý đăng kíkí
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json

        if not data or "username" not in data or "password" not in data:
            return jsonify({"error": "Thiếu thông tin đăng ký."}), 400

        username = data.get("username")
        password = data.get("password")

        sheet = connect_google_sheet("Account")
        success, message = create_account(sheet, username, password)

        if success:
            return jsonify({"redirect_url": f"/chat?username={username}"}), 201
        else:
            return jsonify({"error": message}), 400
    except Exception as e:
        print(f"❌ Register Error: {e}")
        return jsonify({"error": f"Lỗi server: {e}"}), 500

# API xử lý đăng nhập
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get("username")
        password = data.get("password")
        sheet = connect_google_sheet("Account")
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
        username = request.args.get('username')
        if not username:
            return jsonify({"error": "Unauthorized. Username is missing."}), 401
        
        sheet = connect_google_sheet("CodesupporterHistory")
        data = request.json
        user_message = data.get("message")
        
        memory = get_user_conversation(sheet, username, max_rows=8)
        memory_context = "\n".join([f"{row[1]}: {row[2]}" for row in memory if len(row) >= 3])
        
        prompt = (
            f"Dữ liệu từ cơ sở dữ liệu:\n{memory_context}\n\n"
            f"Câu hỏi của người dùng: {user_message}\n\n"
        )
        
        bot_reply = generate_response_llama(prompt)
        
        save_to_google_sheet(sheet, username, "user", user_message)
        save_to_google_sheet(sheet, username, "assistant", bot_reply)
        
        return jsonify({"reply": bot_reply})
    except Exception as e:
        print(f"Lỗi: {e}")
        return jsonify({"error": "Có lỗi xảy ra khi kết nối mô hình."}), 500

# Chạy ứng dụng
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  
    app.run(host='0.0.0.0', port=port)
