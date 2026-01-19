from loguru import logger

"""
[LLD 4.1] Interaction Layer - Intent Detector.

This module provides deterministic intent detection for the Mutual Fund Recommendation Engine.
It uses keyword-based rules to categorize user input without relying on LLMs for reasoning,
ensuring low latency and predictable behavior.
"""

def detect_intent(text: str) -> str:
    """
    Categorizes the user's input into one of the predefined intents based on keyword matches.
    
    The detection logic follows a priority-based sequence to handle multi-keyword phrases 
    deterministically (e.g., "Compare low risk funds" is prioritized as COMPARE_FUNDS over PROVIDE_PREFERENCE).

    Intents:
        - START_RECOMMENDATION: Initializing the recommendation flow or asking for advice.
        - PROVIDE_PREFERENCE: Supplying specific constraints like risk, time, or asset class.
        - ASK_EXPLANATION: Requesting the rationale or 'why' behind a recommendation.
        - COMPARE_FUNDS: Asking for a side-by-side comparison between schemes.
        - UNKNOWN: Fallback for inputs that do not match any known pattern.

    Args:
        text (str): The raw input string from the user.

    Returns:
        str: The detected intent identifier (e.g., "PROVIDE_PREFERENCE").
    """
    
    # 1. Validation and Normalization
    if not text or not isinstance(text, str):
        logger.warning(f"Invalid input received for intent detection: {type(text)}")
        return "UNKNOWN"

    # Normalize for uniform matching (lowercase, stripped)
    clean_text = text.lower().strip()
    logger.debug(f"Processing text for intent detection: '{clean_text}'")

    # 2. Intent Keyword Mapping
    # Rule Priority Order: Comparison > Explanation > Start > Preference
    
    # Intent: COMPARE_FUNDS
    comparison_keywords = [
        "compare", "vs", "versus", "difference between", 
        "better than", "which one is better", "contrast", "alternatives"
    ]
    if any(kw in clean_text for kw in comparison_keywords):
        logger.info("Intent detected: COMPARE_FUNDS")
        return "COMPARE_FUNDS"

    # Intent: ASK_EXPLANATION
    explanation_keywords = [
        "why", "reason", "explain", "basis", "justify", 
        "details", "elaborate", "tell me more", "how did you"
    ]
    if any(kw in clean_text for kw in explanation_keywords):
        logger.info("Intent detected: ASK_EXPLANATION")
        return "ASK_EXPLANATION"

    # Intent: START_RECOMMENDATION
    # Keywords indicating a desire to begin a search or get advice
    start_keywords = [
        "start", "invest", "recommend", "suggest", "find", 
        "get advice", "begin", "setup", "new portfolio", "advice"
    ]
    if any(kw in clean_text for kw in start_keywords):
        logger.info("Intent detected: START_RECOMMENDATION")
        return "START_RECOMMENDATION"

    # Intent: PROVIDE_PREFERENCE
    # Keywords related to specific financial parameters or constraints
    preference_keywords = [
        "risk", "return", "equity", "debt", "conservative", 
        "aggressive", "moderate", "horizon", "duration", 
        "years", "months", "timeframe", "volatility", "growth",
        "low", "medium", "high", "tax saving"
    ]
    if any(kw in clean_text for kw in preference_keywords):
        logger.info("Intent detected: PROVIDE_PREFERENCE")
        return "PROVIDE_PREFERENCE"

    # 3. Fallback
    logger.info("No matching intent found. Defaulting to UNKNOWN.")
    return "UNKNOWN"
