from loguru import logger
from online.interaction.intent_detector import detect_intent
from online.engine.request_normalizer import RequestNormalizer
from online.engine.clarification_logic import get_missing_field, get_question_intent
from online.engine.user_snapshot import UserSnapshot
from online.engine.recommender import RecommendationEngine

"""
[LLD 4.6] Engine - Orchestrator.

This module acts as the central coordinator for the online recommendation flow.
It determines the user's intent, extracts preferences, manages the session state 
(UserSnapshot), and decides whether to ask for more information or generate 
the final recommendations.
"""

async def handle_user_input(
    text: str, 
    snapshot: UserSnapshot, 
    normalizer: RequestNormalizer, 
    recommender: RecommendationEngine
) -> dict:
    """
    Main entry point for processing a user's natural language input.
    
    Orchestrates the flow from raw text to either a clarification question 
    or a list of fund recommendations.

    Args:
        text (str): The raw user input.
        snapshot (UserSnapshot): The current session state.
        normalizer (RequestNormalizer): Instance to extract structured data.
        recommender (RecommendationEngine): Instance to fetch and score funds.

    Returns:
        dict: A response object with 'type' and either 'question_intent' or 'data'.
    """
    
    # 1. Detect Intent
    intent = detect_intent(text)
    logger.info(f"Detected intent: {intent}")

    # 2. Extract and Update if Providing Preferences
    if intent == "PROVIDE_PREFERENCE":
        preferences = normalizer.normalize(text)
        snapshot.update_from_preferences(preferences)
        logger.debug(f"Snapshot updated with preferences: {preferences}")

    # 3. Check snapshot completeness
    # Completeness requires risk_level, horizon, and preferred_categories
    if not snapshot.is_complete():
        # 4. Handle Incomplete Snapshot - Determine what to ask next
        missing_field = get_missing_field(snapshot)
        question_intent = get_question_intent(missing_field)
        
        logger.info(f"Snapshot incomplete. Missing field: {missing_field}. Intent: {question_intent}")
        
        return {
            "type": "question",
            "question_intent": question_intent
        }

    # 5. Handle Complete Snapshot - Generate Recommendations
    logger.info("Snapshot complete. Generating recommendations.")
    recommendations = await recommender.get_recommendations(snapshot)
    
    return {
        "type": "recommendation",
        "data": recommendations
    }
