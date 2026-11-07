/* Friday AI Canvas Grid & Interactivity Engine */

const GRID_STEP = 20; // 20px Graph Paper Grid Snap

document.addEventListener('DOMContentLoaded', () => {
    initGridSnapping();
    initChat();
    initAudioMeter();
    initPyWebViewBridge();
});

// Grid Snapping Math
function snapToGrid(value) {
    return Math.round(value / GRID_STEP) * GRID_STEP;
}

// Drag & Drop + Resize Grid Snapping
function initGridSnapping() {
    const panels = document.querySelectorAll('.widget-panel');
    const container = document.getElementById('canvas-container');

    panels.forEach(panel => {
        const header = panel.querySelector('.widget-header');
        const resizeHandle = panel.querySelector('.resize-handle');

        let isDragging = false;
        let isResizing = false;
        let startX, startY, startLeft, startTop, startWidth, startHeight;

        // Dragging Logic
        header.addEventListener('mousedown', (e) => {
            if (e.target.closest('.btn-drag') || e.target === header || e.target.classList.contains('widget-title')) {
                isDragging = true;
                panel.classList.add('dragging');
                startX = e.clientX;
                startY = e.clientY;
                startLeft = panel.offsetLeft;
                startTop = panel.offsetTop;
            }
        });

        // Resizing Logic
        if (resizeHandle) {
            resizeHandle.addEventListener('mousedown', (e) => {
                e.stopPropagation();
                isResizing = true;
                startX = e.clientX;
                startY = e.clientY;
                startWidth = panel.offsetWidth;
                startHeight = panel.offsetHeight;
            });
        }

        document.addEventListener('mousemove', (e) => {
            if (isDragging) {
                const dx = e.clientX - startX;
                const dy = e.clientY - startY;
                const rawLeft = startLeft + dx;
                const rawTop = startTop + dy;

                // Snap position to graph grid points
                panel.style.left = `${snapToGrid(rawLeft)}px`;
                panel.style.top = `${snapToGrid(rawTop)}px`;
            } else if (isResizing) {
                const dx = e.clientX - startX;
                const dy = e.clientY - startY;
                const rawW = startWidth + dx;
                const rawH = startHeight + dy;

                // Snap dimensions to graph grid points
                if (rawW > 200) panel.style.width = `${snapToGrid(rawW)}px`;
                if (rawH > 180) panel.style.height = `${snapToGrid(rawH)}px`;
            }
        });

        document.addEventListener('mouseup', () => {
            if (isDragging || isResizing) {
                isDragging = false;
                isResizing = false;
                panel.classList.remove('dragging');
                saveLayout();
            }
        });
    });

    // Reset Layout Button
    document.getElementById('btn-reset-layout').addEventListener('click', () => {
        document.getElementById('widget-face').style.cssText = 'top: 70px; left: 30px; width: 320px; height: 340px;';
        document.getElementById('widget-chat').style.cssText = 'top: 70px; left: 370px; width: 560px; height: 650px;';
        document.getElementById('widget-audio').style.cssText = 'top: 430px; left: 30px; width: 320px; height: 290px;';
        document.getElementById('widget-logs').style.cssText = 'top: 70px; left: 950px; width: 300px; height: 650px;';
        saveLayout();
    });
}

// Layout Persistence
function saveLayout() {
    const layout = {};
    document.querySelectorAll('.widget-panel').forEach(p => {
        layout[p.id] = {
            top: p.style.top,
            left: p.style.left,
            width: p.style.width,
            height: p.style.height
        };
    });
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.save_widget_layout(JSON.stringify(layout));
    }
}

// Chat UI Logic
function initChat() {
    const input = document.getElementById('chat-input');
    const btnSend = document.getElementById('btn-send');
    const messages = document.getElementById('chat-messages');

    function appendMessage(role, text) {
        const div = document.createElement('div');
        div.className = `msg ${role}`;
        const icon = role === 'user' ? 'fa-user' : 'fa-robot';
        div.innerHTML = `
            <div class="avatar"><i class="fa-solid ${icon}"></i></div>
            <div class="bubble">${escapeHtml(text)}</div>
        `;
        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    }

    function handleSend() {
        const text = input.value.strip ? input.value.strip() : input.value.trim();
        if (!text) return;
        appendMessage('user', text);
        input.value = '';

        // Animate Friday core face to processing state
        setCoreState('processing', 'PROCESSING REQUEST...');

        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.send_message(text).then(res => {
                appendMessage('assistant', res);
                setCoreState('idle', 'IDLE & STANDING BY');
            }).catch(err => {
                appendMessage('assistant', '⚠️ Error connecting to Friday backend: ' + err);
                setCoreState('idle', 'IDLE & STANDING BY');
            });
        } else {
            // Demo fallback mode
            setTimeout(() => {
                appendMessage('assistant', "Friday is online on your graph canvas! (Demo mode)");
                setCoreState('idle', 'IDLE & STANDING BY');
            }, 600);
        }
    }

    btnSend.addEventListener('click', handleSend);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSend();
    });

    window.appendChatMessage = appendMessage;
}

// Friday Face Visualizer State
function setCoreState(state, text) {
    const core = document.getElementById('friday-core');
    const statusText = document.getElementById('core-status-text');
    statusText.innerText = text;

    if (state === 'listening') {
        core.style.background = 'radial-gradient(circle, #00e676, #0052d4)';
        core.style.boxShadow = '0 0 45px #00e676';
    } else if (state === 'processing') {
        core.style.background = 'radial-gradient(circle, #ffea00, #ff6d00)';
        core.style.boxShadow = '0 0 45px #ffea00';
    } else if (state === 'speaking') {
        core.style.background = 'radial-gradient(circle, #d500f9, #651fff)';
        core.style.boxShadow = '0 0 45px #d500f9';
    } else {
        core.style.background = 'radial-gradient(circle, #00f2fe, #0052d4)';
        core.style.boxShadow = '0 0 35px #00f2fe';
    }
}

// Audio Meter & Microphones
function initAudioMeter() {
    const fill = document.getElementById('meter-fill');
    const levelVal = document.getElementById('meter-level-val');
    const micSelect = document.getElementById('mic-select');

    micSelect.addEventListener('change', () => {
        const val = micSelect.value;
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.select_microphone(val);
        }
    });

    // Poll live mic signal from backend
    setInterval(() => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.get_mic_level().then(level => {
                const pct = Math.min(100, Math.max(0, Math.round(level * 100)));
                fill.style.width = pct + '%';
                levelVal.innerText = pct + '%';
                if (pct > 15) {
                    setCoreState('listening', 'HEARING VOICE SIGNAL...');
                }
            }).catch(() => {});
        }
    }, 200);
}

// PyWebView Bridge Integration
function initPyWebViewBridge() {
    window.addEventListener('pywebviewready', () => {
        // Load stored layout
        if (window.pywebview.api.load_widget_layout) {
            window.pywebview.api.load_widget_layout().then(jsonStr => {
                if (!jsonStr) return;
                try {
                    const layout = JSON.parse(jsonStr);
                    Object.keys(layout).forEach(id => {
                        const panel = document.getElementById(id);
                        if (panel && layout[id]) {
                            if (layout[id].top) panel.style.top = layout[id].top;
                            if (layout[id].left) panel.style.left = layout[id].left;
                            if (layout[id].width) panel.style.width = layout[id].width;
                            if (layout[id].height) panel.style.height = layout[id].height;
                        }
                    });
                } catch(e) {}
            });
        }

        // Load Microphones list into dropdown
        if (window.pywebview.api.get_microphones) {
            window.pywebview.api.get_microphones().then(mics => {
                const select = document.getElementById('mic-select');
                select.innerHTML = '<option value="auto">⚡ Auto-Detect Physical Mic</option>';
                mics.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m.index;
                    opt.innerText = `[Mic ${m.index}] ${m.name}`;
                    if (m.selected) opt.selected = true;
                    select.appendChild(opt);
                });
            });
        }

        // Poll logs
        setInterval(() => {
            if (window.pywebview.api.get_logs) {
                window.pywebview.api.get_logs().then(lines => {
                    if (!lines || lines.length === 0) return;
                    const logStream = document.getElementById('log-stream');
                    logStream.innerHTML = lines.map(l => `<div class="log-line info">${escapeHtml(l)}</div>`).join('');
                    logStream.scrollTop = logStream.scrollHeight;
                });
            }
        }, 1500);
    });
}

function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
