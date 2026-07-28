import pandas as pd
import glob
import os

DATA_DIR = "data"
OUTPUT_DIR = "profiling"

def profile_table(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        rows.append({
            "column_name": col,
            "data_type": str(df[col].dtype),
            "null_count": df[col].isnull().sum(),
            "distinct_value_count": df[col].nunique()
        })
    return pd.DataFrame(rows)

def main():
    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for path in csv_files:
        table_name = os.path.splitext(os.path.basename(path))[0]
        df = pd.read_csv(path)
        report = profile_table(df, table_name)
        out_path = os.path.join(OUTPUT_DIR, f"{table_name}_profile.csv")
        report.to_csv(out_path, index=False)
        print(f"Profiled {table_name} -> {out_path}")

if __name__ == "__main__":
    main()