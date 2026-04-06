import streamlit as st
import pandas as pd
import pydeck as pdk
import time
import datetime
from google.cloud import bigquery
from google.oauth2 import service_account 

# 1. THEME & UI STYLING
st.set_page_config(layout="wide", page_title="SEDAP Control Center")

# Session State Persistence
if 'broadcast_mode' not in st.session_state: st.session_state.broadcast_mode = False
if 'p_idx' not in st.session_state: st.session_state.p_idx = 0
if 'playing' not in st.session_state: st.session_state.playing = False

# Broadcast Mode CSS
if st.session_state.broadcast_mode:
    st.markdown("""
        <style>
        [data-testid="stSidebar"], [data-testid="stHeader"], .st-emotion-cache-zq5m06 { display: none !important; }
        .stMain { padding: 0 !important; }
        .watermark { bottom: 120px !important; } 
        </style>
        """, unsafe_allow_html=True)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@200;300;400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Oswald', sans-serif !important; background-color: #000000; color: #FFFFFF; font-weight: 300; }
    h1, h2, h3, h4 { color: #D32F2F !important; font-family: 'Oswald', sans-serif !important; text-transform: uppercase; letter-spacing: 3px; }
    [data-testid="stSidebar"] { background-color: #0A0A0A; border-right: 1px solid #1A1A1A; min-width: 320px !important; }
    
    /* Clean Rounded Red Buttons */
    div.stButton > button { 
        background-color: #D32F2F !important; 
        color: white !important; 
        border-radius: 25px !important; 
        border: 1px solid #D32F2F !important; 
        padding: 10px 25px !important; 
        text-transform: uppercase; 
        width: 100%; 
        transition: 0.3s;
        box-shadow: none !important;
        outline: none !important;
    }
    div.stButton > button:hover { background-color: #FF5252 !important; border-color: #FF5252 !important; }
    
    /* Metric Styling */
    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; font-weight: 200; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; }
    
    .watermark { position: absolute; bottom: 60px; right: 40px; opacity: 0.4; z-index: 1000; pointer-events: none; }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING (Deduplicated)
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
        
        # Dynamic Column Detection
        log_dx_col = [c for c in df_logs.columns if 'Concatenated' in c and 'DX' in c][0]
        log_st_col = [c for c in df_logs.columns if 'Concatenated' in c and 'Station' in c][0]
        crd_dx_col = [c for c in df_coords.columns if 'Concatenated' in c and 'DX' in c][0]
        crd_st_col = [c for c in df_coords.columns if 'Concatenated' in c and 'Station' in c][0]

        df_coords = df_coords.drop_duplicates(subset=[crd_dx_col, crd_st_col])
        df = df_logs.merge(df_coords, left_on=[log_dx_col, log_st_col], right_on=[crd_dx_col, crd_st_col], how='left')
        
        # Coords
        dx_lat_col = [c for c in df.columns if 'DXer_Latitude' in c or ('DX' in c and 'Lat' in c)][0]
        dx_lon_col = [c for c in df.columns if 'DXer_Longitude' in c or ('DX' in c and 'Lon' in c)][0]
        st_lat_col = [c for c in df.columns if 'Station_Lat' in c or ('ST' in c and 'Lat' in c)][0]
        st_lon_col = [c for c in df.columns if 'Station_Long' in c or ('ST' in c and 'Lon' in c)][0]
        
        for c in [dx_lat_col, dx_lon_col, st_lat_col, st_lon_col]:
            df[c] = pd.to_numeric(df[c], errors='coerce').astype('float32')
            
        df['Mid_Lat'] = (df[dx_lat_col] + df[st_lat_col]) / 2
        df['Mid_Lon'] = (df[dx_lon_col] + df[st_lon_col]) / 2
        df['Date_Obj'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Time_Str'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
        
        dist_col = [c for c in df.columns if 'Distance' in c and 'mi' in c][0]
        return df, df['Date_Obj'].max(), dist_col, dx_lat_col, dx_lon_col, st_lat_col, st_lon_col
    except Exception as e:
        st.error(f"System Link Failure: {e}")
        return pd.DataFrame(), "Error", "Distance", None, None, None, None

df, last_log_date, dist_col_name, dx_lat, dx_lon, st_lat, st_lon = load_data()
if df.empty: st.stop()

# 3. SIDEBAR NAVIGATION
from streamlit_option_menu import option_menu
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(
        menu_title="DATA MODULES",
        options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC RADIUS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"],
        icons=["house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], 
        default_index=0
    )

# 4. GLOBAL FILTERS (ALL 13 RESTORED)
st.image("SEDAP Banner.png", width=600)
with st.expander(label="GLOBAL FILTERS", expanded=True):
    r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
    f_freq = r1c1.selectbox("Frequency", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key="filt_freq")
    f_dxer = r1c2.selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().astype(str).tolist()), key="filt_dxer")
    f_station = r1c3.selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().astype(str).tolist()), key="filt_station")
    f_state = r1c4.selectbox("State", ["All"] + sorted(df['State'].dropna().unique().astype(str).tolist()), key="filt_state")
    f_country = r1c5.selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().astype(str).tolist()), key="filt_country")

    r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
    f_dxco = r2c1.selectbox("DXer Country", ["All"] + sorted(df['DXer_Country'].dropna().unique().astype(str).tolist()), key="filt_dxco")
    f_dxst = r2c2.selectbox("DXer State", ["All"] + sorted(df['DXer_State_Prov'].dropna().unique().astype(str).tolist()), key="filt_dxst")
    f_month = r2c3.selectbox("Local Month", ["All"] + sorted(df['Local_Month'].dropna().unique().astype(str).tolist()), key="filt_month")
    f_year = r2c4.selectbox("Local Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key="filt_year")
    f_day = r2c5.selectbox("Month Day", ["All"] + sorted(df['Month_Day'].dropna().unique().astype(str).tolist()), key="filt_day")

    r3c1, r3c2, r3c3 = st.columns(3)
    f_dist = r3c1.selectbox("Distance Distribution", ["All"] + sorted(df['Distance_Distribution'].dropna().unique().astype(str).tolist()), key="filt_dist")
    f_reg = r3c2.selectbox("DXer Region", ["All"] + sorted(df['DXer_Region'].dropna().unique().astype(str).tolist()), key="filt_reg")
    f_rds = r3c3.selectbox("RDS Decode?", ["All"] + (sorted(df['RDS Decode?'].dropna().unique().astype(str).tolist()) if 'RDS Decode?' in df.columns else []), key="filt_rds")

filt_df = df.copy()
filter_map = {'Frequency': f_freq, 'DXer': f_dxer, 'Station': f_station, 'State': f_state, 'Country': f_country, 'DXer_Country': f_dxco, 'DXer_State_Prov': f_dxst, 'Local_Month': f_month, 'Local_Year': f_year, 'Month_Day': f_day, 'Distance_Distribution': f_dist, 'DXer_Region': f_reg}
for col, val in filter_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == val]

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
    m7.metric("Max Distance", f"{filt_df[dist_col_name].max() if not filt_df.empty else 0:,.0f} mi")
    st.dataframe(filt_df.head(100), width='stretch', hide_index=True)

# 6. ES-CLOUD TRACKER
elif selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    
    # NEW PILL SELECTOR (Looks like Buttons)
    view_mode = st.pills("MAP LAYER SELECTION", ["Midpoint Heatmap (Es-Cloud)", "Path Line Analysis (Signal Grid)"], default="Midpoint Heatmap (Es-Cloud)")
    
    hc1, hc2 = st.columns([1, 2])
    with hc1:
        # HYBRID DATE SELECTOR
        range_on = st.toggle("Enable Date Range Mode", value=False)
        avail_days = sorted(filt_df['Date_Obj'].unique())
        if not range_on:
            date_sel = st.date_input("Select Event Date", value=avail_days[-1])
            map_df = filt_df[filt_df['Date_Obj'] == date_sel]
        else:
            date_range = st.date_input("Select Date Range", value=(avail_days[0], avail_days[-1]))
            if isinstance(date_range, tuple) and len(date_range) == 2:
                map_df = filt_df[(filt_df['Date_Obj'] >= date_range[0]) & (filt_df['Date_Obj'] <= date_range[1])]
            else: map_df = filt_df[filt_df['Date_Obj'] == date_range[0]]
        
        speed_sets = {"1x": {"delay": 0.2, "step": 1}, "2x": {"delay": 0.1, "step": 2}, "4x": {"delay": 0.01, "step": 4}}
        play_speed = st.selectbox("Playback Speed", options=list(speed_sets.keys()), index=1)
        if st.button("📺 ENTER BROADCAST MODE"):
            st.session_state.broadcast_mode = True
            st.rerun()

    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        current_time = times[min(st.session_state.p_idx, len(times)-1)]
        
        # Draw Map
        t_obj = datetime.datetime.strptime(current_time, '%H:%M')
        t_start = (t_obj - datetime.timedelta(minutes=60)).strftime('%H:%M')
        render_df = map_df[(map_df['Time_Str'] <= current_time) & (map_df['Time_Str'] >= t_start)]

        layers = []
        if view_mode == "Midpoint Heatmap (Es-Cloud)":
            layers.append(pdk.Layer('HeatmapLayer', data=render_df[['Mid_Lat', 'Mid_Lon']].dropna(), get_position='[Mid_Lon, Mid_Lat]', radius_pixels=65, intensity=2.0, threshold=0.03,
                                   color_range=[[183, 28, 28, 60], [211, 47, 47, 150], [244, 67, 54, 200], [255, 235, 238, 230], [255, 255, 255, 255]]))
        else:
            layers.append(pdk.Layer('LineLayer', data=render_df[[dx_lat, dx_lon, st_lat, st_lon]].dropna(), get_source_position=f'[{dx_lon}, {dx_lat}]', get_target_position=f'[{st_lon}, {st_lat}]', get_width=1, get_color=[211, 47, 47, 45]))

        st.pydeck_chart(pdk.Deck(
            map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
            initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=4.5 if st.session_state.broadcast_mode else 4),
            layers=layers
        ))

        # Controls
        bc1, bc2, bc3, bc4 = st.columns([1,1,1,1])
        if st.session_state.broadcast_mode:
            if bc1.button("▶ START"): st.session_state.playing = True; st.rerun()
            if bc2.button("⏹ STOP"): st.session_state.playing = False; st.rerun()
            bc3.write(f"## 🕒 {current_time}")
            if bc4.button("❌ EXIT"): st.session_state.broadcast_mode = False; st.rerun()
        else:
            sel_time = hc2.select_slider("Time Control", options=times, value=current_time)
            if not st.session_state.playing: st.session_state.p_idx = times.index(sel_time)

        # 40% Opacity Watermark
        st.markdown("""<div class="watermark"><img src="https://raw.githubusercontent.com/dxcentral/fm-dx-dashboard/main/SEDAP%20Banner.png" width="220"></div>""", unsafe_allow_html=True)
        
        if st.session_state.playing:
            conf = speed_sets[play_speed]
            if st.session_state.p_idx + conf['step'] < len(times):
                st.session_state.p_idx += conf['step']
                time.sleep(conf['delay'])
                st.rerun()
            else:
                st.session_state.playing = False; st.rerun()
