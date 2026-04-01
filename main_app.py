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
    h1, h2, h3, h4 { color: #D32F2F !important; font-weight: 700; text-transform: uppercase; }
    
    /* Metric / Counter Boxes */
    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 1.1rem; text-transform: uppercase; }

    /* Custom Red Rounded Buttons */
    div.stButton > button {
        background-color: #D32F2F;
        color: white;
        border-radius: 25px;
        border: 2px solid #D32F2F;
        padding: 10px 25px;
        font-family: 'Oswald', sans-serif;
    }
    div.stButton > button:hover {
        background-color: #FFFFFF;
        color: #D32F2F;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING (BigQuery + Google Sheets)
@st.cache_data(ttl=3600) # Caches data for 1 hour to keep it fast
def load_data():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        # Drive scope is required for Google-Sheet-backed BigQuery tables
        scopes = [
            "https://www.googleapis.com/auth/bigquery",
            "https://www.googleapis.com/auth/drive.readonly"
        ]
        
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = bigquery.Client(credentials=credentials, project=credentials.project_id, location="US")
        
        query = "SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_data_raw`"
        df = client.query(query).to_dataframe()
        
        # Coordinate Splitting Logic
        if 'Mid_Point' in df.columns:
            # We use errors='coerce' to handle any malformed lat/long strings
            df[['Mid_Lat', 'Mid_Lon']] = df['Mid_Point'].str.split(',', expand=True).apply(pd.to_numeric, errors='coerce')
        return df
    except Exception as e:
        st.error(f"Error connecting to BigQuery: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("No data found. Please check your BigQuery connection and Google Sheet sharing settings.")
    st.stop()

# 3. TOP SECTION: LOGO & FILTERS
st.image("SEDAP Banner.png", use_container_width=True)

# Helper function to create clean, sorted dropdown options without Nulls
def get_options(column_name):
    if column_name not in df.columns:
        return ["All"]
    return ["All"] + sorted([str(x) for x in df[column_name].dropna().unique()])

with st.expander("GLOBAL FILTERS", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    c5, c6, c7, c8 = st.columns(4)
    c9, c10, c11, c12 = st.columns(4)
    c13, c14 = st.columns([1, 3])
    
    f_freq = c1.selectbox("Frequency", get_options('Frequency'))
    f_dxer = c2.selectbox("DXer Name", get_options('DXer'))
    f_station = c3.selectbox("Station", get_options('Station'))
    f_state = c4.selectbox("State", get_options('State'))
    
    f_country = c5.selectbox("Country", get_options('Country'))
    f_dx_country = c6.selectbox("DXer Country", get_options('DXer_Country'))
    f_dx_state = c7.selectbox("DXer State", get_options('DXer_State_Prov'))
    f_month = c8.selectbox("Local Month", get_options('Local_Month'))
    
    f_year = c9.selectbox("Local Year", get_options('Local_Year'))
    f_day = c10.selectbox("Month Day", get_options('Month_Day'))
    f_dist = c11.selectbox("Distance Distribution", get_options('Distance_Distribution'))
    f_region = c12.selectbox("DXer Region", get_options('DXer_Region'))
    
    rds_col = 'RDS_Decode_' if 'RDS_Decode_' in df.columns else 'RDS_Decode'
    f_rds = c13.selectbox("RDS Decode?", get_options(rds_col))
    
    if c14.button("RESET ALL FILTERS"):
        st.rerun()

# --- FILTERING LOGIC ---
filt_df = df.copy()
# Mapping of filter variables to DataFrame columns
filters = {
    'Frequency': f_freq,
    'DXer': f_dxer,
    'Station': f_station,
    'State': f_state,
    'Country': f_country,
    'DXer_Country': f_dx_country,
    'DXer_State_Prov': f_dx_state,
    'Local_Month': f_month,
    'Local_Year': f_year,
    'Month_Day': f_day,
    'Distance_Distribution': f_dist,
    'DXer_Region': f_region,
    rds_col: f_rds
}

for col, val in filters.items():
    if val != "All":
        # Force column to string comparison for consistency
        filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# 4. CONTENT: GENERAL STATS
st.header("General Stats")

# Identify naming variants for Distance
dist_col = 'Distance__mi_' if 'Distance__mi_' in df.columns else 'Distance'

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Total Stations", f"{len(filt_df):,}")
m2.metric("States/DC", filt_df['State'].dropna().nunique())
m3.metric("Countries", filt_df['Country'].dropna().nunique())
m4.metric("CAN Prov", filt_df[filt_df['Country'] == 'CAN']['DXer_State_Prov'].dropna().nunique())
m5.metric("MEX States", filt_df[filt_df['Country'] == 'MEX']['DXer_State_Prov'].dropna().nunique())

# Distance calculation (Handles empty sets gracefully)
max_dist = 0
if not filt_df.empty and dist_col in filt_df.columns:
    max_dist = filt_df[dist_col].max()
m6.metric("Max Distance", f"{max_dist:,.0f} mi")

st.subheader("Raw Logging Data")
# Displaying the main logging columns for the table
table_cols = ['Local_Date', 'Frequency', 'Station', 'City', 'State', dist_col]
# Check if columns exist before showing table
available_cols = [c for c in table_cols if c in filt_df.columns]
st.dataframe(filt_df[available_cols], use_container_width=True)

# Export Functionality
csv = filt_df.to_csv(index=False).encode('utf-8')
st.download_button("EXPORT TABLE TO CSV", data=csv, file_name="dx_logs_export.csv", mime="text/csv")
