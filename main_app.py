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

    /* THE ULTIMATE SHIELD: Suppress internal Streamlit code/icon leaks */
    [data-testid="stSidebarCollapseButton"], 
    [data-testid="stExpanderIcon"],
    .st-emotion-cache-p5msec,
    .st-emotion-cache-1vt4y6f,
    span[data-testid="stHeaderActionElements"] { 
        display: none !important; 
        visibility: hidden !important;
    }

    h1, h2, h3, h4 { color: #D32F2F !important; font-family: 'Oswald', sans-serif !important; letter-spacing: 3px; text-transform: uppercase; }
    [data-testid="stSidebar"] { background-color: #0A0A0A; border-right: 1px solid #1A1A1A; min-width: 320px !important; }
    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; font-weight: 200; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; }

    /* Centered Data Table */
    [data-testid="stDataFrame"] td { text-align: center !important; }

    div.stButton > button {
        background-color: #D32F2F !important;
        color: white !important;
        border-radius: 4px !important;
        border: none !important;
        padding: 8px 25px !important;
        font-family: 'Oswald', sans-serif !important;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING (Path-Based Join)
@st.cache_data(ttl=2592000)
def load_data():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/bigquery", "https://www.googleapis.com/auth/drive.readonly"]
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = bigquery.Client(credentials=credentials, project=credentials.project_id, location="US")
        
        # 1. Pull Logs
        df_logs = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_data_raw`").to_dataframe()
        
        # 2. Pull 7-Column Path Coordinates
        df_paths = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_coords`").to_dataframe()
        
        # 3. JOIN: Match logs to their coordinates using BOTH locations
        # This ensures the DXer and Station coordinates are locked in correctly
        df = df_logs.merge(
            df_paths, 
            left_on=['DXer_Concatenated_Location', 'Station_Concatenated_Location'], 
            right_on=['DXer_Concatenated_Location', 'Station_Concatenated_Location'], 
            how='left'
        )

        # Process Time/Date
        df['Local_Date'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Clean_Time'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.time
        
        # Midpoint Calculation for Heatmap
        df['Mid_Lat'] = (df['DXer_Latitude'] + df['Station_Lat']) / 2
        df['Mid_Lon'] = (df['DXer_Longitude'] + df['Station_Long']) / 2
            
        return df, df['Local_Date'].max()
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
        icons=["house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], 
        default_index=0,
        styles={"nav-link-selected": {"background-color": "#D32F2F"}, "nav-link": {"font-size": "13px", "white-space": "nowrap"}}
    )
    st.markdown("---")
    st.caption(f"LOGS THROUGH: {last_log_date}")

# 4. STATIC HEADER & FILTERS
st.image("SEDAP Banner.png", width=600)
# (Filter Grid remains the same as previous Version 18.0)

# ... (Insert Filter Grid Logic) ...

# 5. ES-CLOUD TRACKER MODULE
if selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    
    view_mode = st.radio("SELECT MAP LAYER", ["Midpoint Heatmap (Es-Cloud)", "Path Line Analysis (Signal Grid)"], horizontal=True)
    
    # Time-Lapse Controls
    t_col, b_col = st.columns([3, 1])
    target_date = t_col.date_input("Event Date", value=last_log_date)
    day_df = df[df['Local_Date'] == target_date].dropna(subset=['Clean_Time', 'DXer_Latitude'])
    
    if not day_df.empty:
        times = sorted(day_df['Clean_Time'].unique())
        if 'anim_idx' not in st.session_state: st.session_state.anim_idx = 0
        
        selected_time = st.select_slider("Temporal Scrub", options=times, value=times[min(st.session_state.anim_idx, len(times)-1)])
        st.session_state.anim_idx = times.index(selected_time)
        
        # Player
        p1, p2, p3 = st.columns([1, 1, 2])
        if p1.button("▶ PLAY"):
            for i in range(st.session_state.anim_idx, len(times)):
                st.session_state.anim_idx = i
                time.sleep(0.05)
                st.rerun()
        if p2.button("⏹ RESET"): st.session_state.anim_idx = 0; st.rerun()

        # Filtering Map Window (45 minute persistence)
        window_start = (pd.to_datetime(str(selected_time)) - pd.Timedelta(minutes=45)).time()
        map_data = day_df[(day_df['Clean_Time'] <= selected_time) & (day_df['Clean_Time'] >= window_start)]
        
        layers = []
        if view_mode == "Midpoint Heatmap (Es-Cloud)":
            layers.append(pdk.Layer(
                'HeatmapLayer', data=map_data, get_position='[Mid_Lon, Mid_Lat]',
                radius_pixels=80, intensity=1, threshold=0.03,
                color_range=[[211, 47, 47, 50], [211, 47, 47, 180], [255, 255, 255, 255]]
            ))
        else:
            # Path Analysis (3D Arc Grid)
            # Group by path to calculate line thickness (density)
            path_counts = map_data.groupby(['DXer_Latitude', 'DXer_Longitude', 'Station_Lat', 'Station_Long']).size().reset_index(name='density')
            layers.append(pdk.Layer(
                'ArcLayer', data=path_counts,
                get_source_position='[DXer_Longitude, DXer_Latitude]', 
                get_target_position='[Station_Long, Station_Lat]',
                get_width='density * 2',
                get_source_color=[211, 47, 47, 140],
                get_target_color=[255, 255, 255, 140],
                pickable=True
            ))

        st.pydeck_chart(pdk.Deck(
            map_style='mapbox://styles/mapbox/dark-v10',
            initial_view_state=pdk.ViewState(latitude=39, longitude=-98, zoom=3.8, pitch=45),
            layers=layers,
            tooltip={"text": "Logs on this path: {density}"} if view_mode != "Midpoint Heatmap (Es-Cloud)" else True
        ))
    else:
        st.warning("No data found for the selected temporal window.")

# ... (Other Modules) ...
