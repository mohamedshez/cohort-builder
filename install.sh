# 1. Create & activate a venv (recommended)
python -m venv venv
source venv/bin/activate        # Windows: venv\\Scripts\\activate

# 2. Install dependencies
pip install streamlit snowflake-connector-python pandas

# 3. Save your Snowflake creds
mkdir -p .streamlit
cat > .streamlit/secrets.toml <<'EOF'
[snowflake]
account = "MSVVWOV-KJB88781"
user = "MSHEZ"
password = "PLACE_YOUR_PASSWORD_HERE"
role = "ACCOUNTADMIN"
warehouse = "COHORT_BUILDER_LOAD_WH"
database = "SHEZ_RESEARCH_DEV"
schema = "MOHAMED_SHEZ"
EOF

