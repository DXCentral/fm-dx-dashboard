import streamlit as st
import pandas as pd
import pydeck as pdk
from google.cloud import bigquery
from google.oauth2 import service_account
from streamlit_option_menu import option_menu

# 1. THEME & UI STYLING
st.set_page_config(layout="wide", page_title="SEDAP Control Center")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@200;300;400;700&display=swap');
    
    html, body, [class*="st-"] {
        font-family: 'Oswald', sans-serif !important;
        background-color: #000000;
        color: #FFFFFF;
        font-weight: 300;
    }

    /* KILL STREAMLIT INTERNAL ICON TEXT LEAKS */
    [data-testid="stSidebarNavSeparator"], 
    [data-testid="stSidebarCollapseButton"] button div,
    .st-emotion-cache-p5msec { 
        display: none !important; 
    }

    h1, h2, h3, h4 { 
        color: #D32F2F !important; 
        font-family: 'Oswald', sans-serif !important;
        font-weight: 400; 
        text-transform: uppercase; 
        letter-spacing: 3px;
    }

    [data-testid="stSidebar"] {
        background-color: #0A0A0A;
        border-right: 1px solid #1A1A1A;
        min-width: 300px !important;
        max-width: 350px !important;
    }

    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; font-weight: 200; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; }

    /* Centering Data Table Content */
    [data-testid="stTable"] td { text-align: center !important; }
    [data-testid="stDataFrame"] div[data-testid="stTable"] div { justify-content: center !important; }

    div.stButton > button {
        background-color: #D32F2F !important;
        color: white !important;
        border-radius: 4px !important;
        border: none !important;
        padding: 5px 20px !important;
        font-size: 0.8rem !important;
        letter-spacing: 2px;
        text-transform: uppercase;
        font-family: 'Oswald', sans-serif !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING
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
        df['Local_Date'] = pd.to_datetime(df['Local_Date']).dt.date
        latest_date = df['Local_Date'].max()
        return df, latest_date
    except Exception as e:
        st.error(f"Link Error: {e}")
        return pd.DataFrame(), "Error"

df, last_log_date = load_data()

# 3. SIDEBAR NAVIGATION
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(
        menu_title="DATA MODULES",
        options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC RADIUS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"],
        icons=["speedometer2", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], 
        menu_icon="terminal",
        default_index=0,
        styles={
            "container": {"background-color": "#0A0A0A", "padding": "0px"},
            "icon": {"color": "#888", "font-size": "16px"},
            "nav-link": {
                "color": "white", 
                "font-family": "Oswald, sans-serif", 
                "font-size": "13px", 
                "text-align": "left", 
                "letter-spacing": "1.5px", 
                "text-transform": "uppercase",
                "white-space": "nowrap"
            },
            "nav-link-selected": {"background-color": "#D32F2F"},
            "menu-title": {"color": "#D32F2F", "font-family": "Oswald", "font-size": "11px", "letter-spacing": "3px"}
        }
    )
    st.markdown("---")
    st.caption(f"LOGS THROUGH: {last_log_date}")

# 4. STATIC HEADER & GLOBAL FILTERS
st.image("SEDAP Banner.png", width=600)

def reset_all():
    for key in st.session_state.keys():
        if key.startswith("filt_"): st.session_state[key] = "All"

# Explicit label and suppressed icon leak
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

filt_df = df.copy()
# (Filter mapping logic...)
filter_map = {'Frequency': f_freq, 'DXer': f_dxer, 'Station': f_station, 'State': f_state, 'Country': f_country, 'DXer_Country': f_dxer_co, 'DXer_State_Prov': f_dxer_st, 'Local_Month': f_month, 'Local_Year': f_year, 'Month_Day': f_day, 'Distance_Distribution': f_dist, 'DXer_Region': f_reg, rds_col: f_rds}
for col, val in filter_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == str(val)]

st.markdown("---")

# 5. DASHBOARD OVERVIEW
if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Total Logs", f"{len(filt_df):,}")
    m2.metric("Unique Stations", f"{filt_df['Station'].nunique():,}")
    m3.metric("US States", filt_df[filt_df['Country'] == 'USA']['State'].nunique())
    m4.metric("Canadian Provinces", filt_df[filt_df['Country'] == 'Canada']['State'].nunique())
    m5.metric("Mexican States", filt_df[filt_df['Country'] == 'Mexico']['State'].nunique())
    m6.metric("Total Countries", filt_df['Country'].nunique())
    dist_col = 'Distance__mi_' if 'Distance__mi_' in df.columns else 'Distance'
    max_d = filt_df[dist_col].max() if not filt_df.empty else 0
    m7.metric("Furthest Reception", f"{max_d:,.0f} mi")

    st.subheader("Submitted Logs")
    row_count = st.slider("Select rows:", 1, max(len(filt_df), 10), min(len(filt_df), 100))
    
    # Using column_config to ensure alignment and clean presentation
    st.dataframe(
        filt_df.head(row_count), 
        use_container_width=True, 
        hide_index=True,
        column_config={col: st.column_config.Column(width="medium") for col in filt_df.columns}
    )

elif selected_page == "GEOGRAPHIC RADIUS":
    st.header("Regional Density Analysis")
    tab_usa, tab_can, tab_mex = st.tabs(["🇺🇸 UNITED STATES", "🇨🇦 CANADA", "🇲🇽 MEXICO"])
    # (Maps go here next!)
