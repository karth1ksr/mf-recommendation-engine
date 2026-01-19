from loguru import logger
from online.interaction.intent_detector import detect_intent
from online.engine.request_normalizer import RequestNormalizer
from online.engine.clarification_logic import get_missing_field, get_question_intent
from online.engine.user_snapshot import UserSnapshot
from online.engine.recommender import RecommendationEngine

from online.interaction.static_questions import get_question
from online.interaction.explanation_llm import explain, compare_funds

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
    """
    
    # 1. Detect Intent
    intent = detect_intent(text)
    logger.info(f"Detected intent: {intent}")

    # 2. Handle Specific Intents
    if intent == "COMPARE_FUNDS":
        # logic to identify which funds to compare (e.g., from last recommendation list)
        # For now, we'll try to find any mentioned names or indices.
        # This is a placeholder for more complex extraction logic.
        return {
            "type": "comparison",
            "message": "Please specify the two funds you would like to compare from the list."
        }

    if intent == "PROVIDE_PREFERENCE" or intent == "START_RECOMMENDATION":
        preferences = normalizer.normalize(text)
        snapshot.update_from_preferences(preferences)
        logger.debug(f"Snapshot updated with preferences: {preferences}")

    # 3. Check snapshot completeness
    if not snapshot.is_complete():
        # 4. Handle Incomplete Snapshot - Determine what to ask next
        missing_field = get_missing_field(snapshot)
        question_intent = get_question_intent(missing_field)
        question_text = get_question(question_intent)
        
        logger.info(f"Snapshot incomplete. Missing field: {missing_field}. Intent: {question_intent}")
        
        return {
            "type": "question",
            "question_intent": question_intent,
            "text": question_text
        }

    # 5. Handle Complete Snapshot - Generate Recommendations
    logger.info("Snapshot complete. Generating recommendations.")
    recommendations = await recommender.get_recommendations(snapshot)
    
    # Add human-friendly explanation using LLM
    explanation = explain(snapshot.__dict__, recommendations)
    
    return {
        "type": "recommendation",
        "data": recommendations,
        "explanation": explanation
    }
