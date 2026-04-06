import streamlit as st
import pandas as pd
import pydeck as pdk
from google.cloud import bigquery
from google.oauth2 import service_account
from streamlit_option_menu import option_menu

# 1. THEME & UI STYLING (Sleek/Narrow Refinement)
st.set_page_config(layout="wide", page_title="SEDAP Control Center")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@200;300;400;700&display=swap');
    
    /* Global Font Tweak: Using Light (300) or Extra Light (200) for that thin look */
    html, body, [class*="st-"] {
        font-family: 'Oswald', sans-serif;
        background-color: #000000;
        color: #FFFFFF;
        font-weight: 300;
    }
    
    h1, h2, h3, h4 { 
        color: #D32F2F !important; 
        font-weight: 400; 
        text-transform: uppercase; 
        letter-spacing: 3px; /* Narrow and spaced out */
    }

    /* Tightening the Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0A0A0A;
        border-right: 1px solid #1A1A1A;
        min-width: 200px !important; /* Narrower sidebar */
        max-width: 250px !important;
    }

    /* Shrink Sidebar Text */
    [data-testid="stSidebar"] .stMarkdown p {
        font-size: 0.85rem !important;
        letter-spacing: 1px;
    }

    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; font-weight: 200; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; }

    /* Narrow Reset Button */
    div.stButton > button {
        background-color: #D32F2F !important;
        color: white !important;
        border-radius: 4px !important; /* Square-ish for a tech look */
        border: none !important;
        padding: 5px 20px !important;
        font-size: 0.8rem !important;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING (Standard 30-Day Cache)
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

# 3. SIDEBAR NAVIGATION (Reduced Font Size)
with st.sidebar:
    st.image("SEDAP Banner.png", use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    selected_page = option_menu(
        menu_title="SYSTEM MODULES",
        options=[
            "DASHBOARD OVERVIEW", 
            "ES-CLOUD TRACKER", 
            "GEOGRAPHIC RADIUS", 
            "TEMPORAL TRENDS", 
            "FREQUENCY & MUF", 
            "STATION & RDS IQ", 
            "RECEPTION DYNAMICS"
        ],
        icons=["speedometer2", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], 
        menu_icon="terminal",
        default_index=0,
        styles={
            "container": {"background-color": "#0A0A0A", "padding": "0px"},
            "icon": {"color": "#888", "font-size": "14px"}, # Smaller icons
            "nav-link": {
                "color": "white", 
                "font-family": "Oswald", 
                "font-size": "12px", # Narrower, smaller font
                "text-align": "left", 
                "margin": "0px", 
                "letter-spacing": "1px",
                "text-transform": "uppercase"
            },
            "nav-link-selected": {"background-color": "#D32F2F", "font-weight": "400"},
            "menu-title": {"color": "#D32F2F", "font-family": "Oswald", "font-size": "10px", "letter-spacing": "3px"}
        }
    )
    st.markdown("---")
    st.caption(f"LOGS THROUGH: {last_log_date}")

# 4. GLOBAL FILTER FRAME
st.image("SEDAP Banner.png", width=600)

# (Filter grid logic goes here - keep your existing 13-box grid)
# ...

# 5. GEOGRAPHIC RADIUS MODULE (Tab-based maps)
if selected_page == "GEOGRAPHIC RADIUS":
    st.header("Regional Density Analysis")
    
    # Using Tabs for a clean, non-scrolling interface
    tab_usa, tab_can, tab_mex = st.tabs(["🇺🇸 UNITED STATES", "🇨🇦 CANADA", "🇲🇽 MEXICO"])
    
    with tab_usa:
        st.subheader("US Log Density by State")
        # Chloropleth map logic will go here
        st.info("Loading US Spatial Map...")
        
    with tab_can:
        st.subheader("Canadian Log Density by Province")
        st.info("Loading Canada Spatial Map...")
        
    with tab_mex:
        st.subheader("Mexican Log Density by State")
        st.info("Loading Mexico Spatial Map...")
