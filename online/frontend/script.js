const API_BASE = "http://localhost:8000/api/v1";
let sessionId = localStorage.getItem("mf_session_id") || crypto.randomUUID();
localStorage.setItem("mf_session_id", sessionId);

const chatWindow = document.getElementById("chat-window");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const resetBtn = document.getElementById("reset-btn");
const compModal = document.getElementById("comp-modal");
const compTableContainer = document.getElementById("comp-table-container");
const compAnalysis = document.getElementById("comp-analysis");
const closeCompBtn = document.getElementById("close-comp");
let callInstance = null;

closeCompBtn.addEventListener("click", () => {
    compModal.classList.add("hidden");
});

// --- UI Utilities ---

let lastRole = null;
let lastMessageDiv = null;

function addMessage(text, role) {
    // If it's a special result bubble (like fund-results), always create new
    const isSpecial = role.includes("fund-results");

    if (role === "assistant" && lastRole === "assistant" && lastMessageDiv && !isSpecial) {
        // Find the paragraph and append text with a space
        const p = lastMessageDiv.querySelector("p");
        if (p) {
            p.innerHTML += " " + text;
        } else {
            lastMessageDiv.innerHTML += `<p>${text}</p>`;
        }
    } else {
        const div = document.createElement("div");
        div.className = `message ${role}`;
        div.innerHTML = `<p>${text}</p>`;
        chatWindow.appendChild(div);
        lastMessageDiv = div;
    }

    lastRole = role;
    chatWindow.scrollTop = chatWindow.scrollHeight;

    // Sync with comparison modal if open
    if (role === "assistant" && compModal && !compModal.classList.contains("hidden")) {
        // Limit sync to non-special messages (actual text)
        if (!isSpecial) {
            const formattedText = text.replace(/\n/g, '<br>');
            if (compAnalysis) {
                // If it's an append, we might want to append here too, 
                // but let's just keep the latest insight or everything for now.
                if (lastRole === "assistant") {
                    compAnalysis.innerHTML += " " + formattedText;
                } else {
                    compAnalysis.innerHTML = formattedText;
                }
            }
        }
    }
}

function showLoading() {
    const div = document.createElement("div");
    div.className = "message assistant loading";
    div.id = "loading-bubble";
    div.innerHTML = "<p>Analyzing your requirements...</p>";
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function removeLoading() {
    const loader = document.getElementById("loading-bubble");
    if (loader) loader.remove();
}

// --- Unified Interaction Logic ---

let isConnecting = false;

async function ensureConnected() {
    if (isConnecting) return false;
    if (callInstance && callInstance.meetingState() === "joined-meeting") {
        return true;
    }

    isConnecting = true;
    try {
        const response = await fetch(`${API_BASE}/connect`, { method: "POST" });
        const { room_url, session_id } = await response.json();

        sessionId = session_id;
        localStorage.setItem("mf_session_id", session_id);

        if (!callInstance) {
            // @ts-ignore
            callInstance = DailyIframe.createCallObject({
                audioSource: true,
                videoSource: false,
            });

            callInstance.on("track-started", (evt) => {
                console.log("Remote track started:", evt.participant.session_id, evt.track.kind);
                if (evt.participant.local) return;
                if (evt.track.kind === "audio") {
                    console.log("Setting up audio playback for bot...");
                    const audio = document.createElement("audio");
                    audio.srcObject = new MediaStream([evt.track]);
                    audio.autoplay = true;
                    // Some browsers need an explicit play() call after srcObject is set
                    audio.play().catch(e => console.warn("Autoplay was blocked or failed:", e));
                    document.body.appendChild(audio);
                }
            });

            callInstance.on("app-message", (evt) => {
                console.log("Raw App Message Event:", evt);
                const msg = evt.data;
                console.log("Extracted Payload:", msg);

                // --- 1. Aggressive Text Detection ---
                const botText = msg.data?.text || msg.text || msg.data?.content || msg.message?.text;
                const isTextType = ["bot-tts-text", "bot-llm-text", "text"].includes(msg.type);

                if (botText && isTextType) {
                    addMessage(botText, "assistant");
                    return;
                }

                // --- 2. Structured Data Detection ---
                if (msg.type === "recommendation") {
                    addMessage(msg.message || "I've found these recommendations:", "assistant");
                    addMessage(renderFundList(msg.data), "assistant fund-results");
                }
                else if (msg.type === "comparison_result") {
                    addMessage("Opening the comparison window...", "assistant");
                    showComparisonModal(msg.funds, msg.analysis || "Analyzing...", msg.horizon);
                }
            });
        }

        await callInstance.join({ url: room_url });
        isConnecting = false;
        return true;
    } catch (err) {
        isConnecting = false;
        console.error("Connection failed", err);
        addMessage("Connection error.", "assistant");
        return false;
    }
}

async function sendMessage(text) {
    const isConnected = await ensureConnected();
    if (!isConnected) return;

    showLoading();
    try {
        await callInstance.sendAppMessage({
            id: crypto.randomUUID(),
            label: "rtvi-ai",
            type: "send-text",
            data: {
                content: text
            }
        }, "*");
        removeLoading();
    } catch (error) {
        removeLoading();
        addMessage("Engine error.", "assistant");
    }
}

function showComparisonModal(funds, analysis, horizon) {
    const f1 = funds[0];
    const f2 = funds[1];

    let tableHtml = `
        <table class="comp-table">
            <thead>
                <tr>
                    <th>Metric</th>
                    <td><strong>${f1.scheme_name}</strong></td>
                    <td><strong>${f2.scheme_name}</strong></td>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <th>Score</th>
                    <td>${f1.recommendation_score}</td>
                    <td>${f2.recommendation_score}</td>
                </tr>
                <tr>
                    <th>CAGR (${horizon < 5 ? '3Y' : '5Y'})</th>
                    <td>${((horizon < 5 ? f1.norm_cagr_3y : f1.norm_cagr_5y) * 100).toFixed(2)}%</td>
                    <td>${((horizon < 5 ? f2.norm_cagr_3y : f2.norm_cagr_5y) * 100).toFixed(2)}%</td>
                </tr>
                <tr>
                    <th>Consistency</th>
                    <td>${f1.norm_consistency.toFixed(4)}</td>
                    <td>${f2.norm_consistency.toFixed(4)}</td>
                </tr>
                <tr>
                    <th>Max Drawdown</th>
                    <td>${f1.norm_max_drawdown.toFixed(4)}</td>
                    <td>${f2.norm_max_drawdown.toFixed(4)}</td>
                </tr>
                <tr>
                    <th>Expense Ratio</th>
                    <td>${f1.norm_expense_ratio.toFixed(4)}</td>
                    <td>${f2.norm_expense_ratio.toFixed(4)}</td>
                </tr>
                <tr>
                    <th>Category</th>
                    <td>${f1.category}</td>
                    <td>${f2.category}</td>
                </tr>
            </tbody>
        </table>
    `;

    compTableContainer.innerHTML = tableHtml;
    const formattedAnalysis = analysis.replace(/\n/g, '<br>');
    compAnalysis.innerHTML = formattedAnalysis;

    if (compModal) {
        compModal.classList.remove("hidden");
        compModal.style.display = "flex";
    }
}

async function resetSession() {
    try {
        if (callInstance) {
            await callInstance.leave();
        }
        await fetch(`${API_BASE}/session/${sessionId}`, { method: "DELETE" });
        localStorage.removeItem("mf_session_id");
        sessionId = crypto.randomUUID();
        localStorage.setItem("mf_session_id", sessionId);
        chatWindow.innerHTML = `
            <div class="message assistant">
                <p>Advisor reset. Describe your investment goals to start.</p>
            </div>
        `;
    } catch (err) {
        console.error("Reset failed", err);
    }
}

function renderFundList(funds) {
    let html = '<div class="chat-fund-list">';
    funds.forEach((fund, index) => {
        html += `
            <div class="chat-fund-card">
                <span class="rank">${index + 1}</span>
                <div class="fund-details">
                    <div class="name">${fund.scheme_name}</div>
                    <div class="meta">${fund.category} | Score: ${fund.recommendation_score}</div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    return html;
}

// --- Event Listeners ---

sendBtn.addEventListener("click", () => {
    const text = userInput.value.trim();
    if (text) {
        addMessage(text, "user");
        sendMessage(text);
        userInput.value = "";
    }
});

userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
        sendBtn.click();
    }
});

const voiceBtn = document.getElementById("voice-btn");
let isMuted = false;

async function toggleMic() {
    if (!callInstance) {
        await ensureConnected();
        return;
    }

    isMuted = !isMuted;
    await callInstance.setLocalAudio(!isMuted);

    // Update UI
    voiceBtn.innerHTML = isMuted ? "🔇" : "🎤";
    voiceBtn.title = isMuted ? "Unmute Mic" : "Mute Mic";
    voiceBtn.classList.toggle("muted", isMuted);

    addMessage(isMuted ? "Microphone muted." : "Microphone unmuted.", "assistant");
}

if (voiceBtn) voiceBtn.addEventListener("click", toggleMic);

const startBtn = document.getElementById("start-btn");

startBtn.addEventListener("click", async () => {
    startBtn.disabled = true;
    startBtn.innerText = "Connecting...";
    const success = await ensureConnected();
    if (success) {
        startBtn.classList.add("hidden");
        resetBtn.classList.remove("hidden");
    } else {
        startBtn.disabled = false;
        startBtn.innerText = "Start Chat";
    }
});

resetBtn.addEventListener("click", resetSession);

// Remove the automatic load connection to satisfy autoplay policies
// window.addEventListener("load", () => {
//     ensureConnected();
// });
