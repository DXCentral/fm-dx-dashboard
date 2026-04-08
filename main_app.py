import streamlit as st
import pandas as pd
import pydeck as pdk
import time
import datetime
from google.cloud import bigquery
from google.oauth2 import service_account 

# 1. THEME & UI STYLING
st.set_page_config(layout="wide", page_title="SEDAP Control Center")

if 'full_screen' not in st.session_state: st.session_state.full_screen = False
if 'p_idx' not in st.session_state: st.session_state.p_idx = 0
if 'playing' not in st.session_state: st.session_state.playing = False
if 'reset_count' not in st.session_state: st.session_state.reset_count = 0

if st.session_state.full_screen:
    st.markdown("""
        <style>
        [data-testid="stSidebar"], [data-testid="stHeader"], .st-emotion-cache-zq5m06, .st-emotion-cache-18ni7ap { display: none !important; }
        .stMain { padding: 0 !important; }
        .watermark { bottom: 120px !important; } 
        </style>
        """, unsafe_allow_html=True)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@200;300;400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Oswald', sans-serif !important; background-color: #000000; color: #FFFFFF; font-weight: 300; }
    div.stButton > button {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        border: 1px solid #444444 !important;
        border-radius: 25px !important;
        padding: 8px 25px !important;
        text-transform: uppercase;
        font-family: 'Oswald', sans-serif !important;
        letter-spacing: 1px;
        box-shadow: none !important;
        outline: none !important;
    }
    div.stButton > button:hover { border-color: #D32F2F !important; color: #D32F2F !important; }
    div[data-testid="stPills"] button[aria-checked="true"] { border: 2px solid #D32F2F !important; background-color: #000000 !important; color: #FFFFFF !important; }
    div[data-testid="stPills"] button { background-color: #000000 !important; border: 1px solid #444444 !important; border-radius: 25px !important; color: #888888 !important; }
    h1, h2, h3, h4 { color: #D32F2F !important; text-transform: uppercase; letter-spacing: 3px; }
    [data-testid="stSidebar"] { background-color: #0A0A0A; border-right: 1px solid #1A1A1A; }
    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; font-weight: 200; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; }
    .reset-box { display: flex; justify-content: center; width: 100%; margin-top: 15px; }
    .watermark { position: absolute; bottom: 80px; right: 40px; z-index: 1000; pointer-events: none; }
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
        
        l_dx = [c for c in df_logs.columns if 'Concatenated' in c and 'DX' in c][0]
        l_st = [c for c in df_logs.columns if 'Concatenated' in c and 'Station' in c][0]
        c_dx = [c for c in df_coords.columns if 'Concatenated' in c and 'DX' in c][0]
        c_st = [c for c in df_coords.columns if 'Concatenated' in c and 'Station' in c][0]

        df_coords = df_coords.drop_duplicates(subset=[c_dx, c_st])
        df = df_logs.merge(df_coords, left_on=[l_dx, l_st], right_on=[c_dx, c_st], how='left')
        
        dx_lat = [c for c in df.columns if 'DXer_Latitude' in c or ('DX' in c and 'Lat' in c)][0]
        dx_lon = [c for c in df.columns if 'DXer_Longitude' in c or ('DX' in c and 'Lon' in c)][0]
        st_lat = [c for c in df.columns if 'Station_Lat' in c or ('ST' in c and 'Lat' in c)][0]
        st_lon = [c for c in df.columns if 'Station_Long' in c or ('ST' in c and 'Lon' in c)][0]
        
        # Scrub Coordinates to prevent TypeErrors
        for c in [dx_lat, dx_lon, st_lat, st_lon]:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace('°', '').str.strip(), errors='coerce').astype('float32')
            
        df['Mid_Lat'] = (df[dx_lat] + df[st_lat]) / 2
        df['Mid_Lon'] = (df[dx_lon] + df[st_lon]) / 2
        df['Date_Obj'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Time_Str'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
        
        dist_col = [c for c in df.columns if 'Distance' in c and 'mi' in c][0]
        return df, df['Date_Obj'].max(), dist_col, dx_lat, dx_lon, st_lat, st_lon
    except Exception as e:
        st.error(f"System Link Failure: {e}")
        return pd.DataFrame(), "Error", "Distance", None, None, None, None

df, last_log_date, d_col, dx_lat, dx_lon, st_lat, st_lon = load_data()
if df.empty: st.stop()

# 3. SIDEBAR NAVIGATION
from streamlit_option_menu import option_menu
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(
        menu_title="DATA MODULES", 
        options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC ANALYSIS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"], 
        icons=["house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], 
        default_index=1
    )

# 4. GLOBAL FILTERS
if not st.session_state.full_screen:
    try:
        st.image("SEDAP Banner.png", width=600)
    except:
        st.markdown("<h1 style='color: #D32F2F;'>SEDAP</h1>", unsafe_allow_html=True)
        
    rk = f"v{st.session_state.reset_count}"
    
    with st.expander(label="GLOBAL FILTERS", expanded=True):
        r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
        f_freq = r1c1.selectbox("Frequency", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key=f"freq_{rk}")
        f_dxer = r1c2.selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().astype(str).tolist()), key=f"dxer_{rk}")
        f_station = r1c3.selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().astype(str).tolist()), key=f"stat_{rk}")
        f_state = r1c4.selectbox("State", ["All"] + sorted(df['State'].dropna().unique().astype(str).tolist()), key=f"stte_{rk}")
        f_country = r1c5.selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().astype(str).tolist()), key=f"ctry_{rk}")
        
        r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
        f_dxco = r2c1.selectbox("DXer Country", ["All"] + sorted(df['DXer_Country'].dropna().unique().astype(str).tolist()), key=f"dxco_{rk}")
        f_dxst = r2c2.selectbox("DXer State", ["All"] + sorted(df['DXer_State_Prov'].dropna().unique().astype(str).tolist()), key=f"dxst_{rk}")
        f_month = r2c3.selectbox("Local Month", ["All"] + sorted(df['Local_Month'].dropna().unique().astype(str).tolist()), key=f"moth_{rk}")
        f_year = r2c4.selectbox("Local Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key=f"year_{rk}")
        f_day = r2c5.selectbox("Month Day", ["All"] + sorted(df['Month_Day'].dropna().unique().astype(str).tolist()), key=f"day_{rk}")
        
        r3c1, r3c2, r3c3 = st.columns(3)
        f_dist = r3c1.selectbox("Distance Distribution", ["All"] + sorted(df['Distance_Distribution'].dropna().unique().astype(str).tolist()), key=f"dist_{rk}")
        f_reg = r3c2.selectbox("DXer Region", ["All"] + sorted(df['DXer_Region'].dropna().unique().astype(str).tolist()), key=f"regn_{rk}")
        rds_col = 'RDS Decode?' if 'RDS Decode?' in df.columns else 'RDS Decode'
        f_rds = r3c3.selectbox("RDS Decode?", ["All"] + (sorted(df[rds_col].dropna().unique().astype(str).tolist()) if rds_col in df.columns else []), key=f"rds_{rk}")
        
        st.markdown('<div class="reset-box">', unsafe_allow_html=True)
        if st.button("RESET ALL FILTERS", key="global_reset"):
            st.session_state.reset_count += 1
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
else:
    f_freq, f_dxer, f_station, f_state, f_country, f_dxco, f_dxst, f_month, f_year, f_day, f_dist, f_reg, f_rds = ["All"] * 13

# 🚀 DATA FILTER ENGINE
filt_df = df.copy()
f_map = {
    'Frequency': f_freq, 'DXer': f_dxer, 'Station': f_station, 'State': f_state, 'Country': f_country,
    'DXer_Country': f_dxco, 'DXer_State_Prov': f_dxst, 'Local_Month': f_month, 'Local_Year': f_year,
    'Month_Day': f_day, 'Distance_Distribution': f_dist, 'DXer_Region': f_reg, rds_col: f_rds
}
for col, val in f_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# 5. PAGE LOGIC
if selected_page == "ES-CLOUD TRACKER":
    if not st.session_state.full_screen:
        st.header("Ionospheric Propagation Analysis")
        view_mode = st.pills("MAP LAYER SELECTION", ["Es Cloud Location Heatmap", "Path Line Analysis"], default="Es Cloud Location Heatmap")
        st.session_state.last_mode = view_mode
    else: view_mode = st.session_state.get('last_mode', "Es Cloud Location Heatmap")

    hc1, hc2 = st.columns([1, 2])
    with hc1:
        range_on = st.checkbox("Enable Date Range Mode", value=True) 
        avail_days = sorted(filt_df['Date_Obj'].unique()) 
        if not range_on:
            date_sel = st.date_input("Select Event Date", value=avail_days[-1])
            map_df = filt_df[filt_df['Date_Obj'] == date_sel]
        else:
            date_range = st.date_input("Select Date Range", value=(avail_days[0], avail_days[-1]))
            map_df = filt_df[(filt_df['Date_Obj'] >= date_range[0]) & (filt_df['Date_Obj'] <= date_range[1])] if len(date_range) == 2 else filt_df[filt_df['Date_Obj'] == date_range[0]]
        
        speed_sets = {"1x": {"delay": 0.2, "step": 1}, "2x": {"delay": 0.1, "step": 2}, "4x": {"delay": 0.01, "step": 4}}
        play_speed = st.selectbox("Playback Speed", options=list(speed_sets.keys()), index=1)
        if st.button("📺 VIEW FULL SCREEN" if not st.session_state.full_screen else "❌ EXIT FULL SCREEN"):
            st.session_state.full_screen = not st.session_state.full_screen; st.rerun()

    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        pb1, pb2, pb_txt = st.columns([1, 1, 3])
        if pb1.button("▶ PLAY"): st.session_state.playing = True; st.session_state.p_idx = 0; st.rerun()
        if pb2.button("⏹ STOP"): st.session_state.playing = False; st.rerun()
        
        current_time = times[st.session_state.p_idx] if st.session_state.playing else "SHOW ALL"
        if not st.session_state.playing:
            current_time = hc2.select_slider("Time Control", options=["SHOW ALL"] + times, value="SHOW ALL")
        pb_txt.write(f"## 🕒 CURRENT TIME: {current_time}")

        render_df = map_df[(map_df['Time_Str'] <= current_time) & (map_df['Time_Str'] >= (datetime.datetime.strptime(current_time, '%H:%M') - datetime.timedelta(minutes=60)).strftime('%H:%M'))] if current_time != "SHOW ALL" else map_df
        map_clean = render_df.dropna(subset=['Mid_Lat', 'Mid_Lon', dx_lat, dx_lon, st_lat, st_lon])

        layers = []
        if view_mode == "Es Cloud Location Heatmap":
            layers.append(pdk.Layer('HeatmapLayer', data=map_clean, get_position='[Mid_Lon, Mid_Lat]', radius_pixels=65, intensity=2.0, threshold=0.03,
                                   color_range=[[183, 28, 28, 60], [211, 47, 47, 150], [244, 67, 54, 200], [255, 235, 238, 230], [255, 255, 255, 255]]))
        else:
            layers.append(pdk.Layer('LineLayer', data=map_clean, get_source_position=f'[{dx_lon}, {dx_lat}]', get_target_position=f'[{st_lon}, {st_lat}]', get_width=1, get_color=[211, 47, 47, 45]))

        st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=32, longitude=-95, zoom=3.4), layers=layers, height=1000))
        st.markdown("""<div class="watermark"><img src="https://raw.githubusercontent.com/dxcentral/fm-dx-dashboard/main/SEDAP%20Banner.png" style="width: 250px; opacity: 0.4;"></div>""", unsafe_allow_html=True)
        
        if st.session_state.playing:
            conf = speed_sets[play_speed]
            if st.session_state.p_idx + conf['step'] < len(times):
                st.session_state.p_idx += conf['step']; time.sleep(conf['delay']); st.rerun()
            else: st.session_state.playing = False; st.rerun()

elif selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Total Logs", f"{len(filt_df):,}")
    m2.metric("Unique Stations", f"{filt_df['Station'].nunique():,}")
    m3.metric("US States", filt_df[filt_df['Country'] == 'USA']['State'].nunique())
    m4.metric("CA Provinces", filt_df[filt_df['Country'] == 'Canada']['State'].nunique())
    m5.metric("MX States", filt_df[filt_df['Country'] == 'Mexico']['State'].nunique())
    m6.metric("Total Countries", filt_df['Country'].nunique())
    m7.metric("Max Distance", f"{filt_df[d_col].max() if not filt_df.empty else 0:,.0f} mi")
    st.dataframe(filt_df.head(100), width=1500, hide_index=True)

elif selected_page == "GEOGRAPHIC ANALYSIS":
    st.header("Geographic Analysis Suite")
    
    geo_sections = ["Country Stats", "Canadian Stats", "Mexican Stats", "US States", "Distance Stats"]
    geo_view = st.pills("SELECT ANALYSIS VIEW", geo_sections, default="US States")
    
    st.markdown("---")
    
    if geo_view == "Country Stats":
        st.subheader("🌎 International Insights (Excl. NA Big Three)")
        st.info("Visuals coming soon: International log density and country leaderboards.")
        
    elif geo_view == "Canadian Stats":
        st.subheader("🍁 Canada Propagation Profile")
        st.info("Visuals coming soon: Province density maps and leaderboard.")
        
    elif geo_view == "Mexican Stats":
        st.subheader("🇲🇽 Mexico Propagation Profile")
        st.info("Visuals coming soon: Mexico state density and reception patterns.")
        
    elif geo_view == "US States":
        st.subheader("🇺🇸 US Domestic Reception Analysis")
        st.info("Visuals coming soon: State-by-state density heatmap and leaderboards.")
        
    elif geo_view == "Distance Stats":
        st.subheader("📏 Propagation Distance Metrics")
        st.info("Visuals coming soon: Sweet-spot histograms and distance distribution.")
