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
    
    h1, h2, h3, h4 { color: #D32F2F !important; font-weight: 700; text-transform: uppercase; }
    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2rem; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 1.1rem; text-transform: uppercase; }

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

# 2. DATA LOADING (With Google Drive Scopes)
@st.cache_data
def load_data():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        # This is CRITICAL for External (Google Sheet) Tables
        scopes = [
            "https://www.googleapis.com/auth/bigquery",
            "https://www.googleapis.com/auth/drive.readonly"
        ]
        
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=scopes
        )
        
        client = bigquery.Client(credentials=credentials, project=credentials.project_id, location="US")
        
        # Querying the RAW table directly based on your Table Info
        query = "SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_data_raw`"
        df = client.query(query).to_dataframe()
        
        # Split Mid_Point string into Lat/Lon for Maps
        if 'Mid_Point' in df.columns:
            df[['Mid_Lat', 'Mid_Lon']] = df['Mid_Point'].str.split(',', expand=True).astype(float)
        return df
    except Exception as e:
        st.error(f"Error connecting to BigQuery: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("Data is empty. Ensure you have shared the Google Sheet with your Service Account email.")
    st.stop()

# 3. TOP SECTION: LOGO & FILTERS
st.image("SEDAP Banner.png", use_container_width=True)

with st.expander("GLOBAL FILTERS", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    c5, c6, c7, c8 = st.columns(4)
    c9, c10, c11, c12 = st.columns(4)
    c13, c14 = st.columns([1, 3])
    
    # Using dynamic column names from your specific dataset
    f_freq = c1.selectbox("Frequency", ["All"] + sorted(df['Frequency'].unique().tolist()))
    f_dxer = c2.selectbox("DXer Name", ["All"] + sorted(df['DXer'].unique().tolist()))
    f_station = c3.selectbox("Station", ["All"] + sorted(df['Station'].unique().tolist()))
    f_state = c4.selectbox("State", ["All"] + sorted(df['State'].unique().tolist()))
    
    f_country = c5.selectbox("Country", ["All"] + sorted(df['Country'].unique().tolist()))
    f_dx_country = c6.selectbox("DXer Country", ["All"] + sorted(df['DXer_Country'].unique().tolist()))
    f_dx_state = c7.selectbox("DXer State", ["All"] + sorted(df['DXer_State_Prov'].unique().tolist()))
    f_month = c8.selectbox("Local Month", ["All"] + sorted(df['Local_Month'].unique().tolist()))
    
    f_year = c9.selectbox("Local Year", ["All"] + sorted(df['Local_Year'].unique().tolist()))
    f_day = c10.selectbox("Month Day", ["All"] + sorted(df['Month_Day'].unique().tolist()))
    f_dist = c11.selectbox("Distance Distribution", ["All"] + sorted(df['Distance_Distribution'].unique().tolist()))
    f_region = c12.selectbox("DXer Region", ["All"] + sorted(df['DXer_Region'].unique().tolist()))
    
    # BigQuery often appends underscores to columns with special characters like 'RDS Decode?'
    rds_col = 'RDS_Decode_' if 'RDS_Decode_' in df.columns else 'RDS_Decode'
    f_rds = c13.selectbox("RDS Decode?", ["All"] + sorted(df[rds_col].unique().tolist()))
    
    if c14.button("RESET ALL FILTERS"):
        st.rerun()

# Apply Filtering Logic
filt_df = df.copy()
if f_freq != "All": filt_df = filt_df[filt_df['Frequency'] == f_freq]
if f_dxer != "All": filt_df = filt_df[filt_df['DXer'] == f_dxer]
if f_state != "All": filt_df = filt_df[filt_df['State'] == f_state]
if f_year != "All": filt_df = filt_df[filt_df['Local_Year'] == f_year]

# 4. DASHBOARD CONTENT
st.header("General Stats")

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Total Stations", len(filt_df))
m2.metric("States/DC", filt_df['State'].nunique())
m3.metric("Countries", filt_df['Country'].nunique())
m4.metric("CAN Prov", filt_df[filt_df['Country'] == 'CAN']['DXer_State_Prov'].nunique())
m5.metric("MEX States", filt_df[filt_df['Country'] == 'MEX']['DXer_State_Prov'].nunique())

# Identifying the Distance column
dist_col = 'Distance__mi_' if 'Distance__mi_' in df.columns else 'Distance'
m6.metric("Max Distance", f"{filt_df[dist_col].max()} mi")

st.subheader("Raw Logging Data")
st.dataframe(filt_df, use_container_width=True)

csv = filt_df.to_csv(index=False).encode('utf-8')
st.download_button("EXPORT TABLE TO CSV", data=csv, file_name="dx_logs.csv", mime="text/csv")
