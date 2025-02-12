// Xác định các phần tử dựa trên từng trang
const authContainer = document.getElementById('auth-container');
const chatContainer = document.getElementById('chat-container');

// Logic cho trang đăng nhập/đăng ký
if (authContainer) {
    const registerButton = document.getElementById('register-btn');
    const loginButton = document.getElementById('login-btn');

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
                    window.location.href = data.redirect_url;
                } else {
                    alert(data.error || 'Đăng ký thất bại.');
                }
            } catch (error) {
                console.error('Đăng ký thất bại:', error);
                alert('Đăng ký thất bại.');
            }
        });
    }

    if (loginButton) {
        loginButton.addEventListener('click', async () => {
            const username = document.getElementById('login-username').value;
            const password = document.getElementById('login-password').value;

            try {
                console.log("🔍 Sending login request:", { username, password });

                const response = await fetch('/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password }),
                });

                const text = await response.text();
                console.log("🔍 Server response:", text);

                try {
                    const data = JSON.parse(text);
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

    // Ẩn khung chat ban đầu và thêm nút mở chat
    chatContainer.classList.add("close"); // Thêm class để thu nhỏ ban đầu

    const chatToggleButton = document.createElement("div");
    chatToggleButton.id = "chat-toggle-button";
    chatToggleButton.innerHTML = "💬";
    document.body.appendChild(chatToggleButton);

    const closeChatButton = document.createElement("div");
    closeChatButton.id = "close-chat-button";
    closeChatButton.innerHTML = "❌";
    document.body.appendChild(closeChatButton);
    closeChatButton.style.display = "none";

    chatToggleButton.addEventListener("click", () => {
        chatContainer.classList.remove("close");
        chatContainer.classList.add("open");

        chatToggleButton.style.display = "none";
        closeChatButton.style.display = "flex";
    });

    closeChatButton.addEventListener("click", () => {
        chatContainer.classList.remove("open");
        chatContainer.classList.add("close");

        setTimeout(() => {
            closeChatButton.style.display = "none";
            chatToggleButton.style.display = "flex";
        }, 300); // Chờ hiệu ứng chạy xong rồi ẩn nút
    });

    // Xử lý chuyển đổi chế độ sáng/tối
    themeToggleButton.addEventListener('click', () => {
        document.body.classList.toggle('light-mode');
        localStorage.setItem('theme', document.body.classList.contains('light-mode') ? 'light' : 'dark');
        themeToggleButton.textContent = document.body.classList.contains('light-mode') ? '🌞' : '🌙';
    });

    // Duy trì chế độ sáng/tối khi tải lại trang
    if (localStorage.getItem('theme') === 'light') {
        document.body.classList.add('light-mode');
        themeToggleButton.textContent = '🌞';
    }

    // Lấy username từ query string
    const urlParams = new URLSearchParams(window.location.search);
    const username = urlParams.get('username');
    if (!username) {
        alert('Missing username! Redirecting to login page.');
        window.location.href = '/';
    } else {
        document.getElementById('username-display').textContent = username;
    }

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
            // ✅ Chuyển Markdown thành HTML và bảo toàn code block
            content = marked.parse(content);

            // 🛠 Loại bỏ các thẻ <p> thừa do Markdown Parser tự động thêm vào
            content = content.replace(/^<p>|<\/p>$/g, '');
            // 🛠 Loại bỏ các <br> không mong muốn sau danh sách (<ul>)
            content = content.replace(/<\/ul>\s*<br>/g, '</ul>');
            // 🛠 Loại bỏ <br> dư thừa trong danh sách số thứ tự (<ol>)
            content = content.replace(/<\/ol>\s*<br>/g, '</ol>');
            
            // 🔹 Giữ nguyên việc xuống dòng Shift + Enter nhưng không áp dụng vào <pre><code>
            content = content.replace(/(<pre><code[\s\S]*?<\/code><\/pre>)|(?:\n)/g, (match, codeBlock) => {
                return codeBlock ? codeBlock : '<br>';
            });
        }

        // 🔹 Chỉ thêm <br> cho tin nhắn của NGƯỜI DÙNG (Không ảnh hưởng tin nhắn bot)
        if (sender === 'user') {
            content = content.replace(/\n/g, '<br>');
        }

        messageDiv.innerHTML = content;
        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;

        // 🛠 **Tự động phát hiện và sửa lỗi hiển thị code**
        setTimeout(() => {
            messageDiv.querySelectorAll("pre code").forEach((codeBlock) => {
                console.log("🔍 Tìm thấy code block trước khi thay thế:", codeBlock.innerText);
        
                const container = document.createElement("div");
                container.classList.add("code-container");
        
                const copyButton = document.createElement("button");
                copyButton.classList.add("copy-btn");
                copyButton.innerText = "📋 Sao chép";
        
                copyButton.addEventListener("click", () => {
                    navigator.clipboard.writeText(codeBlock.innerText).then(() => {
                        copyButton.innerText = "✅ Đã sao chép!";
                        setTimeout(() => (copyButton.innerText = "📋 Sao chép"), 2000);
                    }).catch(err => console.error("Lỗi sao chép:", err));
                });
        
                container.appendChild(codeBlock.cloneNode(true)); // Sử dụng clone để không mất nội dung
                container.appendChild(copyButton);
        
                codeBlock.parentElement.replaceWith(container);
        
                console.log("✅ Sau khi thay thế:", container.outerHTML);
            });
        }, 100);
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
    userInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // Ngăn xuống dòng
            sendMessage();
        } else if (event.key === 'Enter' && event.shiftKey) {
            event.preventDefault();
            userInput.value += '\n'; // Thêm xuống dòng vào nội dung
        }
    });
}