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
    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; font-weight: 200; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; }
    div.stButton > button { background-color: #D32F2F !important; color: white !important; border-radius: 4px !important; border: none !important; padding: 8px 25px !important; text-transform: uppercase; width: 100%; }
    
    /* Watermark Opacity Styling */
    .watermark {
        position: absolute;
        bottom: 40px;
        right: 30px;
        opacity: 0.4;
        z-index: 1000;
        pointer-events: none;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING (Deduplicated to 74k)
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
        
        df_coords = df_coords.drop_duplicates(subset=['DXer_Concatenated_Location', 'Station_Concatenated_Location'])
        df = df_logs.merge(df_coords, left_on=['Concatenated_DXer_Location', 'Concatenated_Station_Location'], 
                           right_on=['DXer_Concatenated_Location', 'Station_Concatenated_Location'], how='left')
        
        df['DX_Lat'] = pd.to_numeric(df['DXer_Latitude'], errors='coerce').astype('float32')
        df['DX_Lon'] = pd.to_numeric(df['DXer_Longitude'], errors='coerce').astype('float32')
        df['ST_Lat'] = pd.to_numeric(df['Station_Lat'], errors='coerce').astype('float32')
        df['ST_Lon'] = pd.to_numeric(df['Station_Long'], errors='coerce').astype('float32')
        df['Mid_Lat'] = (df['DX_Lat'] + df['ST_Lat']) / 2
        df['Mid_Lon'] = (df['DX_Lon'] + df['ST_Lon']) / 2
        df['Date_Obj'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Time_Str'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
        
        d_col = [c for c in df.columns if 'Distance' in c and 'mi' in c][0]
        return df, df['Date_Obj'].max(), d_col
    except Exception as e:
        st.error(f"Link Failure: {e}")
        return pd.DataFrame(), "Error", "Distance"

df, last_log_date, dist_col = load_data()

# 3. SIDEBAR NAVIGATION
from streamlit_option_menu import option_menu
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(menu_title="DATA MODULES", options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC RADIUS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"], icons=["house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], default_index=1)

# 4. SHARED FILTERS (13 RESTORED)
st.image("SEDAP Banner.png", width=600)
with st.expander(label="GLOBAL FILTERS", expanded=True):
    r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
    f_freq = r1c1.selectbox("Frequency", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key="filt_freq")
    f_dxer = r1c2.selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().astype(str).tolist()), key="filt_dxer")
    f_station = r1c3.selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().astype(str).tolist()), key="filt_station")
    f_state = r1c4.selectbox("State", ["All"] + sorted(df['State'].dropna().unique().astype(str).tolist()), key="filt_state")
    f_country = r1c5.selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().astype(str).tolist()), key="filt_country")

    r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
    f_dx_co = r2c1.selectbox("DXer Country", ["All"] + sorted(df['DXer_Country'].dropna().unique().astype(str).tolist()), key="filt_dxco")
    f_dx_st = r2c2.selectbox("DXer State", ["All"] + sorted(df['DXer_State_Prov'].dropna().unique().astype(str).tolist()), key="filt_dxst")
    f_month = r2c3.selectbox("Local Month", ["All"] + sorted(df['Local_Month'].dropna().unique().astype(str).tolist()), key="filt_month")
    f_year = r2c4.selectbox("Local Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key="filt_year")
    f_day = r2c5.selectbox("Month Day", ["All"] + sorted(df['Month_Day'].dropna().unique().astype(str).tolist()), key="filt_day")

    r3c1, r3c2, r3c3 = st.columns(3)
    f_dist = r3c1.selectbox("Distance Distribution", ["All"] + sorted(df['Distance_Distribution'].dropna().unique().astype(str).tolist()), key="filt_dist")
    f_reg = r3c2.selectbox("DXer Region", ["All"] + sorted(df['DXer_Region'].dropna().unique().astype(str).tolist()), key="filt_reg")
    f_rds = r3c3.selectbox("RDS Decode?", ["All"] + (sorted(df['RDS Decode?'].dropna().unique().astype(str).tolist()) if 'RDS Decode?' in df.columns else []), key="filt_rds")

filt_df = df.copy()
if f_freq != "All": filt_df = filt_df[filt_df['Frequency'].astype(str) == f_freq]
if f_dxer != "All": filt_df = filt_df[filt_df['DXer'].astype(str) == f_dxer]
if f_station != "All": filt_df = filt_df[filt_df['Station'].astype(str) == f_station]
if f_state != "All": filt_df = filt_df[filt_df['State'].astype(str) == f_state]
if f_country != "All": filt_df = filt_df[filt_df['Country'].astype(str) == f_country]

# 5. DASHBOARD
if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Total Logs", f"{len(filt_df):,}")
    m2.metric("Unique Stations", f"{filt_df['Station'].nunique():,}")
    m3.metric("US States", filt_df[filt_df['Country'] == 'USA']['State'].nunique())
    m4.metric("CA Provinces", filt_df[filt_df['Country'] == 'Canada']['State'].nunique())
    m5.metric("MX States", filt_df[filt_df['Country'] == 'Mexico']['State'].nunique())
    m6.metric("Total Countries", filt_df['Country'].nunique())
    m7.metric("Max Distance", f"{filt_df[dist_col].max() if not filt_df.empty else 0:,.0f} mi")
    st.dataframe(filt_df.head(100), width='stretch', hide_index=True)

# 6. ES-CLOUD TRACKER
elif selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    view_mode = st.radio("SELECT MAP LAYER", ["Midpoint Heatmap (Es-Cloud)", "Path Line Analysis (Signal Grid)"], horizontal=True)
    
    hc1, hc2 = st.columns([1, 2])
    with hc1:
        range_mode = st.toggle("Enable Date Range Mode", value=False)
        avail_days = sorted(filt_df['Date_Obj'].unique())
        if not range_mode:
            date_sel = st.date_input("Select Event Date", value=avail_days[-1])
            map_df = filt_df[filt_df['Date_Obj'] == date_sel]
        else:
            date_range = st.date_input("Select Date Range", value=(avail_days[0], avail_days[-1]))
            if isinstance(date_range, tuple) and len(date_range) == 2:
                map_df = filt_df[(filt_df['Date_Obj'] >= date_range[0]) & (filt_df['Date_Obj'] <= date_range[1])]
            else: map_df = filt_df[filt_df['Date_Obj'] == date_range[0]]

    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        speed_map = {"1x": 0.3, "1.5x": 0.2, "2x": 0.1, "3x": 0.05, "4x": 0.01}
        play_speed = hc1.selectbox("Playback Speed", options=list(speed_map.keys()), index=1)
        
        if 'p_idx' not in st.session_state: st.session_state.p_idx = 0
        if 'playing' not in st.session_state: st.session_state.playing = False

        sel_time = hc2.select_slider("Timing Control", options=["SHOW ALL"] + times, 
                                     value=times[st.session_state.p_idx] if st.session_state.playing else "SHOW ALL")
        
        c1, c2, c3 = st.columns(3)
        if c1.button("▶ PLAY"):
            st.session_state.playing = True
            st.session_state.p_idx = 0
            st.rerun()
        if c2.button("⏹ STOP"):
            st.session_state.playing = False
            st.rerun()
        c3.button("🎥 EXPORT MP4")

        # RENDER CALCULATION
        current_time = times[st.session_state.p_idx] if st.session_state.playing else sel_time
        
        if current_time != "SHOW ALL":
            t_obj = datetime.datetime.strptime(current_time, '%H:%M')
            t_start = (t_obj - datetime.timedelta(minutes=60)).strftime('%H:%M')
            render_df = map_df[(map_df['Time_Str'] <= current_time) & (map_df['Time_Str'] >= t_start)]
        else:
            render_df = map_df

        # LAYERS
        layers = []
        if view_mode == "Midpoint Heatmap (Es-Cloud)":
            map_ready = render_df[['Mid_Lat', 'Mid_Lon']].dropna()
            layers.append(pdk.Layer('HeatmapLayer', data=map_ready, get_position='[Mid_Lon, Mid_Lat]', radius_pixels=65, intensity=2.0, threshold=0.03,
                                   color_range=[[183, 28, 28, 60], [211, 47, 47, 150], [244, 67, 54, 200], [255, 235, 238, 230], [255, 255, 255, 255]]))
        else:
            map_ready = render_df[['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']].dropna()
            layers.append(pdk.Layer('LineLayer', data=map_ready, get_source_position='[DX_Lon, DX_Lat]', get_target_position='[ST_Lon, ST_Lat]', get_width=1, get_color=[211, 47, 47, 45]))

        st.pydeck_chart(pdk.Deck(
            map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
            initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=4, pitch=0),
            layers=layers
        ))
        
        # WATERMARK OVERLAY
        st.markdown("""
            <div class="watermark">
                <img src="https://raw.githubusercontent.com/dxcentral/fm-dx-dashboard/main/SEDAP%20Banner.png" width="180">
            </div>
            """, unsafe_allow_html=True)
        
        if st.session_state.playing:
            st.markdown(f"### 🕒 TIMESTAMP: {current_time}")
            # AUTO-ADVANCE (AFTER CHART)
            if st.session_state.p_idx < len(times) - 1:
                st.session_state.p_idx += 1
                time.sleep(speed_map[play_speed])
                st.rerun()
            else:
                st.session_state.playing = False
                st.rerun()
