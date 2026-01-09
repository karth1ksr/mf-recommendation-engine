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

        # Map DataFrame columns to plan types
        column_map = {
            "Regular": "regular_plan_-_total_ter_(%)",
            "Direct": "direct_plan_-_total_ter_(%)"
        }

        for _, row in df.iterrows():
            scheme_name_raw = str(row["scheme_name"])
            base_name = normalize_name(scheme_name_raw)

            # Get funds matching this base name
            matched_funds = fund_map.get(base_name, [])
            
            for fund in matched_funds:
                fund_id = fund["fund_id"]
                plan_type = fund["plan_type"]
                
                col_name = column_map.get(plan_type)
                if col_name in row and pd.notnull(row[col_name]):
                    try:
                        ter_value = float(row[col_name])
                        record = {
                            "fund_id": fund_id,
                            "plan_type": plan_type,
                            "ter": ter_value,
                            "as_of_month": self.as_of_month,
                            "source": "AMFI"
                        }
                        records.append(record)
                    except (ValueError, TypeError):
                        continue

        return records
