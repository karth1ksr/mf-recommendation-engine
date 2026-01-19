"""
[LLD 4.7] Interaction Layer - Static Questions.

This module provides deterministic, pre-defined questions for the 
recommendation engine's clarification phase. It ensures consistency 
and low latency by avoiding LLM calls for basic information gathering.
"""

def get_question(intent: str) -> str:
    """
    Returns a static question based on the provided system intent.
    
    Args:
        intent (str): The clarification intent identified by the engine.
        
    Returns:
        str: The corresponding question string or a fallback message.
    """
    
    mapping = {
        "ASK_RISK_PREFERENCE": "What level of risk are you comfortable with? (low / moderate / high)",
        "ASK_TIME_HORIZON": "How long do you plan to invest for? (in years)",
        "ASK_CATEGORY_PREFERENCE": "Which category do you prefer Equity / Debt / Hybrid?"
    }
    
    return mapping.get(intent, "Could you please provide more details about your investment goals?")
