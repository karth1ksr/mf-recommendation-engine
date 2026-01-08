import pandas as pd

def normalize_name(name: str) -> str:
    return (
        name.lower()
        .replace("&", "and")
        .replace("-", " ")
        .replace("  ", " ")
        .strip()
    )

class TerIngestor:
    def __init__(self, file_path: str, as_of_month: str):
        self.file_path = file_path
        self.as_of_month = as_of_month

    def load(self) -> pd.DataFrame:
        df = pd.read_excel(self.file_path)

        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
        )

        return df

    @staticmethod
    def derive_plan_type(name: str) -> str:
        return "Direct" if "direct" in name else "Regular"

    def transform(self, df: pd.DataFrame, fund_map: dict) -> list[dict]:
        records = []

        for _, row in df.iterrows():
            scheme_name_raw = str(row["scheme_name"])
            scheme_name = normalize_name(scheme_name_raw)

            fund_id = fund_map.get(scheme_name)
            if not fund_id:
                continue  # unmatched scheme (normal)

            record = {
                "fund_id": fund_id,
                "plan_type": self.derive_plan_type(scheme_name),
                "ter": float(row["total_expense_ratio"]),
                "as_of_month": self.as_of_month,
                "source": "AMFI"
            }

            records.append(record)

        return records
