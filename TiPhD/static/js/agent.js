let currentSessionId = null;

document.addEventListener('DOMContentLoaded', () => {
    loadSessionList();

    // 绑定新会话按钮
    document.getElementById('new-chat-btn').addEventListener('click', createNewSession);
    
    // 绑定发送按钮
    document.getElementById('send-btn').addEventListener('click', sendMessage);
    
    // 绑定回车键发送 (Shift+Enter 换行)
    document.getElementById('chat-input').addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
});

// 1. 加载左侧会话列表
async function loadSessionList() {
    try {
        const response = await fetch('/api/sessions/list');
        if (!response.ok) return; // 可能未登录
        const sessions = await response.json();
        
        const listUl = document.getElementById('session-list');
        listUl.innerHTML = '';
        
        sessions.forEach(session => {
            const li = document.createElement('li');
            li.textContent = session.title || "Conversation";
            li.className = session.id === currentSessionId ? 'active' : '';
            li.onclick = () => loadSessionHistory(session.id, li.textContent);
            listUl.appendChild(li);
        });

        // 如果没有会话，自动创建一个；如果有，默认加载第一个
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
        document.getElementById('chat-box').innerHTML = ''; // 清空聊天区
        
        loadSessionList(); // 刷新左侧列表使其高亮
    } catch (error) {
        console.error("Failed to create session:", error);
    }
}

// 3. 加载特定会话的历史记录
async function loadSessionHistory(sessionId, title) {
    currentSessionId = sessionId;
    document.getElementById('current-chat-title').textContent = title || "Conversation";
    document.getElementById('welcome-screen')?.remove();
    
    // 更新左侧高亮
    document.querySelectorAll('#session-list li').forEach(li => li.classList.remove('active'));
    event?.currentTarget?.classList.add('active');

    try {
        const response = await fetch(`/api/sessions/${sessionId}`);
        const messages = await response.json();
        
        const chatBox = document.getElementById('chat-box');
        chatBox.innerHTML = ''; // 清空当前
        
        messages.forEach(msg => {
            appendMessage(msg.role, msg.content);
        });
        scrollToBottom();
    } catch (error) {
        console.error("Failed to load history:", error);
    }
}

// 4. 发送消息
async function sendMessage() {
    const inputEl = document.getElementById('chat-input');
    const text = inputEl.value.trim();
    if (!text || !currentSessionId) return;

    // 清空输入框并显示用户消息
    inputEl.value = '';
    document.getElementById('welcome-screen')?.remove();
    appendMessage('user', text);
    scrollToBottom();

    // 显示 Agent 正在思考的提示
    const loadingId = appendMessage('agent', '<i class="fas fa-spinner fa-spin"></i> Thinking...', true);
    scrollToBottom();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: text, session_id: currentSessionId })
        });
        
        const data = await response.json();
        
        // 移除 loading，填入真实回复
        document.getElementById(loadingId).remove();
        if (data.error) {
            appendMessage('agent', `❌ Error: ${data.error}`);
        } else {
            appendMessage('agent', data.answer);
        }
        scrollToBottom();
        
        // 如果这是这个新会话的第一句话，重新加载一下左侧列表（后端如果自动改了标题的话）
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
    msgDiv.className = `chat-message ${role}`; // 'chat-message user' 或 'chat-message agent'
    
    // 简单的 Markdown 处理 (将换行转为 <br>)
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