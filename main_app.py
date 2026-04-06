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
        
        # PREVENT DUPLICATION
        df_coords = df_coords.drop_duplicates(subset=['DXer_Concatenated_Location', 'Station_Concatenated_Location'])
        
        df = df_logs.merge(df_coords, left_on=['Concatenated_DXer_Location', 'Concatenated_Station_Location'], 
                           right_on=['DXer_Concatenated_Location', 'Station_Concatenated_Location'], how='left')
        
        # Standardize Coordinates
        df['DX_Lat'] = pd.to_numeric(df['DXer_Latitude'], errors='coerce').astype('float32')
        df['DX_Lon'] = pd.to_numeric(df['DXer_Longitude'], errors='coerce').astype('float32')
        df['ST_Lat'] = pd.to_numeric(df['Station_Lat'], errors='coerce').astype('float32')
        df['ST_Lon'] = pd.to_numeric(df['Station_Long'], errors='coerce').astype('float32')
        df['Mid_Lat'] = (df['DX_Lat'] + df['ST_Lat']) / 2
        df['Mid_Lon'] = (df['DX_Lon'] + df['ST_Lon']) / 2
        
        df['Date_Obj'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Time_Str'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
        
        dist_col = [c for c in df.columns if 'Distance' in c and 'mi' in c][0]
        return df, df['Date_Obj'].max(), dist_col
    except Exception as e:
        st.error(f"System Link Failure: {e}")
        return pd.DataFrame(), "Error", "Distance"

df, last_log_date, d_col = load_data()
if df.empty: st.stop()

# 3. SIDEBAR NAVIGATION
from streamlit_option_menu import option_menu
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(menu_title="DATA MODULES", options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC RADIUS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"], icons=["house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], default_index=0)

# 4. ES-CLOUD TRACKER
if selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    view_mode = st.radio("SELECT MAP LAYER", ["Midpoint Heatmap (Es-Cloud)", "Path Line Analysis (Signal Grid)"], horizontal=True)
    
    hc1, hc2 = st.columns([1, 2])
    
    # 4a. ADVANCED DATE SELECTOR
    with hc1:
        use_range = st.checkbox("Enable Date Range Mode", value=False)
        avail_dates = sorted(df['Date_Obj'].unique())
        
        if not use_range:
            date_sel = st.date_input("Select Event Date", value=avail_dates[-1])
            map_df = df[df['Date_Obj'] == date_sel]
        else:
            preset = st.selectbox("Presets", ["Custom Range", "Last 7 Days", "Peak June 2023"])
            if preset == "Last 7 Days":
                start_d, end_d = avail_dates[-7], avail_dates[-1]
            elif preset == "Peak June 2023":
                start_d, end_d = datetime.date(2023, 6, 1), datetime.date(2023, 6, 30)
            else:
                start_d, end_d = avail_dates[0], avail_dates[-1]
                
            date_range = st.date_input("Custom Range", value=(start_d, end_d))
            if isinstance(date_range, tuple) and len(date_range) == 2:
                map_df = df[(df['Date_Obj'] >= date_range[0]) & (df['Date_Obj'] <= date_range[1])]
            else:
                map_df = df[df['Date_Obj'] == date_range[0]]

    # 4b. TIMING & PLAYBACK
    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        if 'p_idx' not in st.session_state: st.session_state.p_idx = 0
        if 'playing' not in st.session_state: st.session_state.playing = False

        sel_time = hc2.select_slider("Timing Control", options=["SHOW ALL"] + times, 
                                     value=times[st.session_state.p_idx] if st.session_state.playing else "SHOW ALL")
        
        c1, c2, c3 = st.columns(3)
        if c1.button("▶ PLAY"):
            st.session_state.playing = True
            for i in range(st.session_state.p_idx, len(times)):
                st.session_state.p_idx = i
                time.sleep(0.12)
                st.rerun()
            st.session_state.playing = False
        if c2.button("⏹ STOP"):
            st.session_state.playing = False
            st.session_state.p_idx = 0
            st.rerun()
        c3.button("🎥 EXPORT MP4")

        # 4c. RENDERING (WITH SKIP-ERROR PROTECTION)
        current_time = times[st.session_state.p_idx] if st.session_state.playing else sel_time
        
        if current_time != "SHOW ALL":
            sel_dt = datetime.datetime.strptime(current_time, '%H:%M')
            win_start = (sel_dt - datetime.timedelta(minutes=60)).strftime('%H:%M')
            render_df = map_df[(map_df['Time_Str'] <= current_time) & (map_df['Time_Str'] >= win_start)]
        else:
            render_df = map_df

        layers = []
        try:
            if view_mode == "Midpoint Heatmap (Es-Cloud)":
                map_ready = render_df[['Mid_Lat', 'Mid_Lon']].dropna()
                layers.append(pdk.Layer('HeatmapLayer', data=map_ready, get_position='[Mid_Lon, Mid_Lat]', radius_pixels=65, intensity=2.2, threshold=0.03,
                                       color_range=[[183, 28, 28, 60], [211, 47, 47, 150], [244, 67, 54, 200], [255, 235, 238, 230], [255, 255, 255, 255]]))
            else:
                map_ready = render_df[['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']].dropna()
                layers.append(pdk.Layer('LineLayer', data=map_ready, get_source_position='[DX_Lon, DX_Lat]', get_target_position='[ST_Lon, ST_Lat]', get_width=1, get_color=[211, 47, 47, 45]))

            st.pydeck_chart(pdk.Deck(
                # SPECIAL URL: Carto Dark Matter WITH Labels/Borders enabled
                map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
                initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=3.8),
                layers=layers
            ))
        except:
            st.warning("Skipping frame with signal interference...")
            pass

# 5. DASHBOARD OVERVIEW (Restored Metrics)
elif selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    # ... (Restored 7-metric grid and dataframe here)
