let currentSessionId = null;

document.addEventListener('DOMContentLoaded', () => {
    loadSessionList();

    // 绑定新会话按钮
    const newChatBtn = document.getElementById('new-chat-btn');
    if (newChatBtn) {
        newChatBtn.addEventListener('click', createNewSession);
    }
    
    // 绑定发送按钮
    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }
    
    // 绑定回车键发送 (Shift+Enter 换行)
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
});

// 1. 加载左侧会话列表
// 1. 加载左侧会话列表
async function loadSessionList() {
    try {
        const response = await fetch('/api/sessions/list');
        if (!response.ok) return; 
        const sessions = await response.json();
        
        const listUl = document.getElementById('session-list');
        listUl.innerHTML = '';
        
        sessions.forEach(session => {
            const li = document.createElement('li');
            li.textContent = session.title || "Conversation";
            li.dataset.id = session.id; 
            
            // 如果是当前正在聊天的会话
            if (session.id === currentSessionId) {
                li.classList.add('active');
                // 🌟 【丝滑体验核心】同步更新右侧顶部的标题栏
                const headerTitle = document.getElementById('current-chat-title');
                if (headerTitle) {
                    headerTitle.textContent = session.title;
                }
            }
            
            li.onclick = () => loadSessionHistory(session.id, li.textContent);
            listUl.appendChild(li);
        });

        if (sessions.length === 0) {
            createNewSession();
        } else if (!currentSessionId) {
            loadSessionHistory(sessions[0].id, sessions[0].title);
        }
    } catch (error) {
        console.error("Failed to load sessions:", error);
    }
}

// 2. 创建新会话
async function createNewSession() {
    try {
        const response = await fetch('/api/sessions/create', { method: 'POST' });
        const data = await response.json();
        currentSessionId = data.session_id;
        
        document.getElementById('current-chat-title').textContent = "New Conversation";
        document.getElementById('chat-box').innerHTML = `
            <div class="welcome-screen" id="welcome-screen">
                <h2>Welcome to TiAgent</h2>
                <p>Your intelligent biomedical research assistant.</p>
            </div>
        `; // 恢复欢迎卡片
        
        await loadSessionList(); // 刷新左侧列表
    } catch (error) {
        console.error("Failed to create session:", error);
    }
}

// 3. 加载特定会话的历史记录
async function loadSessionHistory(sessionId, title) {
    currentSessionId = sessionId;
    document.getElementById('current-chat-title').textContent = title || "Conversation";
    
    const welcomeScreen = document.getElementById('welcome-screen');
    if(welcomeScreen) welcomeScreen.remove();
    
    // 【关键修复2】更安全的高亮切换逻辑，去除可能报错的 event 对象
    document.querySelectorAll('#session-list li').forEach(li => {
        if (li.dataset.id === sessionId) {
            li.classList.add('active');
        } else {
            li.classList.remove('active');
        }
    });

    try {
        const response = await fetch(`/api/sessions/${sessionId}`);
        const messages = await response.json();
        
        const chatBox = document.getElementById('chat-box');
        chatBox.innerHTML = ''; 
        
        if(messages.length === 0) {
            chatBox.innerHTML = `
                <div class="welcome-screen" id="welcome-screen">
                    <h2>Welcome to TiAgent</h2>
                    <p>Your intelligent biomedical research assistant.</p>
                </div>
            `;
        } else {
            messages.forEach(msg => {
                appendMessage(msg.role, msg.content);
            });
            scrollToBottom();
        }
    } catch (error) {
        console.error("Failed to load history:", error);
    }
}

// 4. 发送消息
async function sendMessage() {
    const inputEl = document.getElementById('chat-input');
    const text = inputEl.value.trim();
    if (!text || !currentSessionId) return;

    inputEl.value = '';
    const welcomeScreen = document.getElementById('welcome-screen');
    if(welcomeScreen) welcomeScreen.remove();
    
    appendMessage('user', text);
    scrollToBottom();

    const loadingId = appendMessage('agent', '<i class="fas fa-spinner fa-spin"></i> Thinking...', true);
    scrollToBottom();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: text, session_id: currentSessionId })
        });
        
        const data = await response.json();
        
        document.getElementById(loadingId).remove();
        if (data.error) {
            appendMessage('agent', `❌ Error: ${data.error}`);
        } else {
            appendMessage('agent', data.answer);
        }
        scrollToBottom();
        
        loadSessionList(); 
    } catch (error) {
        document.getElementById(loadingId).remove();
        appendMessage('agent', "❌ Connection failed.");
    }
}

// 5. 将消息追加到界面
function appendMessage(role, content, isHtml = false) {
    const chatBox = document.getElementById('chat-box');
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${role}`; 
    
    let displayContent = content;
    if (!isHtml) {
        displayContent = content.replace(/\n/g, '<br>');
    }

    const id = 'msg-' + Date.now();
    msgDiv.id = id;
    
    msgDiv.innerHTML = `
        <div class="avatar">${role === 'user' ? '👤' : '🤖'}</div>
        <div class="bubble">${displayContent}</div>
    `;
    
    chatBox.appendChild(msgDiv);
    return id;
}

function scrollToBottom() {
    const chatBox = document.getElementById('chat-box');
    chatBox.scrollTop = chatBox.scrollHeight;
}