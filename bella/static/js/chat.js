/**
 * BELLA — Chat Client
 * Handles SSE streaming, session management, and UI updates.
 */

const API_BASE = '/api';

// State
let sessionId = null;
let isStreaming = false;

// DOM refs
const messagesContainer = document.getElementById('messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('btn-send');
const clearBtn = document.getElementById('btn-clear');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');

// ─── Initialization ─────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    chatInput.focus();

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    });

    sendBtn.addEventListener('click', sendMessage);
    clearBtn.addEventListener('click', clearChat);

    // Suggestion chips
    document.querySelectorAll('.welcome-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            chatInput.value = chip.textContent;
            sendMessage();
        });
    });
});

// ─── Health Check ────────────────────────────────────────────

async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/health`);
        const data = await res.json();
        if (data.ollama) {
            statusDot.className = 'status-dot';
            statusText.textContent = `${data.model}`;
        } else {
            statusDot.className = 'status-dot offline';
            statusText.textContent = 'Model offline';
        }
    } catch {
        statusDot.className = 'status-dot offline';
        statusText.textContent = 'Server offline';
    }
}

// ─── Send Message ────────────────────────────────────────────

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text || isStreaming) return;

    // Hide welcome state
    const welcome = document.getElementById('welcome');
    if (welcome) welcome.style.display = 'none';

    // Add user message to UI
    appendMessage('user', text);
    chatInput.value = '';
    chatInput.style.height = 'auto';

    // Show thinking indicator
    const thinkingEl = showThinking();
    setStreaming(true);

    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                session_id: sessionId,
                stream: true,
            }),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        // Remove thinking indicator, create assistant bubble
        thinkingEl.remove();
        const assistantEl = appendMessage('assistant', '');
        const contentEl = assistantEl.querySelector('.message-text');

        // Read SSE stream
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullText = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line in buffer

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const jsonStr = line.slice(6).trim();
                if (!jsonStr) continue;

                try {
                    const event = JSON.parse(jsonStr);

                    if (event.type === 'session') {
                        sessionId = event.session_id;
                    } else if (event.type === 'token') {
                        fullText += event.content;
                        contentEl.innerHTML = renderMarkdown(fullText);
                        scrollToBottom();
                    } else if (event.type === 'done') {
                        // Streaming complete
                    } else if (event.type === 'error') {
                        contentEl.innerHTML = `<span style="color: #ef4444;">Error: ${event.content}</span>`;
                    }
                } catch (parseErr) {
                    // Skip malformed JSON
                }
            }
        }
    } catch (err) {
        thinkingEl.remove();
        appendMessage('assistant', `Connection error: ${err.message}. Is Ollama running?`);
    } finally {
        setStreaming(false);
    }
}

// ─── Clear Chat ──────────────────────────────────────────────

async function clearChat() {
    if (sessionId) {
        await fetch(`${API_BASE}/chat/clear`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId }),
        }).catch(() => {});
    }

    sessionId = null;
    messagesContainer.innerHTML = createWelcomeHTML();

    // Rebind chips
    document.querySelectorAll('.welcome-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            chatInput.value = chip.textContent;
            sendMessage();
        });
    });
}

// ─── UI Helpers ──────────────────────────────────────────────

function appendMessage(role, content) {
    const msg = document.createElement('div');
    msg.className = `message ${role}`;

    const avatar = role === 'assistant' ? '✦' : '→';
    const rendered = content ? renderMarkdown(content) : '';

    msg.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-text">${rendered}</div>
        </div>
    `;

    messagesContainer.appendChild(msg);
    scrollToBottom();
    return msg;
}

function showThinking() {
    const el = document.createElement('div');
    el.className = 'message assistant';
    el.innerHTML = `
        <div class="message-avatar">✦</div>
        <div class="message-content">
            <div class="thinking-indicator">
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
            </div>
        </div>
    `;
    messagesContainer.appendChild(el);
    scrollToBottom();
    return el;
}

function setStreaming(active) {
    isStreaming = active;
    sendBtn.disabled = active;
    chatInput.disabled = active;
    if (!active) chatInput.focus();

    statusDot.className = active ? 'status-dot thinking' : 'status-dot';
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// ─── Markdown Rendering (lightweight) ────────────────────────

function renderMarkdown(text) {
    return text
        // Code blocks
        .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="lang-$1">$2</code></pre>')
        // Inline code
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        // Bold
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        // Italic
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // Line breaks
        .replace(/\n/g, '<br>');
}

// ─── Welcome State HTML ──────────────────────────────────────

function createWelcomeHTML() {
    return `
        <div class="welcome-state" id="welcome">
            <div class="welcome-icon">✦</div>
            <h1 class="welcome-title">Hello, I'm BELLA</h1>
            <p class="welcome-subtitle">
                Your private, fully local AI assistant. Everything runs on your hardware — 
                no data ever leaves this machine.
            </p>
            <div class="welcome-chips">
                <div class="welcome-chip">What can you do?</div>
                <div class="welcome-chip">Tell me a fun fact</div>
                <div class="welcome-chip">Help me write code</div>
                <div class="welcome-chip">Explain quantum computing</div>
            </div>
        </div>
    `;
}
