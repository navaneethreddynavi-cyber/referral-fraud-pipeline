# Referral Fraud Detection Pipeline

## Project Overview
A Python-based data engineering project that processes referral datasets, integrates customer and transaction information, and applies business rules to identify potentially invalid referral records.

## Tech Stack
- **Language:** Python
- **Libraries:** Pandas, OpenPyXL
- **Tools:** Docker, Git
- **Data Format:** CSV

## Pipeline Architecture

```text
Source CSV Files
      |
      v
Data Loading & Cleaning
      |
      v
Data Transformation
      |
      v
Timezone Standardization
      |
      v
Entity Resolution & Data Joins
      |
      v
Business Rule Validation
      |
      v
Referral Fraud Report (CSV)
```

## Key Features
- Loaded and processed multiple referral-related CSV datasets.
- Cleaned missing values, duplicates and inconsistent data.
- Standardized timestamps and timezone information.
- Integrated referral, customer, reward and transaction records.
- Applied business rules to identify potentially invalid referrals.
- Generated automated data profiling reports.

## Project Structure

```text
referral-fraud-pipeline/
├── data/
├── output/
├── profiling/
├── your_script.py
├── profile_data.py
├── requirements.txt
├── Dockerfile
└── README.md
```

## Run Locally

```bash
git clone https://github.com/navaneethreddynavi-cyber/referral-fraud-pipeline.git

cd referral-fraud-pipeline

python -m venv venv

venv\Scripts\activate

pip install -r requirements.txt

python your_script.py
```

**Output:** `output/referral_fraud_report.csv`

To generate profiling reports:

```bash
python profile_data.py
```

## Skills Demonstrated
Python | Pandas | ETL Pipelines | Data Cleaning | Data Transformation | Data Integration | Entity Resolution | Business Rule Validation | Docker

## Author
**Navaneeth Reddy Banala**
