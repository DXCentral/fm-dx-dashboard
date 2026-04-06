import streamlit as st
import pandas as pd
import pydeck as pdk
from google.cloud import bigquery
from google.oauth2 import service_account
from streamlit_option_menu import option_menu
import time

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
    [data-testid="stExpanderIcon"],
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

    div.stButton > button {
        background-color: #D32F2F !important;
        color: white !important;
        border-radius: 4px !important;
        border: none !important;
        padding: 8px 25px !important;
        font-size: 0.8rem !important;
        letter-spacing: 2px;
        text-transform: uppercase;
        font-family: 'Oswald', sans-serif !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING (Pulling both tables and Joining)
@st.cache_data(ttl=2592000)
def load_data():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/bigquery", "https://www.googleapis.com/auth/drive.readonly"]
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = bigquery.Client(credentials=credentials, project=credentials.project_id, location="US")
        
        # Pull Raw Logs
        log_query = "SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_data_raw`"
        df_logs = client.query(log_query).to_dataframe()
        
        # Pull Coordinates (The new table from the other tab)
        coord_query = "SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_coords`"
        df_coords = client.query(coord_query).to_dataframe()
        
        # JOIN LOGIC: Merge Lat/Lon into the logs based on Concatenated Locations
        # Assuming df_coords has columns: 'Location_Key', 'Lat', 'Lon'
        # We perform two merges: one for the DXer and one for the Station
        df = df_logs.copy()
        
        # 1. Merge DXer Coordinates
        df = df.merge(df_coords[['Concatenated_Location', 'Latitude', 'Longitude']], 
                      left_on='DXer_Concatenated_Location', 
                      right_on='Concatenated_Location', 
                      how='left').rename(columns={'Latitude': 'DXer_Lat', 'Longitude': 'DXer_Lon'})
        
        # 2. Merge Station Coordinates
        df = df.merge(df_coords[['Concatenated_Location', 'Latitude', 'Longitude']], 
                      left_on='Station_Concatenated_Location', 
                      right_on='Concatenated_Location', 
                      how='left', 
                      suffixes=('', '_st')).rename(columns={'Latitude': 'Station_Lat', 'Longitude': 'Station_Lon'})

        # Clean up Dates/Times
        df['Local_Date'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Clean_Time'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.time
        
        # Midpoint Processing
        if 'Mid_Point' in df.columns:
            df[['Mid_Lat', 'Mid_Lon']] = df['Mid_Point'].str.split(',', expand=True).apply(pd.to_numeric, errors='coerce')
            
        return df, df['Local_Date'].max()
    except Exception as e:
        st.error(f"System Link Failure: {e}")
        return pd.DataFrame(), "Error"

df, last_log_date = load_data()

# 3. SIDEBAR NAVIGATION
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(
        menu_title="DATA MODULES",
        options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC RADIUS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"],
        icons=["speedometer2", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], 
        default_index=0,
        styles={"nav-link-selected": {"background-color": "#D32F2F"}, "nav-link": {"font-size": "13px", "white-space": "nowrap"}}
    )
    st.markdown("---")
    st.caption(f"LOGS THROUGH: {last_log_date}")

# 4. GLOBAL FILTERS (Standard Frame)
st.image("SEDAP Banner.png", width=600)
# (Your 13-box filter grid goes here...)

# --- FILTER APPLICATION ---
filt_df = df.copy() 
# (Apply your filter mapping logic here...)

# 5. ES-CLOUD TRACKER MODULE
if selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    
    # MODULE SUB-NAV
    m_type = st.radio("SELECT DISPLAY MODE", ["Midpoint Heatmap (Es-Cloud)", "Path Line Analysis (Signal Grid)"], horizontal=True)
    
    # TIME-LAPSE CONTROLS
    t1, t2 = st.columns([3, 1])
    target_date = t1.date_input("Select Event Date", value=last_log_date)
    day_df = filt_df[filt_df['Local_Date'] == target_date].dropna(subset=['Clean_Time'])
    
    if not day_df.empty:
        times = sorted(day_df['Clean_Time'].unique())
        if 'anim_idx' not in st.session_state: st.session_state.anim_idx = 0
        
        selected_time = st.select_slider("Temporal Scrub", options=times, value=times[min(st.session_state.anim_idx, len(times)-1)])
        st.session_state.anim_idx = times.index(selected_time)
        
        # Player Buttons
        p1, p2, p3 = st.columns([1, 1, 2])
        if p1.button("▶ PLAY"):
            for i in range(st.session_state.anim_idx, len(times)):
                st.session_state.anim_idx = i
                time.sleep(0.05)
                st.rerun()
        if p2.button("⏹ RESET"): st.session_state.anim_idx = 0; st.rerun()
        if p3.button("🎥 RECORD (ALPHA)"): st.info("Sequence initialized. Use system screen-capture to record output.")

        # MAP PROCESSING
        # 60-minute window for "Cloud" persistence
        window_start = (pd.to_datetime(str(selected_time)) - pd.Timedelta(minutes=60)).time()
        map_data = day_df[(day_df['Clean_Time'] <= selected_time) & (day_df['Clean_Time'] >= window_start)]
        
        layers = []
        if m_type == "Midpoint Heatmap (Es-Cloud)":
            layers.append(pdk.Layer(
                'HeatmapLayer', data=map_data, get_position='[Mid_Lon, Mid_Lat]',
                radius_pixels=80, intensity=1, threshold=0.05,
                color_range=[[211, 47, 47, 50], [211, 47, 47, 180], [255, 255, 255, 255]]
            ))
        else:
            # Path Analysis (3D Arcs)
            # Grouping by paths to determine line thickness
            path_counts = map_data.groupby(['DXer_Lat', 'DXer_Lon', 'Station_Lat', 'Station_Lon']).size().reset_index(name='density')
            layers.append(pdk.Layer(
                'ArcLayer', data=path_counts,
                get_source_position='[DXer_Lon, DXer_Lat]', get_target_position='[Station_Lon, Station_Lat]',
                get_width='density * 1.5', # Thicker for high-density paths
                get_source_color=[211, 47, 47, 160], # Soft Red
                get_target_color=[255, 255, 255, 160], # White
                pickable=True
            ))

        st.pydeck_chart(pdk.Deck(
            map_style='mapbox://styles/mapbox/dark-v10',
            initial_view_state=pdk.ViewState(latitude=39, longitude=-98, zoom=3.8, pitch=45),
            layers=layers,
            tooltip={"text": "Logs on this path: {density}" if m_type != "Midpoint Heatmap (Es-Cloud)" else "Concentration detected"}
        ))
    else:
        st.warning("Insufficient data for target parameters.")
