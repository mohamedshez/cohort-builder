import os
import streamlit as st
import snowflake.connector
from datetime import datetime
from textwrap import dedent

"""
Cohort Builder – Local‑Schema Edition (v6)
==============================================

⚙️ **Hard preview limit: 10 rows**
---------------------------------
The constant `QUERY_LIMIT = 10` still caps every preview *and* saved cohort
unless you raise it.

🔐 **Credential handling overhaul**
----------------------------------
1. **Preferred** – A `.streamlit/secrets.toml` file with:

   ```toml
   [snowflake]
   account = "YOUR_ACCOUNT"
   user = "MOHAMED.SHEZ@DIACEUTICS.COM"
   authenticator = "externalbrowser"
   role = "NHS_DEVELOPER"
   warehouse = "NHS_WH"        # optional
   database = "NHS_RESEARCH_DEV"  # optional
   schema = "MOHAMED_SHEZ"         # optional
   ```

2. **Fallback** – Environment variables `SNOWFLAKE_<KEY>` (e.g.
   `SNOWFLAKE_USER`, `SNOWFLAKE_ACCOUNT`, …). This lets you run the same script
   inside CI/CD or a Snowflake Python worksheet without bundling a secrets file.

If neither source is present, the app raises a clear error telling you exactly
what to create.
"""

# ---------------------------------------------------------------------------
# Constants -----------------------------------------------------------------
# ---------------------------------------------------------------------------

SOURCE_DB   = "NHS_DATA_DEV"
MY_DB       = "NHS_RESEARCH_DEV"
MY_SCHEMA   = "MOHAMED_SHEZ"
QUERY_LIMIT = 10  # ◀️  Hard row‑cap as requested

PP_SRC   = f"{SOURCE_DB}.MEDICAL_LABS_LABELLED.PATIENT_PROCEDURES"
MD_SRC   = f"{SOURCE_DB}.DDP.MEDICAL_LABS_DISEASES"
PP_LOCAL = f"{MY_DB}.{MY_SCHEMA}.PATIENT_PROCEDURES"
MD_LOCAL = f"{MY_DB}.{MY_SCHEMA}.MEDICAL_LABS_DISEASES"

# ---------------------------------------------------------------------------
# Streamlit boilerplate ------------------------------------------------------
# ---------------------------------------------------------------------------

st.set_page_config(page_title="NHS Cohort Builder", layout="wide")

@st.cache_resource(show_spinner=False)
def get_conn():
    """Create (cached) Snowflake connection.

    Tries, in order:
    1. `st.secrets["snowflake"]`
    2. Environment variables `SNOWFLAKE_<KEY>`
    """
    # 1. Try .streamlit/secrets.toml ------------------
    if "snowflake" in st.secrets:
        creds = dict(st.secrets["snowflake"])  # make a copy we can mutate
    else:
        # 2. Fallback to env vars --------------------
        env_map = {
            "user": "SNOWFLAKE_USER",
            "password": "SNOWFLAKE_PASSWORD",
            "account": "SNOWFLAKE_ACCOUNT",
            "role": "SNOWFLAKE_ROLE",
            "warehouse": "SNOWFLAKE_WAREHOUSE",
            "database": "SNOWFLAKE_DATABASE",
            "schema": "SNOWFLAKE_SCHEMA",
            "authenticator": "SNOWFLAKE_AUTHENTICATOR",
        }
        creds = {k: os.getenv(v) for k, v in env_map.items() if os.getenv(v)}

    # Minimal sanity check ----------------------------------------------
    if not creds.get("user") or not creds.get("account"):
        raise RuntimeError(
            "❌ Snowflake credentials not found.\n"
            "Provide either:\n"
            "• a .streamlit/secrets.toml with a [snowflake] block, OR\n"
            "• environment variables SNOWFLAKE_USER and SNOWFLAKE_ACCOUNT (and optionally others)."
        )

    # External browser auth requires no password
    if creds.get("authenticator", "").lower() == "externalbrowser":
        creds.pop("password", None)

    # Fill in sensible defaults so queries work even if user leaves them blank
    creds.setdefault("database", MY_DB)
    creds.setdefault("schema", MY_SCHEMA)

    return snowflake.connector.connect(**creds)

conn = get_conn()
cur  = conn.cursor()

# ---------------------------------------------------------------------------
# One‑click clone to local schema -------------------------------------------
# ---------------------------------------------------------------------------

st.sidebar.header("🗄️ Local Table Sync")

if st.sidebar.button("📥 Sync Base Tables to My Schema"):
    try:
        cur.execute(f"CREATE OR REPLACE TABLE {PP_LOCAL} CLONE {PP_SRC}")
        cur.execute(f"CREATE OR REPLACE TABLE {MD_LOCAL} CLONE {MD_SRC}")
        st.sidebar.success("Tables cloned into your schema ✅")
    except snowflake.connector.errors.ProgrammingError as e:
        st.sidebar.error(f"Clone failed: {e.msg}")

# ---------------------------------------------------------------------------
# Helper to fetch distinct values -------------------------------------------
# ---------------------------------------------------------------------------

def fetch_list(sql: str, col: str):
    return cur.execute(sql).fetch_pandas_all()[col].dropna().tolist()

# Load filter lists from *local* copies -------------------------------------
DISEASES = fetch_list(
    f"SELECT DISTINCT DISEASE_ID FROM {MD_LOCAL} ORDER BY DISEASE_ID",
    "DISEASE_ID",
)

GENDERS = ["M", "F"]

STATES = fetch_list(
    f"SELECT DISTINCT STATE FROM {PP_LOCAL} ORDER BY STATE", "STATE"
)

# ---------------------------------------------------------------------------
# Sidebar – Filters ----------------------------------------------------------
# ---------------------------------------------------------------------------

st.sidebar.header("⚙️ Cohort Filters")
selected_diseases = st.sidebar.multiselect("Disease ID (optional)", DISEASES)

yob_min, yob_max = st.sidebar.slider(
    "Year of Birth", 1900, datetime.now().year, (1950, 2010), key="yob"
)

selected_genders = st.sidebar.multiselect(
    "Gender", GENDERS, default=GENDERS, key="genders"
)

selected_states = st.sidebar.multiselect("US State", STATES, key="states")

# ---------------------------------------------------------------------------
# Cohort Builder -------------------------------------------------------------
# ---------------------------------------------------------------------------

st.title("NHS Cohort Builder – Local Schema")

if st.button("Build Cohort"):

    # -----------------------------------------------------------------------
    # Compose SQL with bound parameters -------------------------------------
    # -----------------------------------------------------------------------

    placeholders = lambda n: ",".join(["%s"] * n)

    sql_base = dedent(f"""
        SELECT pp.*, md.DISEASE_ID
        FROM   {PP_LOCAL} pp
        LEFT JOIN {MD_LOCAL} md
               ON pp.PATIENT_ID = md.PATIENT_ID
        WHERE  pp.YEAR_OF_BIRTH BETWEEN %s AND %s
          AND  pp.GENDER IN ({placeholders(len(selected_genders))})
    """)

    params = [yob_min, yob_max] + selected_genders

    if selected_diseases:
        sql_base += f"  AND md.DISEASE_ID IN ({placeholders(len(selected_diseases))})\n"
        params += selected_diseases

    if selected_states:
        sql_base += f"  AND pp.STATE IN ({placeholders(len(selected_states))})\n"
        params += selected_states

    sql_preview = sql_base + f"LIMIT {QUERY_LIMIT}"

    cohort_df = cur.execute(sql_preview, params).fetch_pandas_all()

    st.caption(f"🔎 Previewing first {len(cohort_df)} of up to {QUERY_LIMIT} rows")
    st.dataframe(cohort_df, use_container_width=True)

    # -----------------------------------------------------------------------
    # Save cohort ------------------------------------------------------------
    # -----------------------------------------------------------------------

    st.subheader(f"Save cohort to Snowflake (will also use the {QUERY_LIMIT}‑row limit)")
    with st.form("save_form", clear_on_submit=True):
        target_db     = st.text_input("Target database", value=MY_DB)
        target_schema = st.text_input("Target schema",  value=MY_SCHEMA)
        table_name    = st.text_input(
            "Table name",
            value=f"COHORT_{datetime.now():%Y%m%d_%H%M%S}",
        )
        submit = st.form_submit_button("💾 Save Table")

        if submit:
            fqtn = f"{target_db}.{target_schema}.{table_name}"
            create_sql = f"CREATE OR REPLACE TABLE {fqtn} AS {sql_preview}"
            cur.execute(create_sql, params)
            st.success(f"Cohort saved as **{fqtn}** (max {QUERY_LIMIT} rows) ✅")

# ---------------------------------------------------------------------------
# Clean‑up -------------------------------------------------------------------
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _close_conn(_conn=conn):
    _conn.close()
