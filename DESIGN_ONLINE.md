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
*   **Data Source**: Reads from the `fund_metrics` collection (precomputed by the offline batch).
*   **Category Matching**: Performs fuzzy regex matching to find funds in the user's preferred asset class.

### 4. Mutual Fund Tools (`MutualFundTools`)
*   Acts as the "Registry" of capabilities exposed to the LLM.
*   Includes tools for:
    *   `get_recommendations`: Fetch top N funds.
    *   `compare_funds`: Side-by-side metric comparison.
    *   `get_explanation`: Deep dive into *why* a fund was suggested.

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
- **AI Services**: Deepgram (STT), Gemini (LLM), Cartesia (TTS).
- **Communication**: WebSockets & WebRTC.
