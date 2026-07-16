/**
 * BELLA — Chat Client
 * Handles SSE streaming, session management, UI updates, and Voice interaction (STT, TTS, Wake Word).
 */

const API_BASE = '/api';

// Chat State
let sessionId = null;
let isStreaming = false;

// Voice State
let mediaRecorder = null;
let audioChunks = [];
let recognition = null;
let audioContext = null;
let mediaStream = null;
let scriptNode = null;
let wsWakeword = null;

// DOM refs
const messagesContainer = document.getElementById('messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('btn-send');
const clearBtn = document.getElementById('btn-clear');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const micBtn = document.getElementById('btn-mic');
const settingsBtn = document.getElementById('btn-voice-settings');
const dropdownContent = document.getElementById('voice-dropdown-content');
const voiceEngineSelect = document.getElementById('voice-engine');
const sttEngineSelect = document.getElementById('stt-engine');
const wakewordToggle = document.getElementById('wakeword-toggle');

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

    // Voice UI Event Listeners
    if (micBtn) micBtn.addEventListener('click', toggleVoiceInput);
    if (settingsBtn && dropdownContent) {
        settingsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdownContent.classList.toggle('show');
        });

        document.addEventListener('click', () => {
            dropdownContent.classList.remove('show');
        });

        dropdownContent.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    }

    if (wakewordToggle) {
        wakewordToggle.addEventListener('change', (e) => {
            if (e.target.checked) {
                startWakeword();
            } else {
                stopWakeword();
            }
        });
    }
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
                        // Streaming complete - speak response if configured
                        const voiceEngine = voiceEngineSelect.value;
                        if (voiceEngine !== 'off') {
                            speakText(fullText);
                        } else {
                            handleWakeWordResume();
                        }
                    } else if (event.type === 'error') {
                        contentEl.innerHTML = `<span style="color: #ef4444;">Error: ${event.content}</span>`;
                        handleWakeWordResume();
                    }
                } catch (parseErr) {
                    // Skip malformed JSON
                }
            }
        }
    } catch (err) {
        thinkingEl.remove();
        appendMessage('assistant', `Connection error: ${err.message}. Is Ollama running?`);
        handleWakeWordResume();
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

// ─── Voice Inputs ────────────────────────────────────────────

function toggleVoiceInput() {
    if (!micBtn) return;
    if (micBtn.classList.contains('recording')) {
        stopRecording();
    } else if (micBtn.classList.contains('listening')) {
        if (recognition) {
            recognition.abort();
        }
    } else {
        const sttEngine = sttEngineSelect.value;
        if (sttEngine === 'browser') {
            startBrowserRecognition();
        } else {
            startRecording();
        }
    }
}

// STT: Browser Native
function startBrowserRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        alert("Speech Recognition not supported in this browser. Please use Local Neural (Whisper).");
        return;
    }

    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        micBtn.className = 'btn-mic listening';
        micBtn.title = 'Listening... Click to cancel';
    };

    recognition.onresult = (event) => {
        const text = event.results[0][0].transcript;
        if (text) {
            chatInput.value = text;
            sendMessage();
        }
    };

    recognition.onerror = (e) => {
        console.error("Speech recognition error:", e);
    };

    recognition.onend = () => {
        micBtn.className = 'btn-mic';
        micBtn.title = 'Start voice command';
        recognition = null;
    };

    recognition.start();
}

// STT: Local Whisper (Recording & Upload)
function startRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            audioChunks = [];
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

            mediaRecorder.ondataavailable = e => {
                if (e.data.size > 0) {
                    audioChunks.push(e.data);
                }
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                sendAudioForTranscription(audioBlob);
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            micBtn.className = 'btn-mic recording';
            micBtn.title = 'Recording... Click to finish';
        })
        .catch(err => {
            console.error("Microphone access failed:", err);
            alert("Could not access microphone.");
        });
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
    micBtn.className = 'btn-mic';
    micBtn.title = 'Start voice command';
}

async function sendAudioForTranscription(blob) {
    const formData = new FormData();
    formData.append('file', blob, 'recording.webm');

    // Show thinking indicator
    const welcome = document.getElementById('welcome');
    if (welcome) welcome.style.display = 'none';
    const thinkingEl = showThinking();
    setStreaming(true);

    try {
        const res = await fetch('/api/voice/transcribe', {
            method: 'POST',
            body: formData
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        thinkingEl.remove();
        setStreaming(false);

        if (data.text && data.text.trim()) {
            chatInput.value = data.text;
            sendMessage();
        } else {
            appendMessage('assistant', "I couldn't hear or transcribe anything. Please try speaking again.");
        }
    } catch (err) {
        thinkingEl.remove();
        setStreaming(false);
        appendMessage('assistant', `Transcription error: ${err.message}`);
    }
}

// ─── Voice Outputs (TTS) ─────────────────────────────────────

function speakText(text) {
    const engine = voiceEngineSelect.value;
    if (engine === 'off') return;

    // Clean up markdown syntax for clean text-to-speech reading
    const cleanedText = text
        .replace(/```[\s\S]*?```/g, '') // remove code blocks
        .replace(/`([^`]+)`/g, '$1')     // remove inline code format
        .replace(/\*\*([^*]+)\*\*/g, '$1') // remove bold
        .replace(/\*([^*]+)\*/g, '$1')     // remove italic
        .trim();

    if (!cleanedText) {
        handleWakeWordResume();
        return;
    }

    if (engine === 'browser') {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(cleanedText);
        utterance.onend = () => {
            handleWakeWordResume();
        };
        utterance.onerror = () => {
            handleWakeWordResume();
        };
        window.speechSynthesis.speak(utterance);
    } else if (engine === 'local') {
        window.speechSynthesis.cancel();
        fetch('/api/voice/synthesize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: cleanedText })
        })
        .then(res => {
            if (!res.ok) throw new Error("TTS synthesis failed");
            return res.blob();
        })
        .then(blob => {
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.onended = () => {
                URL.revokeObjectURL(url);
                handleWakeWordResume();
            };
            audio.onerror = () => {
                URL.revokeObjectURL(url);
                handleWakeWordResume();
            };
            audio.play();
        })
        .catch(err => {
            console.error("Local Piper TTS error:", err);
            handleWakeWordResume();
        });
    }
}

// ─── Wake Word Detection ─────────────────────────────────────

async function startWakeword() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        mediaStream = stream;

        // Establish WebSocket connection
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        wsWakeword = new WebSocket(`${protocol}//${window.location.host}/api/voice/wakeword`);

        wsWakeword.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.event === 'wakeword_detected') {
                console.log("[BELLA] Wake word detected!");
                triggerVoiceCommand();
            }
        };

        // Create 16kHz audio context for resampling
        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        const source = audioContext.createMediaStreamSource(stream);

        // Process audio in chunks of 4096 frames
        scriptNode = audioContext.createScriptProcessor(4096, 1, 1);
        scriptNode.onaudioprocess = (e) => {
            if (wsWakeword && wsWakeword.readyState === WebSocket.OPEN) {
                const inputData = e.inputBuffer.getChannelData(0);
                
                // Convert Float32 arrays to Int16 PCM bytes
                const pcmData = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    const sample = Math.max(-1, Math.min(1, inputData[i]));
                    pcmData[i] = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
                }
                wsWakeword.send(pcmData.buffer);
            }
        };

        source.connect(scriptNode);
        scriptNode.connect(audioContext.destination);
        console.log("[BELLA] Wake Word listener active.");
    } catch (err) {
        console.error("Wake word init failed:", err);
        wakewordToggle.checked = false;
        alert("Microphone access is required for wake word detection.");
    }
}

function stopWakeword() {
    if (scriptNode) {
        scriptNode.disconnect();
        scriptNode = null;
    }
    if (audioContext) {
        audioContext.close().catch(() => {});
        audioContext = null;
    }
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }
    if (wsWakeword) {
        wsWakeword.close();
        wsWakeword = null;
    }
    console.log("[BELLA] Wake Word listener stopped.");
}

function playChime() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(523.25, ctx.currentTime); // C5
        osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.1); // E5

        gain.gain.setValueAtTime(0.08, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start();
        osc.stop(ctx.currentTime + 0.3);
    } catch (e) {
        console.error("Failed to play wake word chime:", e);
    }
}

function triggerVoiceCommand() {
    playChime();

    // Disable wake word listening temporarily while processing voice command
    const originalWakewordState = wakewordToggle.checked;
    if (originalWakewordState) {
        stopWakeword();
    }

    setTimeout(() => {
        const sttEngine = sttEngineSelect.value;
        if (sttEngine === 'browser') {
            startBrowserRecognition();
        } else {
            startRecording();
        }
        
        // Register flag to resume wake word after answer is received/spoken
        window.resumeWakewordOnDone = originalWakewordState;
    }, 300);
}

function handleWakeWordResume() {
    if (window.resumeWakewordOnDone) {
        window.resumeWakewordOnDone = false;
        wakewordToggle.checked = true;
        startWakeword();
    }
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
