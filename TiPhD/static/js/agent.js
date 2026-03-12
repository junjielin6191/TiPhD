document.addEventListener('DOMContentLoaded', () => {
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const chatMessages = document.getElementById('chat-messages');
    const newChatBtn = document.getElementById('new-chat-btn');

    // 自动调整输入框高度
    chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if(this.value.trim() === '') {
            this.style.height = 'auto';
        }
    });

    // 监听回车键发送 (Shift+Enter 用于换行)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener('click', sendMessage);

    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text) return;

        // 1. 在 UI 渲染用户的消息
        appendMessage('user', text);
        chatInput.value = '';
        chatInput.style.height = 'auto';

        // 2. 添加 Agent 正在思考的加载动画
        const loadingId = 'loading-' + Date.now();
        appendMessage('system', '<div class="typing-indicator" style="color:#666; font-style:italic;">TiAgent is thinking...</div>', loadingId);

        try {
            // 3. 发送请求给后端 Flask API
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: text })
            });
            const data = await response.json();

            // 4. 移除加载动画
            document.getElementById(loadingId).remove();
            
            // 5. 渲染真实回复
            if (data.answer) {
                // 使用 marked.js 将 Markdown 渲染为漂亮格式
                const htmlAnswer = marked.parse(data.answer);
                appendMessage('system', htmlAnswer);
            } else {
                appendMessage('system', `<span style="color:red">Error: ${data.error || 'Unknown error'}</span>`);
            }
        } catch (error) {
            document.getElementById(loadingId).remove();
            appendMessage('system', `<span style="color:red">Network Error: Could not reach the server.</span>`);
        }
    }

    function appendMessage(role, content, id = null) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}-msg`;
        if (id) msgDiv.id = id;

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'avatar-container';
        
        if (role === 'user') {
            avatarDiv.innerHTML = `<div class="avatar user-avatar">U</div>`;
        } else {
            avatarDiv.innerHTML = `<img src="/static/logo.png" alt="TiAgent" class="avatar">`;
        }

        const contentDiv = document.createElement('div');
        contentDiv.className = 'msg-content';
        contentDiv.innerHTML = content;

        msgDiv.appendChild(avatarDiv);
        msgDiv.appendChild(contentDiv);
        chatMessages.appendChild(msgDiv);
        
        // 自动滚动到底部
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // New Chat 按钮逻辑 (清空后端记忆，重置界面)
    newChatBtn.addEventListener('click', async () => {
        try {
            await fetch('/api/chat/clear', { method: 'POST' });
            chatMessages.innerHTML = `
                <div class="message system-msg">
                    <div class="avatar-container">
                        <img src="/static/logo.png" alt="TiAgent" class="avatar">
                    </div>
                    <div class="msg-content">
                        Chat memory cleared. I am ready for a new topic!
                    </div>
                </div>
            `;
        } catch(e) {
            console.error("Failed to clear chat memory.");
        }
    });
});