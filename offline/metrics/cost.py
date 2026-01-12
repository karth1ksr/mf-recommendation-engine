import logging

logger = logging.getLogger(__name__)

def compute_cost_metrics(ter_data: dict) -> dict:
    """
    Retrieved from monthly AMFI TER snapshot data.
    """
    if not ter_data:
        return {"expense_ratio": None}
    
    return {
        "expense_ratio": ter_data.get("ter")
    }
