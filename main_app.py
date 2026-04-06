import streamlit as st
import pandas as pd
import pydeck as pdk
import time
import datetime
from google.cloud import bigquery
from google.oauth2 import service_account 

# 1. THEME & UI STYLING
st.set_page_config(layout="wide", page_title="SEDAP Control Center")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@200;300;400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Oswald', sans-serif !important; background-color: #000000; color: #FFFFFF; font-weight: 300; }
    [data-testid="stSidebarCollapseButton"] button, .st-emotion-cache-p5msec, .st-emotion-cache-1vt4y6f { display: none !important; }
    h1, h2, h3, h4 { color: #D32F2F !important; font-family: 'Oswald', sans-serif !important; text-transform: uppercase; letter-spacing: 3px; }
    [data-testid="stSidebar"] { background-color: #0A0A0A; border-right: 1px solid #1A1A1A; min-width: 320px !important; }
    div.stButton > button { background-color: #D32F2F !important; color: white !important; border-radius: 4px !important; border: none !important; padding: 8px 25px !important; text-transform: uppercase; }
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
        client = bigquery.Client(credentials=credentials, project=credentials.project_id)
        
        df_logs = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_data_raw`").to_dataframe()
        df_coords = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_coords`").to_dataframe()
        
        df = df_logs.merge(df_coords, left_on=['Concatenated_DXer_Location', 'Concatenated_Station_Location'], 
                           right_on=['DXer_Concatenated_Location', 'Station_Concatenated_Location'], how='left')

        for c_in, c_out in [('DXer_Latitude','DX_Lat'), ('DXer_Longitude','DX_Lon'), ('Station_Lat','ST_Lat'), ('Station_Long','ST_Lon')]:
            df[c_out] = pd.to_numeric(df[c_in], errors='coerce')
        
        df['Mid_Lat'] = (df['DX_Lat'] + df['ST_Lat']) / 2
        df['Mid_Lon'] = (df['DX_Lon'] + df['ST_Lon']) / 2
        df['Date_Obj'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Time_Str'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
        return df, df['Date_Obj'].max()
    except Exception as e:
        st.error(f"Critical System Error: {e}")
        return pd.DataFrame(), "Error"

df, last_log_date = load_data()

# 3. SIDEBAR & NAVIGATION
from streamlit_option_menu import option_menu
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(menu_title="DATA MODULES", options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC RADIUS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"], icons=["house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], default_index=0)

# 4. GLOBAL FILTERS
st.image("SEDAP Banner.png", width=600)
# (Filtering logic for Dashboard/Tracker...)
filt_df = df.copy()

# 5. ES-CLOUD TRACKER
if selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    view_mode = st.radio("SELECT MAP LAYER", ["Midpoint Heatmap (Es-Cloud)", "Path Line Analysis (Signal Grid)"], horizontal=True)
    
    hc1, hc2 = st.columns([1, 2])
    avail_dates = sorted(filt_df['Date_Obj'].unique())
    date_sel = hc1.date_input("Event Date Range", value=(avail_dates[0], avail_dates[-1]))
    
    # Filter by Date
    if isinstance(date_sel, tuple) and len(date_sel) == 2:
        map_df = filt_df[(filt_df['Date_Obj'] >= date_sel[0]) & (filt_df['Date_Obj'] <= date_sel[1])]
    else:
        map_df = filt_df[filt_df['Date_Obj'] == date_sel]

    if not map_df.empty:
        # Create a full 24-hour minute-by-minute list to prevent stalling at gaps
        all_minutes = [(datetime.datetime(2023, 1, 1, 0, 0) + datetime.timedelta(minutes=i)).strftime('%H:%M') for i in range(1440)]
        # Subset to only the range where data actually exists to save time
        data_times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        play_times = [m for m in all_minutes if m >= data_times[0] and m <= data_times[-1]]

        if 'play_idx' not in st.session_state: st.session_state.play_idx = 0
        if 'is_playing' not in st.session_state: st.session_state.is_playing = False

        selected_time = hc2.select_slider("Timing Control", options=["SHOW ALL"] + play_times, 
                                          value=play_times[st.session_state.play_idx] if st.session_state.is_playing else "SHOW ALL")
        
        btn1, btn2, btn3 = st.columns(3)
        if btn1.button("▶ PLAY TIMELAPSE"):
            st.session_state.is_playing = True
            for i in range(st.session_state.play_idx, len(play_times)):
                st.session_state.play_idx = i
                time.sleep(0.1) # Smooth minute-by-minute crawl
                st.rerun()
            st.session_state.is_playing = False

        if btn2.button("⏹ STOP / RESET"):
            st.session_state.is_playing = False
            st.session_state.play_idx = 0
            st.rerun()

        # Render Logic
        current_time = play_times[st.session_state.play_idx] if st.session_state.is_playing else selected_time
        
        if current_time != "SHOW ALL":
            # 60-minute window for persistence
            sel_dt = datetime.datetime.strptime(current_time, '%H:%M')
            win_start = (sel_dt - datetime.timedelta(minutes=60)).strftime('%H:%M')
            render_df = map_df[(map_df['Time_Str'] <= current_time) & (map_df['Time_Str'] >= win_start)]
        else:
            render_df = map_df

        # Heatmap / Line Layers
        layers = []
        if view_mode == "Midpoint Heatmap (Es-Cloud)":
            map_ready = render_df[['Mid_Lat', 'Mid_Lon']].dropna()
            layers.append(pdk.Layer('HeatmapLayer', data=map_ready, get_position='[Mid_Lon, Mid_Lat]', radius_pixels=60, intensity=1.5, threshold=0.03))
        else:
            map_ready = render_df[['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']].dropna()
            layers.append(pdk.Layer('LineLayer', data=map_ready, get_source_position='[DX_Lon, DX_Lat]', get_target_position='[ST_Lon, ST_Lat]', get_width=1, get_color=[211, 47, 47, 45]))

        st.pydeck_chart(pdk.Deck(
            map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
            initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=3.8, pitch=0),
            layers=layers
        ))
        if st.session_state.is_playing: st.markdown(f"### 🕒 {current_time}")
