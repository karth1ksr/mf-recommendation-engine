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

function addMessage(text, role) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.innerHTML = `<p>${text}</p>`;
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
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

async function ensureConnected() {
    if (callInstance && callInstance.meetingState() === "joined-meeting") {
        return true;
    }
    addMessage("Connecting to the Mutual Fund Advisor...", "assistant");
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

            // Handle audio tracks so we can actually hear the bot
            callInstance.on("track-started", (evt) => {
                if (evt.participant.local) return;
                if (evt.track.kind === "audio") {
                    const audio = document.createElement("audio");
                    audio.srcObject = new MediaStream([evt.track]);
                    audio.autoplay = true;
                    document.body.appendChild(audio);
                }
            });

            // Unified handler for data from the Pipecat pipeline
            callInstance.on("app-message", (evt) => {
                const data = evt.data;
                console.log("Pipeline Data:", data);

                if (data.type === "text") {
                    addMessage(data.text, "assistant");
                } else if (data.type === "recommendation") {
                    const msg = data.message || "I've generated your personalized recommendations! ✨";
                    addMessage(msg, "assistant");
                    addMessage(renderFundList(data.data), "assistant fund-results");
                } else if (data.type === "comparison_result") {
                    addMessage("I've prepared a side-by-side comparison for you. Opening the details...", "assistant");
                    showComparisonModal(data.funds, "The LLM is analyzing the data for you...", data.horizon);
                }
            });
        }

        await callInstance.join({ url: room_url });
        addMessage("Connected! You can type your request or start speaking.", "assistant");
        return true;
    } catch (err) {
        console.error("Connection failed", err);
        addMessage("Connection error. Is the backend running?", "assistant");
        return false;
    }
}

async function sendMessage(text) {
    const isConnected = await ensureConnected();
    if (!isConnected) return;

    showLoading();
    try {
        // Send the text into the Pipecat pipeline as an RTVI action or app message
        // The transport.input() in the backend will pick this up
        await callInstance.sendAppMessage({
            type: "text",
            text: text
        }, "*");

        removeLoading();
        // We don't add the assistant message here because it will come back
        // via the app-message listener or voice stream.
    } catch (error) {
        removeLoading();
        addMessage("Sorry, I'm having trouble sending that to the engine.", "assistant");
        console.error("Pipeline send error:", error);
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

resetBtn.addEventListener("click", resetSession);

// Automatically connect on page load
window.addEventListener("load", () => {
    ensureConnected();
});
