"""
NHS‑13426 ‑ Cohort Builder PoC [Shez]  🧬🚀
Streamlit application for interactive cohort building on Snowflake

Author : Mohamed Shez (SWE)
Created: 2025‑05‑13
Last updated: 2025‑05‑15

═══════════════════════════════════════════════════════════════════════════════
📝  Task Brief (excerpt from Jira / email)
───────────────────────────────────────────────────────────────────────────────
• *Goal*: Replace the manual mapping between
  `NHS_DATA_DEV.MEDICAL_LABS_LABELLED.PATIENT_PROCEDURES` and
  `NHS_DATA_DEV.DDP. MEDICAL_GPS_DISEASES` with a Streamlit interface.
• *Acceptance criteria*:
  1. Work in **KJB88781** using each developer’s personal schema.
  2. One Streamlit per person (learning exercise).
  3. Allow analysts to pick filterable items; *primary key focus = **DISEASE***.
  4. Persist the cohort back to Snowflake as a table.
  5. Layout can mirror examples from Snowflake‑Labs cohort‑builder repos / videos.

This file already wires those tables together via Snowpark joins and gives the
UI necessary hooks to build & save cohorts.
═══════════════════════════════════════════════════════════════════════════════
"""

import streamlit as st
from snowflake.snowpark import Session
import pandas as pd

################################################################################
# 🎨  Session‑state helpers & theming
################################################################################

def initialize_session_state():
    """Populate `st.session_state` with all keys we rely on, only once."""

    # 🎨  Brand colours that the rest of the pages can pick up
    st.session_state.card_bg_color   = st.session_state.get("card_bg_color",   "#eceff1")
    st.session_state.header_bg_color = st.session_state.get("header_bg_color", "#37474f")

    # 🗃  Core selections / cache containers
    default_keys = dict(
        build_cohort_selected_tab = 1,
        selected_database        = "",
        selected_schema          = "",
        selected_table           = "",
        prev_selected_database   = "",
        prev_selected_schema     = "",
        prev_selected_table      = "",
        table_data               = None,
        metadata_raw             = None,
        dataset                  = None,
        row_count                = None,
        table_size_mb            = None,
        dynamic_row_count        = None,
        save_changes_pressed     = False,
        llm_data_dict            = False,
        is_cohort_saved          = False,
        expander_open            = True,
        process_metadata_clicked = False,
        metadata                 = None,
        primary_filters_df       = None,
        secondary_filters_df     = None,
        filter_values            = {},
        primary_where_clause     = "",
        final_where_clause       = "",
        text_filter_conditions   = {},
        secondary_filter_values  = {},
        cohort_row_count         = None,
        base_filter_query        = "",
        selected_table_full      = "",
        cohort_query             = "",
        final_query              = "",
        cohort_name              = "",
        preview_dataset          = pd.DataFrame(),
    )

    for k, v in default_keys.items():
        st.session_state.setdefault(k, v)

################################################################################
# 🏗️  Main application class
################################################################################

class CohortBuilder:
    def __init__(self):
        # 🏠  Global page configuration (executes once)
        st.set_page_config(
            page_title="🧬 NHS Cohort Builder [Shez]",
            page_icon="🧪",
            layout="wide",
            initial_sidebar_state="expanded",
        )

    ############################################################################
    # 🔌  Snowflake connection helpers
    ############################################################################

    def connect_to_snowflake(self):
        """Return a cached Snowpark `Session`. Uses Streamlit secrets when local."""
        if "session" in st.session_state:
            return st.session_state.session

        try:
            # *Inside* Snowflake the Snowpark connector can pick the session up
            session = Session.builder.getOrCreate()
        except Exception as err_in_sf:
            try:
                # Running locally – fall back to secrets.toml
                session = Session.builder.configs(dict(st.secrets["account"])).create()
            except Exception as err_local:
                st.error(
                    f"⚠️  Could not connect to Snowflake. 1️⃣ {err_in_sf}  2️⃣ {err_local}")
                return None

        st.session_state.session = session
        return session

    ############################################################################
    # 🚪  App entry‑points
    ############################################################################

    def run(self):
        initialize_session_state()
        self.home()

    def home(self):
        with st.spinner("🔌 Connecting to Snowflake …"):
            session = self.connect_to_snowflake()

        if session:
            st.success("✅ Connected to Snowflake!")
            self.introduction()
        else:
            st.stop()

    ############################################################################
    # 📜  Landing page content
    ############################################################################

    def introduction(self):
        # Big flashy title
        st.title("🧬  NHS Cohort Builder — Welcome!  ✨")

        st.markdown(
            """
            ### Project Context  📋
            At present, analysts manually map **PATIENT_PROCEDURES** ↔ ** MEDICAL_GPS_DISEASES**.
            This app lets you filter by *disease* (primary key) plus
            other attributes, and saves the resulting cohort back to your own schema on
            **KJB88781**.
            """
        )

        st.markdown(
            """
            **Acceptance Criteria**  ✅  
            • One Streamlit per person (learning exercise)  
            • Work inside personal schemas on `KJB88781`  
            • Must persist cohort table  
            • UI inspired by Snowflake‑Labs examples
            """
        )

        st.markdown(
            """
            **Navigation 🗺️**  
            ► **Build Cohort** – pick a dataset (already joined tabled), inspect the data dictionary, apply filters and generate an SQL `WHERE` clause.  
            ► **Existing Cohorts** – browse, edit or delete previously‑saved cohorts.  
            ► **Schedule Cohorts** – turn a cohort definition into a *dynamic table*, *snapshot* or *one‑off* table.
            """
        )

        # Page summaries with fun emoji bullets
        st.markdown(
            """
            #### Page Details  📄
            1️⃣ **Build Cohort** – four steps:
            • 🗂️ *Select Dataset* – choose database / schema / table.  
            • 🔗 *Select a joined Tables* – `SYNCED_PATIENT_ID_DATA` on `DISEASE_ID`.  
            • 📖 *Data Dictionary* – fetch metadata & column stats.  
            • 🏗️ *Build* – compose filters (primary = disease) and preview row‑count.  
            • 💾 *Schedule* – persist as Dynamic / Snapshot / One‑time table.

            2️⃣ **Existing Cohorts** – 🔍 search, ✏️ edit definitions, 🗑️ delete if obsolete.

            3️⃣ **Schedule Cohorts** – ⏰ automate refresh cadences so your analysts always get fresh slices.
            """
        )

        st.markdown("""---  
        Happy Cohorting, team!  🚀🧬
        """)

################################################################################
# 🏃‍♂️  Script entry‑point
################################################################################

if __name__ == "__main__":
    CohortBuilder().run()
