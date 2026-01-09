import logging
import pandas as pd
from utils.string_utils import normalize_name, extract_base_name

logger = logging.getLogger(__name__)

class FundMasterIngestor:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path

    def load_csv(self) -> pd.DataFrame:
        df = pd.read_csv(self.csv_path)

        # Normalize column names
        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
        )

        return df
    
    @staticmethod
    def derive_plan_type(name: str) -> str:
        return "Direct" if "direct" in name.lower() else "Regular"

    @staticmethod
    def derive_option_type(name: str) -> str:
        name = name.lower()

        if "idcw" in name or "dividend" in name:
            return "IDCW"
        return "Growth"

    def transform(self, df: pd.DataFrame) -> list[dict]:
        records = []

        for _, row in df.iterrows():
            scheme_name = str(row["scheme_name"])

            record = {
                "fund_id": int(row["code"]),
                "scheme_name": scheme_name,
                "normalized_name": normalize_name(scheme_name),
                "base_name": normalize_name(extract_base_name(scheme_name)),
                "amc": row.get("amc"),
                "scheme_type": row.get("scheme_type"),
                "scheme_category": row.get("scheme_category"),
                "plan_type": self.derive_plan_type(scheme_name),
                "option_type": self.derive_option_type(scheme_name),
                "is_active": True,
                "eligible_for_reco": True
            }

            records.append(record)

        return records