from loguru import logger
from online.backend.interaction.intent_detector import detect_intent
from online.backend.engine.request_normalizer import RequestNormalizer
from online.backend.engine.clarification_logic import get_missing_field, get_question_intent
from online.backend.engine.user_snapshot import UserSnapshot
from online.backend.engine.recommender import RecommendationEngine

from online.backend.interaction.static_questions import get_question
from online.backend.interaction.explanation_llm import explain, compare_funds

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
    recommender: RecommendationEngine,
    history: list[dict] = None
) -> dict:
    """
    Main entry point for processing a user's natural language input.
    """
    
    # 1. Detect Intent
    intent = detect_intent(text)
    logger.info(f"Detected intent: {intent}")

    # 2. Handle Specific Intents
    if intent == "COMPARE_FUNDS":
        return {
            "type": "comparison",
            "message": "Please specify the two funds you would like to compare from the list."
        }

    if intent in ["PROVIDE_PREFERENCE", "START_RECOMMENDATION"]:
        # Upgraded to await asynchronous LLM-enabled normalization
        preferences = await normalizer.normalize(text, history)
        snapshot.update_from_preferences(preferences)
        logger.debug(f"Snapshot updated with preferences: {preferences}")

    # 3. Check snapshot completeness
    if not snapshot.is_complete():
        # 4. Handle Incomplete Snapshot
        missing_field = get_missing_field(snapshot)
        question_intent = get_question_intent(missing_field)
        question_text = get_question(question_intent)
        
        logger.info(f"Snapshot incomplete. Missing field: {missing_field}")
        
        return {
            "type": "question",
            "question_intent": question_intent,
            "text": question_text
        }

    # 5. Handle Complete Snapshot
    logger.info("Snapshot complete. Generating recommendations.")
    recommendations = await recommender.get_recommendations(snapshot)
    
    # Explain why these funds were chosen
    explanation = explain(snapshot.__dict__, recommendations)
    
    return {
        "type": "recommendation",
        "data": recommendations,
        "explanation": explanation
    }
