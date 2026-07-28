import pandas as pd
import os

DATA_DIR = "data"

# Treat the literal text "null" as a real missing value when reading CSVs
NULL_VALUES = ["null", "NULL", "None", ""]

def load_data():
    tables = {}
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".csv"):
            table_name = filename.replace(".csv", "")
            path = os.path.join(DATA_DIR, filename)
            tables[table_name] = pd.read_csv(path, na_values=NULL_VALUES)
    return tables

def clean_referral_rewards(df):
    # reward_value looks like "10 days" -> extract just the number 10
    df["reward_value"] = df["reward_value"].astype(str).str.extract(r"(\d+)").astype(float)
    return df
def initcap(series):
    # Converts "john doe" -> "John Doe", leaves NaN alone
    return series.str.title()

def clean_user_logs(df):
    df["name"] = initcap(df["name"])
    # homeclub is NOT initcapped per the instructions - leave as-is
    df["is_deleted"] = df["is_deleted"].astype(bool)
    return df

def clean_user_referrals(df):
    df["referee_name"] = initcap(df["referee_name"])
    df["referral_source"] = initcap(df["referral_source"])
    return df

def clean_user_referral_logs(df):
    df["is_reward_granted"] = df["is_reward_granted"].astype(bool)
    return df

def clean_paid_transactions(df):
    df["transaction_status"] = initcap(df["transaction_status"])
    df["transaction_type"] = initcap(df["transaction_type"])
    # transaction_location looks like a club/site name - leave as-is, do NOT initcap
    return df
def convert_to_local(df, timestamp_col, timezone_col):
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], utc=True)

    def to_local(row):
        try:
            return row[timestamp_col].tz_convert(row[timezone_col])
        except Exception:
            return pd.NaT

    df[f"{timestamp_col}_local"] = df.apply(to_local, axis=1)
    return df

def convert_referrals_to_local(user_referrals_df, user_logs_df):
    referrer_tz = user_logs_df[["user_id", "timezone_homeclub"]].drop_duplicates(subset="user_id")

    df = user_referrals_df.merge(
        referrer_tz,
        left_on="referrer_id",
        right_on="user_id",
        how="left"
    )

    df["referral_at"] = pd.to_datetime(df["referral_at"], utc=True)
    df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True)

    def to_local(row, col):
        try:
            return row[col].tz_convert(row["timezone_homeclub"])
        except Exception:
            return pd.NaT

    df["referral_at_local"] = df.apply(lambda r: to_local(r, "referral_at"), axis=1)
    df["updated_at_local"] = df.apply(lambda r: to_local(r, "updated_at"), axis=1)

    df = df.drop(columns=["user_id"])
    return df
def convert_via_referral(child_df, id_col, user_referrals_local_df):
    """
    For tables that link back to user_referrals (e.g. user_referral_logs, referral_rewards),
    borrow the referrer's timezone via the already-converted user_referrals table.
    id_col = the column on child_df that matches user_referrals.referral_id (for logs)
             or user_referrals.referral_reward_id (for rewards)
    """
    ref_tz = user_referrals_local_df[["referral_id", "timezone_homeclub"]].drop_duplicates(subset="referral_id")

    df = child_df.merge(
        ref_tz,
        left_on=id_col,
        right_on="referral_id",
        how="left"
    )

    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)

    def to_local(row):
        try:
            return row["created_at"].tz_convert(row["timezone_homeclub"])
        except Exception:
            return pd.NaT

    df["created_at_local"] = df.apply(to_local, axis=1)
    return df
def convert_referral_rewards_to_local(referral_rewards_df, user_referrals_local_df):
    """
    referral_rewards has no direct link back to user_referrals.
    Instead, user_referrals.referral_reward_id points to referral_rewards.id.
    So we look up, for each reward id, which referral(s) used it, and borrow that timezone.
    """
    ref_lookup = user_referrals_local_df[["referral_reward_id", "timezone_homeclub"]].dropna(subset=["referral_reward_id"])
    ref_lookup = ref_lookup.drop_duplicates(subset="referral_reward_id")

    df = referral_rewards_df.merge(
        ref_lookup,
        left_on="id",
        right_on="referral_reward_id",
        how="left"
    )

    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)

    def to_local(row):
        try:
            return row["created_at"].tz_convert(row["timezone_homeclub"])
        except Exception:
            return pd.NaT

    df["created_at_local"] = df.apply(to_local, axis=1)
    return df
def resolve_referee(user_referrals_df, user_logs_df):
    """
    Referee identity is resolved two different ways depending on referral_source:
    - If referral_source == 'Lead': trust referee_id, join to user_logs.user_id
    - Otherwise: trust referee_name + referee_phone, join to user_logs.name + phone_number
    """
    df = user_referrals_df.copy()

    # Case 1: Lead source -> join on referee_id
    lead_mask = df["referral_source"] == "Lead"

    logs_by_id = user_logs_df[["user_id", "name", "phone_number"]].rename(
        columns={"name": "resolved_name_by_id", "phone_number": "resolved_phone_by_id"}
    )
    df = df.merge(logs_by_id, left_on="referee_id", right_on="user_id", how="left")

    # Case 2: Not Lead -> join on referee_name + referee_phone
    logs_by_name = user_logs_df[["user_id", "name", "phone_number"]].rename(
        columns={"user_id": "resolved_id_by_name"}
    )
    df = df.merge(
        logs_by_name,
        left_on=["referee_name", "referee_phone"],
        right_on=["name", "phone_number"],
        how="left"
    )

    # Now pick the correct resolved id/name/phone based on referral_source
    df["resolved_referee_id"] = df["referee_id"].where(lead_mask, df["resolved_id_by_name"])
    df["resolved_referee_name"] = df["resolved_name_by_id"].where(lead_mask, df["referee_name"])
    df["resolved_referee_phone"] = df["resolved_phone_by_id"].where(lead_mask, df["referee_phone"])

    return df
def build_master_table(tables):
    ur = tables["user_referrals"]
    user_logs = tables["user_logs"]
    statuses = tables["user_referral_statuses"]
    rewards = tables["referral_rewards"]
    transactions = tables["paid_transactions"]
    referral_logs = tables["user_referral_logs"]
    leads = tables["lead_log"]

    df = ur.copy()

    # --- Referrer info ---
    referrer_info = user_logs[["user_id", "name", "phone_number", "homeclub", "membership_expired_date", "is_deleted"]].rename(
        columns={
            "name": "referrer_name",
            "phone_number": "referrer_phone_number",
            "homeclub": "referrer_homeclub",
            "membership_expired_date": "referrer_membership_expired_date",
            "is_deleted": "referrer_is_deleted"
        }
    )
    df = df.merge(referrer_info, left_on="referrer_id", right_on="user_id", how="left", suffixes=("", "_referrer"))

    # --- Referral status ---
    status_info = statuses.rename(columns={"id": "user_referral_status_id", "description": "referral_status"})
    df = df.merge(status_info[["user_referral_status_id", "referral_status"]], on="user_referral_status_id", how="left")

    # --- Reward info ---
    rewards_clean = rewards.drop(columns=["referral_reward_id"], errors="ignore")
    reward_info = rewards_clean.rename(columns={"id": "referral_reward_id", "reward_value": "num_reward_days"})
    df = df.merge(reward_info[["referral_reward_id", "num_reward_days"]], on="referral_reward_id", how="left")

    # --- Transaction info ---
    txn_info = transactions.drop(columns=["transaction_at"]).rename(columns={"transaction_at_local": "transaction_at"})
    df = df.merge(
        txn_info[["transaction_id", "transaction_status", "transaction_at", "transaction_location", "transaction_type"]],
        on="transaction_id", how="left"
    )

    # --- Reward granted timestamp (from user_referral_logs) ---
    granted_info = referral_logs[referral_logs["is_reward_granted"] == True][["user_referral_id", "created_at_local"]].rename(
        columns={"created_at_local": "reward_granted_at"}
    )
    granted_info = granted_info.drop_duplicates(subset="user_referral_id")
    df = df.merge(granted_info, left_on="referral_id", right_on="user_referral_id", how="left")

    # --- Lead source category (only for Lead referrals) ---
    lead_info = leads.rename(columns={"lead_id": "referee_id", "source_category": "lead_source_category"})
    df = df.merge(lead_info[["referee_id", "lead_source_category"]], on="referee_id", how="left")

    df["referral_source_category"] = df.apply(
        lambda row: "Online" if row["referral_source"] == "User Sign Up"
        else "Offline" if row["referral_source"] == "Draft Transaction"
        else row["lead_source_category"] if row["referral_source"] == "Lead"
        else None,
        axis=1
    )

    return df
def add_fraud_conditions(df):
    df = df.copy()

    # Ensure these are proper datetime columns (merges can turn them into generic objects)
    # Force both to timezone-naive datetimes so all comparisons work consistently
    df["transaction_at"] = pd.to_datetime(df["transaction_at"], errors="coerce", utc=True).dt.tz_localize(None)
    df["referral_at_local"] = pd.to_datetime(df["referral_at_local"], errors="coerce", utc=True).dt.tz_localize(None)
    df["referrer_membership_expired_date"] = pd.to_datetime(
        df["referrer_membership_expired_date"], errors="coerce",utc=True
    ).dt.tz_localize(None)
    # Basic building blocks
    has_reward_value = df["num_reward_days"] > 0
    ...

    # Basic building blocks
    has_reward_value = df["num_reward_days"] > 0
    no_reward_value = df["num_reward_days"].isna() | (df["num_reward_days"] == 0)
    has_transaction = df["transaction_id"].notna()
    no_transaction = df["transaction_id"].isna()
    is_paid = df["transaction_status"] == "Paid"
    is_new_type = df["transaction_type"] == "New"
    is_successful_status = df["referral_status"] == "Berhasil"
    is_pending_or_failed = df["referral_status"].isin(["Menunggu", "Tidak Berhasil"])
    reward_granted = df["reward_granted_at"].notna()

    txn_after_referral = df["transaction_at"] > df["referral_at_local"]
    txn_before_referral = df["transaction_at"] < df["referral_at_local"]
    same_month = (df["transaction_at"].dt.to_period("M") == df["referral_at_local"].dt.to_period("M"))

    membership_active = df["referrer_membership_expired_date"] >= df["transaction_at"]
    referrer_not_deleted = df["referrer_is_deleted"] == False

    # --- VALID conditions ---
    valid_condition_1 = (
        has_reward_value & is_successful_status & has_transaction &
        is_paid & is_new_type & txn_after_referral & same_month &
        membership_active & referrer_not_deleted & reward_granted
    )
    valid_condition_2 = is_pending_or_failed & no_reward_value

    # --- INVALID conditions ---
    invalid_condition_1 = has_reward_value & ~is_successful_status
    invalid_condition_2 = has_reward_value & no_transaction
    invalid_condition_3 = no_reward_value & has_transaction & is_paid & txn_after_referral
    invalid_condition_4 = is_successful_status & no_reward_value
    invalid_condition_5 = txn_before_referral

    df["is_business_logic_valid"] = (valid_condition_1 | valid_condition_2) & ~(
        invalid_condition_1 | invalid_condition_2 | invalid_condition_3 | invalid_condition_4 | invalid_condition_5
    )

    return df
def build_final_report(master):
    final = pd.DataFrame()

    final["referral_details_id"] = range(1, len(master) + 1)
    final["referral_id"] = master["referral_id"]
    final["referral_source"] = master["referral_source"]
    final["referral_source_category"] = master["referral_source_category"]
    final["referral_at"] = master["referral_at_local"]
    final["referrer_id"] = master["referrer_id"]
    final["referrer_name"] = master["referrer_name"]
    final["referrer_phone_number"] = master["referrer_phone_number"]
    final["referrer_homeclub"] = master["referrer_homeclub"]
    final["referee_id"] = master["resolved_referee_id"]
    final["referee_name"] = master["resolved_referee_name"]
    final["referee_phone"] = master["resolved_referee_phone"]
    final["referral_status"] = master["referral_status"]
    final["num_reward_days"] = master["num_reward_days"]
    final["transaction_id"] = master["transaction_id"]
    final["transaction_status"] = master["transaction_status"]
    final["transaction_at"] = master["transaction_at"]
    final["transaction_location"] = master["transaction_location"]
    final["transaction_type"] = master["transaction_type"]
    final["updated_at"] = master["updated_at_local"]
    final["reward_granted_at"] = master["reward_granted_at"]
    final["is_business_logic_valid"] = master["is_business_logic_valid"]

    return final
def main():
    tables = load_data()

    # user_logs has duplicate rows per user_id (identical repeats) - keep one per user
    tables["user_logs"] = tables["user_logs"].drop_duplicates(subset="user_id", keep="first")
    tables["lead_log"] = tables["lead_log"].sort_values("id").drop_duplicates(subset="lead_id", keep="last")

    print("Tables loaded:")
    for name, df in tables.items():
        print(f"  {name}: {df.shape[0]} rows, {df.shape[1]} columns")

    tables["referral_rewards"] = clean_referral_rewards(tables["referral_rewards"])

    print("\nreferral_rewards after cleaning:")
    print(tables["referral_rewards"])
    tables["referral_rewards"] = clean_referral_rewards(tables["referral_rewards"])
    tables["user_logs"] = clean_user_logs(tables["user_logs"])
    tables["user_referrals"] = clean_user_referrals(tables["user_referrals"])
    tables["user_referral_logs"] = clean_user_referral_logs(tables["user_referral_logs"])
    tables["paid_transactions"] = clean_paid_transactions(tables["paid_transactions"])

    print("\nuser_logs after cleaning:")
    print(tables["user_logs"].head())
    tables["user_logs"] = convert_to_local(tables["user_logs"], "membership_expired_date", "timezone_homeclub")
    tables["paid_transactions"] = convert_to_local(tables["paid_transactions"], "transaction_at", "timezone_transaction")
    tables["lead_log"] = convert_to_local(tables["lead_log"], "created_at", "timezone_location")

    print("\npaid_transactions with local time:")
    print(tables["paid_transactions"][["transaction_id", "transaction_at", "timezone_transaction", "transaction_at_local"]].head())
    tables["user_referrals"] = convert_referrals_to_local(tables["user_referrals"], tables["user_logs"])

    print("\nuser_referrals with local time:")
    print(tables["user_referrals"][["referral_id", "referral_at", "referral_at_local"]].head())
    
    tables["user_referral_logs"] = convert_via_referral(
        tables["user_referral_logs"], "user_referral_id", tables["user_referrals"]
    )

    print("\nuser_referral_logs with local time:")
    print(tables["user_referral_logs"][["id", "user_referral_id", "created_at", "created_at_local"]].head())
    
    tables["referral_rewards"] = convert_referral_rewards_to_local(tables["referral_rewards"], tables["user_referrals"])

    print("\nreferral_rewards with local time:")
    print(tables["referral_rewards"][["id", "reward_value", "created_at", "created_at_local"]])
    
    tables["user_referrals"] = resolve_referee(tables["user_referrals"], tables["user_logs"])
    
    master = build_master_table(tables)
    print(f"\nMaster table shape: {master.shape}")
    print(master[["referral_id", "referral_source", "referral_source_category", "referral_status", "num_reward_days"]].head(10))
    
    master = add_fraud_conditions(master)

    print("\nFraud flag counts:")
    print(master["is_business_logic_valid"].value_counts(dropna=False))
    
    print("\nCross-check: status vs fraud flag")
    print(master.groupby(["referral_status", "is_business_logic_valid"], dropna=False).size())
    
    final_report = build_final_report(master)

    import os
    os.makedirs("output", exist_ok=True)
    final_report.to_csv("output/referral_fraud_report.csv", index=False)

    print(f"\nFinal report shape: {final_report.shape}")
    print(final_report.head())
    print(f"\nSaved to output/referral_fraud_report.csv")

if __name__ == "__main__":
    main()