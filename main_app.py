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

# 2. LEAN DATA LOADING (SQL JOIN)
@st.cache_data(ttl=2592000)
def load_data():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        client = bigquery.Client(credentials=credentials, project=credentials.project_id)
        
        # SQL JOIN: We do the work in the cloud, not in the app's RAM
        query = """
        SELECT 
            t1.Frequency, t1.Station, t1.DXer, t1.Local_Year, t1.Country,
            t1.Local_Date, t1.Local_Time, t1.`Distance (mi)`,
            t2.DXer_Latitude as DX_Lat, t2.DXer_Longitude as DX_Lon,
            t2.Station_Lat as ST_Lat, t2.Station_Long as ST_Lon
        FROM `sporadic-es-data-analysis.FMList_Data.fm_list_data_raw` AS t1
        LEFT JOIN `sporadic-es-data-analysis.FMList_Data.fm_list_coords` AS t2
        ON t1.Concatenated_DXer_Location = t2.DXer_Concatenated_Location
        AND t1.Concatenated_Station_Location = t2.Station_Concatenated_Location
        """
        df = client.query(query).to_dataframe()

        # Downcast numbers to save RAM
        for col in ['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('float32')

        df['Mid_Lat'] = (df['DX_Lat'] + df['ST_Lat']) / 2
        df['Mid_Lon'] = (df['DX_Lon'] + df['ST_Lon']) / 2
        df['Date_Obj'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Time_Str'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
        
        return df, df['Date_Obj'].max()
    except Exception as e:
        st.error(f"Memory Safety Error: {e}")
        return pd.DataFrame(), "Error"

df, last_log_date = load_data()

# 3. NAVIGATION (Simplified)
from streamlit_option_menu import option_menu
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(menu_title="DATA MODULES", options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER"], icons=["house-fill", "cloud-haze2"], default_index=0)

# 4. SHARED FILTERS
filt_df = df.copy()

# 5. ES-CLOUD TRACKER
if selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    view_mode = st.radio("SELECT MAP LAYER", ["Midpoint Heatmap", "Path Line Analysis"], horizontal=True)
    
    hc1, hc2 = st.columns([1, 2])
    avail_dates = sorted(filt_df['Date_Obj'].unique())
    date_sel = hc1.date_input("Event Date Range", value=(avail_dates[-1], avail_dates[-1])) # Default to latest date for speed
    
    # Filter by Date
    if isinstance(date_sel, tuple) and len(date_sel) == 2:
        map_df = filt_df[(filt_df['Date_Obj'] >= date_sel[0]) & (filt_df['Date_Obj'] <= date_sel[1])]
    else:
        map_df = filt_df[filt_df['Date_Obj'] == date_sel]

    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        
        # Persistent playback index
        if 'p_idx' not in st.session_state: st.session_state.p_idx = 0
        if 'is_playing' not in st.session_state: st.session_state.is_playing = False

        selected_time = hc2.select_slider("Timing Control", options=["SHOW ALL"] + times, 
                                          value=times[st.session_state.p_idx] if st.session_state.is_playing else "SHOW ALL")
        
        c1, c2 = st.columns(2)
        if c1.button("▶ PLAY TIMELAPSE"):
            st.session_state.is_playing = True
            for i in range(st.session_state.p_idx, len(times)):
                st.session_state.p_idx = i
                time.sleep(0.1) 
                st.rerun()
            st.session_state.is_playing = False

        if c2.button("⏹ STOP"):
            st.session_state.is_playing = False
            st.session_state.p_idx = 0
            st.rerun()

        # Render Slice
        current_time = times[st.session_state.p_idx] if st.session_state.is_playing else selected_time
        
        if current_time != "SHOW ALL":
            sel_dt = datetime.datetime.strptime(current_time, '%H:%M')
            win_start = (sel_dt - datetime.timedelta(minutes=60)).strftime('%H:%M')
            # Extract ONLY the coordinates to keep RAM usage low during render
            render_df = map_df[(map_df['Time_Str'] <= current_time) & (map_df['Time_Str'] >= win_start)][['Mid_Lat', 'Mid_Lon', 'DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']]
        else:
            render_df = map_df[['Mid_Lat', 'Mid_Lon', 'DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']]

        layers = []
        if view_mode == "Midpoint Heatmap":
            layers.append(pdk.Layer('HeatmapLayer', data=render_df[['Mid_Lat', 'Mid_Lon']].dropna(), get_position='[Mid_Lon, Mid_Lat]', radius_pixels=60, intensity=1.5, threshold=0.03))
        else:
            layers.append(pdk.Layer('LineLayer', data=render_df[['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']].dropna(), get_source_position='[DX_Lon, DX_Lat]', get_target_position='[ST_Lon, ST_Lat]', get_width=1, get_color=[211, 47, 47, 45]))

        st.pydeck_chart(pdk.Deck(
            map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
            initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=3.8),
            layers=layers
        ))
        if st.session_state.is_playing: st.markdown(f"### 🕒 {current_time}")
