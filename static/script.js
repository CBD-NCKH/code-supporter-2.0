// Xác định các phần tử dựa trên từng trang
const authContainer = document.getElementById('auth-container');
const chatContainer = document.getElementById('chat-container');

// Logic cho trang đăng nhập/đăng ký
if (authContainer) {
    const registerButton = document.getElementById('register-btn');
    const loginButton = document.getElementById('login-btn');

    // Xử lý sự kiện Đăng ký
    if (registerButton) {
        registerButton.addEventListener('click', async () => {
            const username = document.getElementById('register-username').value;
            const password = document.getElementById('register-password').value;

            try {
                const response = await fetch('/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password }),
                });

                const data = await response.json();

                if (response.ok) {
                    window.location.href = data.redirect_url; // Điều hướng đến URL mới
                } else {
                    alert(data.error || 'Đăng ký thất bại.');
                }
            } catch (error) {
                console.error('Đăng ký thất bại:', error);
                alert('Đăng ký thất bại.');
            }
        });
    }

    // Xử lý sự kiện Đăng nhập
    if (loginButton) {
        loginButton.addEventListener('click', async () => {
            const username = document.getElementById('login-username').value;
            const password = document.getElementById('login-password').value;

            try {
                console.log("🔍 Sending login request:", { username, password }); // Debug log

                const response = await fetch('/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password }),
                });

                const text = await response.text(); // Đọc raw text trước
                console.log("🔍 Server response:", text); // Debug log

                try {
                    const data = JSON.parse(text); // Chuyển thành JSON
                    if (response.ok) {
                        window.location.href = data.redirect_url;
                    } else {
                        alert(data.error || 'Đăng nhập thất bại.');
                    }
                } catch (jsonError) {
                    console.error('❌ Không thể parse JSON:', jsonError);
                    alert('Lỗi server, không nhận được JSON hợp lệ.');
                }
            } catch (error) {
                console.error('❌ Không thể kết nối đến server:', error);
                alert('Không thể kết nối đến server.');
            }
        });
    }
}

// Logic cho trang chat
if (chatContainer) {
    const sendButton = document.getElementById('send-button');
    const userInput = document.getElementById('user-input');
    const messagesDiv = document.getElementById('messages');
    const themeToggleButton = document.getElementById('theme-toggle-button');

    // Lấy username từ query string
    const urlParams = new URLSearchParams(window.location.search);
    const username = urlParams.get('username');
    if (!username) {
        alert('Missing username! Redirecting to login page.');
        window.location.href = '/';
    } else {
        document.getElementById('username-display').textContent = username;
    }

    // Hàm chuyển đổi chế độ sáng/tối
    themeToggleButton.addEventListener('click', () => {
        document.body.classList.toggle('light-mode');
        themeToggleButton.textContent = document.body.classList.contains('light-mode') ? '🌞' : '🌙';
    });

    // Hàm hiển thị hiệu ứng "đang gõ"
    function showTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.classList.add('message', 'bot', 'typing');
        typingDiv.innerHTML = `
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        messagesDiv.appendChild(typingDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    // Hàm xóa hiệu ứng "đang gõ"
    function removeTypingIndicator() {
        const typingDiv = document.querySelector('.typing');
        if (typingDiv) {
            typingDiv.remove();
        }
    }

    // Hàm thêm tin nhắn vào giao diện (CÓ TÍCH HỢP CHỨC NĂNG PHÁT HIỆN CODE)
    function addMessage(content, sender, isMarkdown = false, typingSpeed = 100) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender);

        if (isMarkdown) {
            content = marked.parse(content);
        }

        messageDiv.innerHTML = content;
        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;

        // 🛠 **Tự động phát hiện code và thêm nút "Sao chép"**
        let codeBlocks = content.match(/```([\s\S]*?)```/g);
        if (codeBlocks) {
            codeBlocks.forEach((block) => {
                let codeContent = block.replace(/```[\w]*\n?/, "").replace(/```/, "").trim(); // Xóa dấu ```
                let formattedCode = `
                    <div class="code-container">
                        <pre><code>${codeContent}</code></pre>
                        <button class="copy-btn">📋 Sao chép</button>
                    </div>
                `;

                // Thay thế đoạn code trong nội dung tin nhắn
                messageDiv.innerHTML = messageDiv.innerHTML.replace(block, formattedCode);
            });

            // Thêm sự kiện "Sao chép" cho nút
            messageDiv.querySelectorAll(".copy-btn").forEach((button) => {
                button.addEventListener("click", () => {
                    let code = button.previousElementSibling.innerText;
                    navigator.clipboard.writeText(code).then(() => {
                        button.innerText = "✅ Đã sao chép!";
                        setTimeout(() => (button.innerText = "📋 Sao chép"), 2000);
                    }).catch(err => console.error("Lỗi sao chép:", err));
                });
            });
        }
    }

    // Hàm gửi yêu cầu tới API
    async function sendMessage() {
        const userMessage = userInput.value.trim();
        if (!userMessage) return;

        addMessage(userMessage, 'user');
        userInput.value = '';

        showTypingIndicator(); // Hiển thị hiệu ứng "đang gõ"

        try {
            const response = await fetch(`/api?username=${username}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userMessage }),
            });

            const data = await response.json();

            removeTypingIndicator(); // Xóa hiệu ứng "đang gõ"

            if (data.reply) {
                addMessage(data.reply, 'bot', true, 30);
            } else {
                addMessage('Không nhận được phản hồi từ server.', 'bot');
            }
        } catch (error) {
            removeTypingIndicator(); // Xóa hiệu ứng "đang gõ" nếu có lỗi
            console.error('Không thể kết nối tới server:', error);
            addMessage('Không thể kết nối tới server.', 'bot');
        }
    }

    // Xử lý sự kiện click vào nút "Gửi"
    sendButton.addEventListener('click', sendMessage);

    // Xử lý sự kiện nhấn phím Enter
    userInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });
}
