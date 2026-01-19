const API_BASE = "http://localhost:8000/api/v1";
let sessionId = localStorage.getItem("mf_session_id") || crypto.randomUUID();
localStorage.setItem("mf_session_id", sessionId);

const chatWindow = document.getElementById("chat-window");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const resetBtn = document.getElementById("reset-btn");
const recoModal = document.getElementById("reco-modal");
const closeModal = document.querySelector(".close-modal");

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
            addMessage("I've generated your personalized recommendations! ✨", "assistant");
            showRecommendations(data);
        }
    } catch (error) {
        removeLoading();
        addMessage("Sorry, I'm having trouble connecting to the engine. Is the backend running?", "assistant");
        console.error("API Error:", error);
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

// --- Recommendations Modal ---

function showRecommendations(recoData) {
    const listEl = document.getElementById("reco-list");
    const explanationEl = document.getElementById("reco-explanation");

    listEl.innerHTML = "";
    recoData.data.forEach(fund => {
        const card = document.createElement("div");
        card.className = "fund-card";
        card.innerHTML = `
            <div class="fund-info">
                <h4>${fund.scheme_name}</h4>
                <p>${fund.category}</p>
            </div>
            <div class="score-badge">${fund.recommendation_score}</div>
        `;
        listEl.appendChild(card);
    });

    explanationEl.innerText = recoData.explanation;
    recoModal.classList.add("visible");
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

closeModal.addEventListener("click", () => {
    recoModal.classList.remove("visible");
});

window.addEventListener("click", (e) => {
    if (e.target === recoModal) {
        recoModal.classList.remove("visible");
    }
});
