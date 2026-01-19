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

// --- API Calls ---

async function sendMessage(text) {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                session_id: sessionId,
                text: text
            })
        });

        const data = await response.json();
        removeLoading();

        if (data.type === "question") {
            addMessage(data.text, "assistant");
        } else if (data.type === "recommendation") {
            const msg = data.message || "I've generated your personalized recommendations! ✨";
            addMessage(msg, "assistant");
            addMessage(renderFundList(data.data), "assistant fund-results");
        } else if (data.type === "comparison_result") {
            addMessage("I've prepared a side-by-side comparison for you. Opening the details...", "assistant");
            showComparisonModal(data.funds, data.text);
        } else if (data.type === "explanation") {
            addMessage(data.text, "assistant");
        } else if (data.type === "message") {
            addMessage(data.text, "assistant");
        }
    } catch (error) {
        removeLoading();
        addMessage("Sorry, I'm having trouble connecting to the engine. Is the backend running?", "assistant");
        console.error("API Error:", error);
    }
}

function showComparisonModal(funds, analysis) {
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
                    <th>CAGR (5Y)</th>
                    <td>${(f1.norm_cagr_5y * 100).toFixed(2)}%</td>
                    <td>${(f2.norm_cagr_5y * 100).toFixed(2)}%</td>
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
    // Simple newline to BR conversion for better formatting in modal
    const formattedAnalysis = analysis.replace(/\n/g, '<br>');
    compAnalysis.innerHTML = formattedAnalysis;

    if (compModal) {
        compModal.classList.remove("hidden");
        compModal.style.display = "flex"; // Ensure it shows
    }
}

async function resetSession() {
    try {
        await fetch(`${API_BASE}/session/${sessionId}`, { method: "DELETE" });
        localStorage.removeItem("mf_session_id");
        sessionId = crypto.randomUUID();
        localStorage.setItem("mf_session_id", sessionId);
        chatWindow.innerHTML = `
            <div class="message assistant">
                <p>Session reset. How can I help you find mutual funds today?</p>
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

resetBtn.addEventListener("click", resetSession);
