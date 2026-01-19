from loguru import logger

"""
[LLD 4.4] Engine - Clarification Logic.

This module determines which user preferences are missing and maps them to 
specific question intents. It ensures a structured flow for gathering 
necessary information before making a recommendation.
"""

def get_missing_field(snapshot) -> str | None:
    """
    Identifies the next required field in order of priority.
    
    Priority:
        1. risk_level
        2. investment_horizon_years
        3. preferred_categories
        
    Args:
        snapshot: A UserSnapshot instance or any object with the required attributes.
        
    Returns:
        str | None: The name of the first missing field, or None if all are present.
    """
    # 1. Check Risk Level (Highest Priority)
    if snapshot.risk_level is None:
        logger.debug("Missing field identified: risk_level")
        return "risk_level"
    
    # 2. Check Investment Horizon
    if snapshot.investment_horizon_years is None:
        logger.debug("Missing field identified: investment_horizon_years")
        return "investment_horizon_years"
    
    logger.info("No missing fields identified. Snapshot is complete.")
    return None

def get_question_intent(missing_field: str | None) -> str | None:
    """
    Maps a missing field to a system intent representing a request for information.
    
    Args:
        missing_field (str | None): The name of the missing preference field.
        
    Returns:
        str | None: The intent ID or None.
    """
    mapping = {
        "risk_level": "ASK_RISK_PREFERENCE",
        "investment_horizon_years": "ASK_TIME_HORIZON",
        "preferred_categories": "ASK_CATEGORY_PREFERENCE"
    }
    
    intent = mapping.get(missing_field)
    if intent:
        logger.info(f"Mapped missing field '{missing_field}' to intent '{intent}'")
    return intent
