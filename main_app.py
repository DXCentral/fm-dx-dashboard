import streamlit as st
import pandas as pd
import pydeck as pdk
from google.cloud import bigquery
from google.oauth2 import service_account
from streamlit_option_menu import option_menu
import time

# 1. THEME & UI STYLING (The "Command Center" Look)
st.set_page_config(layout="wide", page_title="SEDAP Control Center")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@300;400;700&display=swap');
    
    html, body, [class*="st-"] {
        font-family: 'Oswald', sans-serif;
        background-color: #000000;
        color: #FFFFFF;
    }
    
    h1, h2, h3, h4 { color: #D32F2F !important; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; }
    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.5rem; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 1.1rem; text-transform: uppercase; }

    /* Clean Sidebar Styling */
    [data-testid="stSidebar"] { background-color: #0A0A0A; border-right: 1px solid #222; }

    /* Reset Button: Pure Red, No Highlights */
    div.stButton > button {
        background-color: #D32F2F !important;
        color: white !important;
        border-radius: 25px !important;
        border: none !important;
        padding: 10px 40px !important;
        width: 100%;
        font-family: 'Oswald', sans-serif !important;
    }
    div.stButton > button p { background-color: transparent !important; }
    
    .log-info-box {
        font-size: 1.2rem;
        color: #FFFFFF;
        margin-bottom: 25px;
        text-transform: uppercase;
        font-weight: 300;
        border-left: 4px solid #D32F2F;
        padding-left: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING (30-Day Cache)
@st.cache_data(ttl=2592000)
def load_data():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/bigquery", "https://www.googleapis.com/auth/drive.readonly"]
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = bigquery.Client(credentials=credentials, project=credentials.project_id, location="US")
        query = "SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_data_raw`"
        df = client.query(query).to_dataframe()
        
        # Date & Time Processing
        df['Local_Date'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Clean_Time'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.time
        latest_date = df['Local_Date'].max()
        
        if 'Mid_Point' in df.columns:
            df[['Mid_Lat', 'Mid_Lon']] = df['Mid_Point'].str.split(',', expand=True).apply(pd.to_numeric, errors='coerce')
            
        return df, latest_date
    except Exception as e:
        st.error(f"System Link Failure: {e}")
        return pd.DataFrame(), "Error"

df, last_log_date = load_data()
if df.empty: st.stop()

# 3. SIDEBAR NAVIGATION (Looker-Style Red Box)
with st.sidebar:
    st.image("SEDAP Banner.png", use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    selected_page = option_menu(
        menu_title="SENSORS",
        options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC RADIUS", "TIMING & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"],
        icons=["speedometer2", "cloud-haze2", "geo-alt", "clock-history", "broadcast-pin", "graph-up"], 
        menu_icon="cpu-fill",
        default_index=0,
        styles={
            "container": {"background-color": "#0A0A0A", "padding": "5px"},
            "icon": {"color": "white", "font-size": "18px"}, 
            "nav-link": {"color": "white", "font-family": "Oswald", "font-size": "14px", "text-align": "left"},
            "nav-link-selected": {"background-color": "#D32F2F"},
        }
    )
    st.markdown("---")
    st.caption(f"SYSTEM STATUS: ONLINE")

# 4. STATIC FRAME (Header & Global Filters)
st.image("SEDAP Banner.png", width=700)
st.markdown(f'<div class="log-info-box">LOG DATA THROUGH: {last_log_date}</div>', unsafe_allow_html=True)

def reset_all():
    for key in st.session_state.keys():
        if key.startswith("filt_"): st.session_state[key] = "All"

with st.expander(label="GLOBAL FILTERS", expanded=True):
    r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
    f_freq = r1c1.selectbox("Frequency", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key="filt_freq")
    f_dxer = r1c2.selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().tolist()), key="filt_dxer")
    f_station = r1c3.selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().tolist()), key="filt_station")
    f_state = r1c4.selectbox("State", ["All"] + sorted(df['State'].dropna().unique().tolist()), key="filt_state")
    f_country = r1c5.selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().tolist()), key="filt_country")

    r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
    f_dxer_co = r2c1.selectbox("DXer Country", ["All"] + sorted(df['DXer_Country'].dropna().unique().tolist()), key="filt_dx_co")
    f_dxer_st = r2c2.selectbox("DXer State", ["All"] + sorted(df['DXer_State_Prov'].dropna().unique().tolist()), key="filt_dx_st")
    f_month = r2c3.selectbox("Local Month", ["All"] + sorted(df['Local_Month'].dropna().unique().astype(str).tolist()), key="filt_month")
    f_year = r2c4.selectbox("Local Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key="filt_year")
    f_day = r2c5.selectbox("Month Day", ["All"] + sorted(df['Month_Day'].dropna().unique().astype(str).tolist()), key="filt_day")

    r3c1, r3c2, r3c3 = st.columns(3)
    f_dist = r3c1.selectbox("Distance Distribution", ["All"] + sorted(df['Distance_Distribution'].dropna().unique().tolist()), key="filt_dist")
    f_reg = r3c2.selectbox("DXer Region", ["All"] + sorted(df['DXer_Region'].dropna().unique().tolist()), key="filt_reg")
    rds_col = 'RDS_Decode_' if 'RDS_Decode_' in df.columns else 'RDS_Decode'
    f_rds = r3c3.selectbox("RDS Decode?", ["All"] + sorted(df[rds_col].dropna().unique().tolist()), key="filt_rds")

    bt_left, bt_mid, bt_right = st.columns([2, 1, 2])
    bt_mid.button("RESET ALL FILTERS", on_click=reset_all)

# SHARED FILTER LOGIC
filt_df = df.copy()
filter_map = {
    'Frequency': f_freq, 'DXer': f_dxer, 'Station': f_station, 'State': f_state,
    'Country': f_country, 'DXer_Country': f_dxer_co, 'DXer_State_Prov': f_dxer_st,
    'Local_Month': f_month, 'Local_Year': f_year, 'Month_Day': f_day,
    'Distance_Distribution': f_dist, 'DXer_Region': f_reg, rds_col: f_rds
}
for col, val in filter_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# 5. DYNAMIC CONTENT SLOTS
st.markdown("---")

if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Logs", f"{len(filt_df):,}")
    m2.metric("Stations", f"{filt_df['Station'].nunique():,}")
    m3.metric("US States", filt_df[filt_df['Country'] == 'USA']['State'].nunique())
    m4.metric("CAN Prov", filt_df[filt_df['Country'] == 'Canada']['State'].nunique())
    m5.metric("MEX States", filt_df[filt_df['Country'] == 'Mexico']['State'].nunique())
    m6.metric("Countries", filt_df['Country'].nunique())
    dist_col = 'Distance__mi_' if 'Distance__mi_' in df.columns else 'Distance'
    m7.metric("Max DX", f"{filt_df[dist_col].max() if not filt_df.empty else 0:,.0f} mi")

    st.subheader("Submitted Logs")
    row_count = st.slider("Select rows:", 1, max(len(filt_df), 10), min(len(filt_df), 100))
    st.dataframe(filt_df.head(row_count), use_container_width=True, hide_index=True)

elif selected_page == "ES-CLOUD TRACKER":
    st.header("Atmospheric Reflectivity (E-Cloud)")
    # (We will build the Time-Lapse code here next)
    st.info("Module Loading... Time-Lapse controls will appear here.")

elif selected_page == "GEOGRAPHIC RADIUS":
    st.header("Regional Density Analysis")
    region = st.radio("SELECT REGION", ["UNITED STATES", "CANADA", "MEXICO"], horizontal=True)
    st.info(f"Generating Geo-Map for {region}...")

elif selected_page == "TIMING & MUF":
    st.header("Temporal Trends & MUF Analysis")
    st.info("Module Loading... Timing Heatmaps and Peak Activity charts.")

elif selected_page == "STATION & RDS IQ":
    st.header("Station Intelligence & RDS Decodes")
    st.info("Module Loading... PI Code usage and Top Station stats.")

elif selected_page == "RECEPTION DYNAMICS":
    st.header("Path & Distance Dynamics")
    st.info("Module Loading... Double-hop vs. Short-haul distribution.")
