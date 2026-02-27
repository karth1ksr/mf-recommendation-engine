# Online Real-time Pipeline Design

## Overview
The online pipeline provides a real-time, conversational interface for users to discover mutual funds. It leverages a Voice AI pipeline (Pipecat) to handle natural language interaction while using a deterministic "Rule Engine" for the actual financial recommendations.

## Architecture & Components

### 1. Interaction Layer (Pipecat)
*   **Transport**: WebRTC/Daily for low-latency audio streaming.
*   **STT (Deepgram)**: Transcribes user speech into text in real-time.
*   **LLM (Google Gemini)**: 
    *   **Intent Recognition**: Identifies if the user is providing preferences, asking for a comparison, or seeking an explanation.
    *   **Entity Extraction**: Extracts `risk_preference` (Low/High) and `investment_horizon` (Years).
    *   **Tool Calling**: Instead of hallucinating data, the LLM calls specific tools to fetch financial data.
*   **TTS (Cartesia)**: Converts the LLM's text response back into high-quality voice.

### 2. State Management (`UserSnapshot`)
*   Maintains the short-term memory of a session.
*   Tracks what values the user has already provided.
*   Triggers the Recommendation Engine only when a "Complete Profile" is reached.

### 3. Recommendation Engine (`RecommendationEngine`)
*   **Deterministic Ranking**: Unlike the LLM, this engine uses strict mathematical formulas.
*   **Formula**: `Score = 0.4*CAGR + 0.25*Consistency + 0.2*MaxDrawdown + 0.15*ExpenseRatio`.
*   **Data Source**: Reads from the `fund_metrics` table (precomputed by the offline batch).
*   **Category Matching**: Performs SQL pattern matching to find funds in the user's preferred asset class.

### 4. Mutual Fund Tools (`MutualFundTools`)
*   Acts as the "Registry" of capabilities exposed to the LLM.
*   Includes tools for:
    *   `get_recommendations`: Fetch top N funds.
    *   `compare_funds`: Side-by-side metric comparison.
    *   `get_explanation`: Deep dive into *why* a fund was suggested.

---

## API Endpoints

### 1. `POST /api/v1/connect`
The primary entry point for the frontend to initiate a voice chat session.
*   **Action**: 
    1.  Provisions a dynamic, expiring WebRTC room via Daily.co.
    2.  Spawns a background worker (`MutualFundBot`) to join the room.
    3.  Generates a unique `session_id`.
*   **Response**: 
    ```json
    {
      "room_url": "https://your-domain.daily.co/room-id",
      "session_id": "uuid-v4-string",
      "config": { "services": { "llm": "gemini", "tts": "cartesia", "stt": "deepgram" } }
    }
    ```

### 2. `DELETE /api/v1/session/{session_id}`
Manual cleanup of a specific session and its associated bot worker.
*   **Action**: Terminates the background bot task and clears session state.

### 3. `GET /health`
Standard health check for monitoring and load balancers.
*   **Response**: `{"status": "healthy", "database": "mf_recom_db"}`

---

## Workflow Sequence

1.  **User Connects**: Bot greets via TTS.
2.  **Conversational Cycle**:
    *   User: "I want a high risk fund for 5 years."
    *   STT: Transcribes the audio.
    *   LLM: Detects "High Risk", "5 Years" -> Calls `get_recommendations`.
3.  **Engine Scoring**:
    *   Engine fetches normalized metrics.
    *   Applies weights and sorts funds.
    *   Returns structured results to LLM.
4.  **Bot Response**:
    *   LLM synthesizes a natural response: "Based on that, I'd suggest the XYZ Equity fund..."
    *   TTS: Streams speech to the user.

---

## Technical Stack
- **Framework**: FastAPI (Backend API).
- **Voice Orchestration**: Pipecat.
- **AI Services**: Deepgram (STT), Gemini 1.5 Flash (LLM), Cartesia (TTS).
- **Communication**: WebRTC (via Daily.co) & RTVI Data Channel.

---

## Project Structure
The online module is split between a real-time backend and a glassmorphism frontend:

```text
online/
├── backend/
│   ├── api/          # FastAPI routes for room provisioning (/connect)
│   ├── engine/       # Recommendation Core (Weighted ranker) & User Snapshot
│   ├── interaction/  # Pipecat pipeline, RTVI processor, and Tool Handlers
│   ├── storage/      # Asynchronous PostgreSQL access for session state (asyncpg)
│   ├── services/     # Custom wrappers for AI and transport services
│   └── main.py       # Entry point for the bot worker and HTTP server
└── frontend/
    ├── index.html    # Core layout with glassmorphism design
    ├── script.js     # RTVI Client, WebRTC handling, and UI dynamics
    └── style.css     # Modern styling for cards and chat interface
```
