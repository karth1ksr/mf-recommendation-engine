const API_BASE = "https://srkarthik27--mf-voice-bot-fastapi-api.modal.run";
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
const micBtn = document.getElementById("mic-btn");

let callFrame = null;
let isMicOn = false;

async function initVoice() {
    try {
        addMessage("Connecting to voice engine...", "assistant");

        const response = await fetch(`${API_BASE}/voice/join?session_id=${sessionId}`, {
            method: "POST"
        });

        const { room_url, token } = await response.json();

        // Initialize Daily call
        callFrame = DailyIframe.createCallObject();

        await callFrame.join({
            url: room_url,
            token: token,
            videoSource: false
        });

        // Set initial mic state to OFF
        await callFrame.setLocalAudio(false);
        isMicOn = false;
        micBtn.classList.add("mic-off");
        micBtn.classList.remove("mic-on");

        addMessage("Connected! You can speak or type to me.", "assistant");

        // Listen for Data Channel messages from Pipecat
        callFrame.on("app-message", (evt) => {
            const data = evt.data;
            console.log("Received data channel message:", data);

            // Path: backend DataFrame(payload) arrives here as evt.data
            handleBackendData(data);
        });

    } catch (err) {
        console.error("Failed to join voice session:", err);
        addMessage("Error connecting to voice. Please check backend.", "assistant");
    }
}

function handleBackendData(data) {
    if (!data) return;

    if (data.type === "question") {
        addMessage(data.text, "assistant");
    } else if (data.type === "recommendation") {
        const msg = data.message || "I've generated your personalized recommendations! ✨";
        addMessage(msg, "assistant");
        addMessage(renderFundList(data.data), "assistant fund-results");
    } else if (data.type === "comparison_result") {
        addMessage("I've prepared a side-by-side comparison for you. Opening the details...", "assistant");
        showComparisonModal(data.funds, data.text, data.horizon);
    } else if (data.type === "explanation" || data.type === "message") {
        addMessage(data.text, "assistant");
    }
}

function addMessage(text, role) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.innerHTML = `<p>${text}</p>`;
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function showComparisonModal(funds, analysis, horizon) {
    if (!funds || funds.length < 2) return;

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
            </tbody>
        </table>
    `;

    compTableContainer.innerHTML = tableHtml;
    const formattedAnalysis = analysis.replace(/\n/g, '<br>');
    compAnalysis.innerHTML = formattedAnalysis;

    compModal.classList.remove("hidden");
    compModal.style.display = "flex";
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

// Update sendMessage to send via Data Channel if active
async function sendMessage(text) {
    if (callFrame) {
        // Send to Pipecat via Daily app-message
        // The transport will usually broadcast this, and we need the backend to pick it up.
        // For the MFProcessor to see it, the pipeline needs to handle this frame.
        // We'll send it as a simple string or an object the backend expects.
        callFrame.sendAppMessage({ text: text }, "*");
        addMessage(text, "user");
    } else {
        addMessage("Not connected to voice engine. Click 'Connect' first.", "assistant");
    }
}

closeCompBtn.addEventListener("click", () => {
    compModal.classList.add("hidden");
    compModal.style.display = "none";
});

sendBtn.addEventListener("click", () => {
    const text = userInput.value.trim();
    if (text) {
        sendMessage(text);
        userInput.value = "";
    }
});

userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendBtn.click();
});

micBtn.addEventListener("click", async () => {
    if (!callFrame) return;

    isMicOn = !isMicOn;
    await callFrame.setLocalAudio(isMicOn);

    if (isMicOn) {
        micBtn.classList.add("mic-on");
        micBtn.classList.remove("mic-off");
    } else {
        micBtn.classList.add("mic-off");
        micBtn.classList.remove("mic-on");
    }
});

resetBtn.addEventListener("click", async () => {
    if (callFrame) {
        await callFrame.leave();
        callFrame = null;
    }
    await fetch(`${API_BASE}/session/${sessionId}`, { method: "DELETE" });
    localStorage.removeItem("mf_session_id");
    location.reload();
});

// Auto-init on first click to satisfy browser audio policies
document.body.addEventListener('click', () => {
    if (!callFrame) initVoice();
}, { once: true });
