from google import genai
from loguru import logger
from online.backend.core.config import get_settings

"""
[LLD 4.8] Interaction Layer - Explanation LLM.

This module leverages a Large Language Model (LLM) to transform raw, 
deterministic fund recommendations into human-friendly, personalized explanations.
It strictly adheres to the engine's rankings and does not perform any 
independent recommendation logic.
"""

def explain(snapshot: dict, recommendations: list) -> str:
    """
    Generates a natural language explanation for the provided fund recommendations.
    
    Args:
        snapshot (dict): User preferences including risk_level, horizon, etc.
        recommendations (list): List of fund dictionaries ranked by the engine.
        
    Returns:
        str: A personalized explanation or a safe fallback if the LLM call fails.
    """
    
    if not recommendations:
        return "I couldn't find any funds matching your specific criteria at the moment. Please try adjusting your risk or horizon."

    # 1. Prepare data summary for the LLM
    fund_summaries = []
    for i, fund in enumerate(recommendations, 1):
        fund_summaries.append(
            f"{i}. {fund.get('scheme_name')} (Score: {fund.get('recommendation_score')}) - "
            f"CAGR: {fund.get('norm_cagr_5y')}, Consistency: {fund.get('norm_consistency')}"
        )
    
    funds_text = "\n".join(fund_summaries)
    
    # 2. Construct Strict Prompt
    prompt = f"""
    You are a professional financial advisor. 
    Explain why the following mutual funds were recommended based on the user's profile.

    USER PROFILE:
    - Risk Level: {snapshot.get('risk_level')}
    - Investment Horizon: {snapshot.get('investment_horizon_years')} years
    - Preferred Categories: {snapshot.get('preferred_categories')}

    RECOMMENDED FUNDS (Ranked List):
    {funds_text}

    INSTRUCTIONS:
    1. DO NOT change the order or ranking of the funds provided above.
    2. DO NOT suggest any new funds, companies, or alternative investment types.
    3. Focus only on explaining the metrics (CAGR, consistency, risk) of the provided funds.
    4. Keep the tone professional, helpful, and concise.
    5. Start with a brief summary of how these funds align with their {snapshot.get('risk_level')} risk profile.

    EXPLANATION:
    """

    # 3. Secure LLM Call
    try:
        settings = get_settings()
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in settings.")

        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt
        )
        
        if response and response.text:
            logger.info("Successfully generated LLM explanation.")
            return response.text.strip()
            
    except Exception as e:
        logger.error(f"LLM Explanation failed: {str(e)}")

    # 4. Safe Fallback Logic
    return _generate_fallback_explanation(snapshot, recommendations)

def _generate_fallback_explanation(snapshot: dict, recommendations: list) -> str:
    """Provides a deterministic fallback explanation when LLM is unavailable."""
    top_fund = recommendations[0].get('scheme_name')
    count = len(recommendations)
    
    return (
        f"Based on your {snapshot.get('risk_level')} risk profile and {snapshot.get('investment_horizon_years')}-year horizon, "
        f"we have selected {count} funds that best match your criteria. "
        f"Your top recommendation is {top_fund}, which shows strong performance across CAGR and consistency metrics. "
        "Each selected fund has been scored specifically to balance growth with your preferred risk tolerance."
    )

def compare_funds(fund_a: dict, fund_b: dict) -> str:
    """
    Provides a side-by-side comparative analysis of two specific funds using LLM.
    
    Args:
        fund_a (dict): First fund to compare.
        fund_b (dict): Second fund to compare.
        
    Returns:
        str: Comparative analysis or fallback.
    """
    
    prompt = f"""
    You are a professional financial advisor.
    Compare these two mutual funds side-by-side based ONLY on the provided metrics.

    FUND A:
    - Name: {fund_a.get('scheme_name')}
    - Score: {fund_a.get('recommendation_score')}
    - CAGR (5yr): {fund_a.get('norm_cagr_5y')}
    - Consistency: {fund_a.get('norm_consistency')}
    - Max Drawdown: {fund_a.get('norm_max_drawdown')}
    - Expense Ratio: {fund_a.get('norm_expense_ratio')}

    FUND B:
    - Name: {fund_b.get('scheme_name')}
    - Score: {fund_b.get('recommendation_score')}
    - CAGR (5yr): {fund_b.get('norm_cagr_5y')}
    - Consistency: {fund_b.get('norm_consistency')}
    - Max Drawdown: {fund_b.get('norm_max_drawdown')}
    - Expense Ratio: {fund_b.get('norm_expense_ratio')}

    INSTRUCTIONS:
    1. Highlight the key differences in growth (CAGR) vs risk (Drawdown/Consistency).
    2. Explain why one scored higher than the other based on the metrics.
    3. DO NOT suggest any third alternative funds.
    4. Provide a clear table or bullet-point summary first, followed by a concise conclusion.

    COMPARISON:
    """

    try:
        settings = get_settings()
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in settings.")

        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt
        )
        
        if response and response.text:
            return response.text.strip()
            
    except Exception as e:
        logger.error(f"LLM Comparison failed: {str(e)}")

    # Fallback
    return (
        f"Comparing {fund_a.get('scheme_name')} vs {fund_b.get('scheme_name')}:\n"
        f"- {fund_a.get('scheme_name')} has a score of {fund_a.get('recommendation_score')} "
        f"with a CAGR of {fund_a.get('norm_cagr_5y')}.\n"
        f"- {fund_b.get('scheme_name')} has a score of {fund_b.get('recommendation_score')} "
        f"with a CAGR of {fund_b.get('norm_cagr_5y')}.\n"
        "Please review the individual metrics for detailed differences."
    )
