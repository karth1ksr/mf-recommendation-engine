class RequestNormalizer:
    """
    [LLD 4.3] Pure rule-based / regex / keyword logic to convert user utterance
    into structured machine-readable intent.
    """
    def __init__(self):
        pass

    def normalize(self, utterance: str, context: dict = None) -> dict:
        # TODO: Implement keyword extraction
        return {
            "investment_goal": None,
            "risk_preference": None,
            "time_horizon": None,
            "constraints": {}
        }
