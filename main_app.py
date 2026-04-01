import streamlit as st
import pandas as pd
import pydeck as pdk
from google.cloud import bigquery
from google.oauth2 import service_account

# 1. THEME & STYLING (Oswald Font + Black/Red Palette)
st.set_page_config(layout="wide", page_title="Sporadic Es Data Analysis")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@300;400;700&display=swap');
    
    html, body, [class*="st-"] {
        font-family: 'Oswald', sans-serif;
        background-color: #000000;
        color: #FFFFFF;
    }
    
    /* Soft Red Headers */
    h1, h2, h3, h4 { color: #D32F2F !important; font-weight: 700; }
    
    /* Descriptions in White */
    .stMarkdown p { color: #FFFFFF; }

    /* Rounded Red Buttons with White Text */
    div.stButton > button {
        background-color: #D32F2F;
        color: white;
        border-radius: 20px;
        border: none;
        padding: 10px 24px;
        font-family: 'Oswald', sans-serif;
    }
    
    /* Dropdown styling */
    .stSelectbox label { color: #D32F2F !important; }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING (BigQuery)
@st.cache_data
def load_data():
    # This pulls from the Streamlit Secrets we discussed earlier
    credentials = service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"])
    client = bigquery.Client(credentials=credentials, project=credentials.project_id)
    
    query = "SELECT * FROM `sporadic-es-data-analysis.FMList_Data.vw_receptions_full`"
    df = client.query(query).to_dataframe()
    
    # Split Mid_Point string into Lat/Lon for the Heatmap
    # Format: "31.7562325,-88.37510585"
    df[['Mid_Lat', 'Mid_Lon']] = df['Mid_Point'].str.split(',', expand=True).astype(float)
    
    return df

try:
    df = load_data()
except Exception as e:
    st.error("Waiting for BigQuery Credentials... Please add them to Streamlit Secrets.")
    st.stop()

# 3. GLOBAL FILTERS (Top Bar)
st.image("logo.png", width=300) # Ensure you upload logo.png to your repo
st.title("SPORADIC Es DATA ANALYSIS PROJECT")

# Create a container for the 13 filters
with st.container():
    # Creating 4 rows of 4 columns to fit all 13 + Reset
    r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
    r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
    r3_c1, r3_c2, r3_c3, r3_c4 = st.columns(4)
    r4_c1, r4_c2 = st.columns([1, 3])

    # Helper function for dropdowns
    def filter_box(col, label, key):
        options = ["All"] + sorted(df[key].unique().tolist())
        return col.selectbox(label, options, key=f"filter_{key}")

    # Row 1
    f_freq = filter_box(r1_c1, "Frequency", "Frequency")
    f_dxer = filter_box(r1_c2, "DXer Name", "DXer")
    f_stat = filter_box(r1_c3, "Station", "Station")
    f_stat_st = filter_box(r1_c4, "Station State", "State")

    # Row 2
    f_stat_co = filter_box(r2_c1, "Station Country", "Country")
    f_dxer_co = filter_box(r2_c2, "DXer Country", "DXer_Country")
    f_dxer_st = filter_box(r2_c3, "DXer State/Prov", "DXer_State_Prov")
    f_month = filter_box(r2_c4, "Local Month", "Local_Month")

    # Row 3
    f_year = filter_box(r3_c1, "Local Year", "Local_Year")
    f_day = filter_box(r3_c2, "Month Day", "Month_Day")
    f_dist = filter_box(r3_c3, "Distance Distribution", "Distance_Distribution")
    f_reg = filter_box(r3_c4, "DXer Region", "DXer_Region")

    # Row 4
    f_rds = r4_c1.selectbox("RDS Decode?", ["All"] + sorted(df['RDS_Decode_'].unique().tolist()))
    
    if r4_c2.button("RESET ALL FILTERS"):
        st.rerun()

# 4. FILTER LOGIC
filtered_df = df.copy()
# (Logic to apply each filter to filtered_df goes here - I've kept it simple for this first draft)
# Example:
if f_year != "All":
    filtered_df = filtered_df[filtered_df['Local_Year'] == f_year]

# 5. LANDING PAGE CONTENT (General Stats)
st.header("GENERAL STATS")

# Counters Row
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Stations", len(filtered_df))
c2.metric("States/DC", filtered_df['State'].nunique())
c3.metric("Countries", filtered_df['Country'].nunique())
c4.metric("Can. Provinces", filtered_df[filtered_df['Country'] == 'CAN']['DXer_State_Prov'].nunique()) # Adjust logic as needed
c5.metric("Mex. States", filtered_df[filtered_df['Country'] == 'MEX']['DXer_State_Prov'].nunique()) # Adjust logic as needed
c6.metric("Furthest", f"{filtered_df['Distance__mi_'].max()} mi")

# Raw Data Table
st.subheader("RECEPTION LOGS")
st.dataframe(filtered_df[['Local_Date', 'Frequency', 'Station', 'City', 'State', 'Distance__mi_']], use_container_width=True)
