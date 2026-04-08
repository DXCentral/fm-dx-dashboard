import streamlit as st
import pandas as pd
import pydeck as pdk
import time
import datetime
import plotly.express as px
from google.cloud import bigquery
from google.oauth2 import service_account 

# --- 1. THEME & UI STYLING (RESTORED V2.1) ---
st.set_page_config(layout="wide", page_title="SEDAP Control Center")

# Session State Initialization
if 'full_screen' not in st.session_state: st.session_state.full_screen = False
if 'p_idx' not in st.session_state: st.session_state.p_idx = 0
if 'playing' not in st.session_state: st.session_state.playing = False
if 'reset_count' not in st.session_state: st.session_state.reset_count = 0

# Full Screen CSS Logic
if st.session_state.full_screen:
    st.markdown("""
        <style>
        [data-testid="stSidebar"], [data-testid="stHeader"], .st-emotion-cache-zq5m06, .st-emotion-cache-18ni7ap { display: none !important; }
        .stMain { padding: 0 !important; }
        </style>
        """, unsafe_allow_html=True)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@200;300;400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Oswald', sans-serif !important; background-color: #000000; color: #FFFFFF; font-weight: 300; }
    div.stButton > button {
        background-color: #000000 !important; color: #FFFFFF !important;
        border: 1px solid #444444 !important; border-radius: 25px !important;
        padding: 8px 25px !important; text-transform: uppercase;
        font-family: 'Oswald', sans-serif !important; letter-spacing: 1px;
    }
    div.stButton > button:hover { border-color: #D32F2F !important; color: #D32F2F !important; }
    div[data-testid="stPills"] button[aria-checked="true"] { border: 2px solid #D32F2F !important; background-color: #000000 !important; color: #FFFFFF !important; }
    div[data-testid="stPills"] button { background-color: #000000 !important; border: 1px solid #444444 !important; border-radius: 25px !important; color: #888888 !important; }
    h1, h2, h3, h4 { color: #D32F2F !important; text-transform: uppercase; letter-spacing: 3px; }
    [data-testid="stSidebar"] { background-color: #0A0A0A; border-right: 1px solid #1A1A1A; }
    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; font-weight: 200; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA LOADING (FORBIDDEN FIX + V2.1 DYNAMIC JOIN) ---
@st.cache_data(ttl=600)
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
        
        # Coordinate Sanitizer (TYPE ERROR FIX)
        for c in [dx_lat, dx_lon, st_lat, st_lon]:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace('°', '').str.strip(), errors='coerce')
        
        df['Mid_Lat'] = (df[dx_lat] + df[st_lat]) / 2
        df['Mid_Lon'] = (df[dx_lon] + df[st_lon]) / 2
        df['Date_Obj'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Time_Str'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
        dist_col = [c for c in df.columns if 'Distance' in c and 'mi' in c][0]
        
        return df, dist_col, dx_lat, dx_lon, st_lat, st_lon
    except Exception as e:
        st.error(f"System Link Failure: {e}")
        return pd.DataFrame(), "Distance", None, None, None, None

df, d_col, dx_lat, dx_lon, st_lat, st_lon = load_data()

# --- 3. SIDEBAR NAVIGATION (RESTORED ALL OPTIONS) ---
from streamlit_option_menu import option_menu
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(menu_title="DATA MODULES", 
        options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC ANALYSIS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"], 
        icons=["house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], 
        default_index=1)

# --- 4. GLOBAL FILTERS (RESTORED 13 FILTERS) ---
if not st.session_state.full_screen:
    try: st.image("SEDAP Banner.png", width=600)
    except: st.markdown("<h1 style='color: #D32F2F;'>SEDAP CONTROL CENTER</h1>", unsafe_allow_html=True)
    rk = f"v{st.session_state.reset_count}"
    with st.expander(label="GLOBAL FILTERS", expanded=True):
        r1 = st.columns(5)
        f_freq = r1[0].selectbox("Freq", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key=f"f_{rk}")
        f_dxer = r1[1].selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().astype(str).tolist()), key=f"d_{rk}")
        f_station = r1[2].selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().astype(str).tolist()), key=f"s_{rk}")
        f_state = r1[3].selectbox("State", ["All"] + sorted(df['State'].dropna().unique().astype(str).tolist()), key=f"t_{rk}")
        f_country = r1[4].selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().astype(str).tolist()), key=f"c_{rk}")
        r2 = st.columns(5)
        f_dxco = r2[0].selectbox("DXer Country", ["All"] + sorted(df['DXer_Country'].dropna().unique().astype(str).tolist()), key=f"dc_{rk}")
        f_dxst = r2[1].selectbox("DXer State", ["All"] + sorted(df['DXer_State_Prov'].dropna().unique().astype(str).tolist()), key=f"ds_{rk}")
        f_month = r2[2].selectbox("Month", ["All"] + sorted(df['Local_Month'].dropna().unique().astype(str).tolist()), key=f"m_{rk}")
        f_year = r2[3].selectbox("Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key=f"y_{rk}")
        f_day = r2[4].selectbox("Day", ["All"] + sorted(df['Month_Day'].dropna().unique().astype(str).tolist()), key=f"dy_{rk}")
        r3 = st.columns(3)
        f_dist = r3[0].selectbox("Dist. Dist.", ["All"] + sorted(df['Distance_Distribution'].dropna().unique().astype(str).tolist()), key=f"dd_{rk}")
        f_reg = r3[1].selectbox("Region", ["All"] + sorted(df['DXer_Region'].dropna().unique().astype(str).tolist()), key=f"rg_{rk}")
        rds_col = 'RDS Decode?' if 'RDS Decode?' in df.columns else 'RDS Decode'
        f_rds = r3[2].selectbox("RDS?", ["All"] + (sorted(df[rds_col].dropna().unique().astype(str).tolist()) if rds_col in df.columns else []), key=f"rd_{rk}")
        if st.button("RESET FILTERS"): st.session_state.reset_count += 1; st.rerun()

filt_df = df.copy()
f_map = {'Frequency':f_freq, 'DXer':f_dxer, 'Station':f_station, 'State':f_state, 'Country':f_country, 'DXer_Country':f_dxco, 'DXer_State_Prov':f_dxst, 'Local_Month':f_month, 'Local_Year':f_year, 'Month_Day':f_day, 'Distance_Distribution':f_dist, 'DXer_Region':f_reg, rds_col:f_rds}
for col, val in f_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# --- 5. DASHBOARD OVERVIEW (RESTORED METRICS) ---
if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Total Logs", f"{len(filt_df):,}")
    m2.metric("Unique Stations", f"{filt_df['Station'].nunique():,}")
    m3.metric("US States", filt_df[filt_df['Country'] == 'USA']['State'].nunique())
    m4.metric("CA Provinces", filt_df[filt_df['Country'] == 'Canada']['State'].nunique())
    m5.metric("MX States", filt_df[filt_df['Country'] == 'Mexico']['State'].nunique())
    m6.metric("Countries", filt_df['Country'].nunique())
    m7.metric("Max Distance", f"{filt_df[d_col].max():,.0f} mi")
    st.dataframe(filt_df.head(100), use_container_width=True, hide_index=True)

# --- 6. ES-CLOUD TRACKER (RESTORED PLAYBACK & TOGGLES) ---
elif selected_page == "ES-CLOUD TRACKER":
    view_mode = st.pills("MAP LAYER", ["Es Cloud Location Heatmap", "Path Line Analysis"], default="Es Cloud Location Heatmap")
    hc1, hc2 = st.columns([1, 2])
    with hc1:
        range_on = st.checkbox("Enable Date Range Mode", value=True)
        avail_days = sorted(filt_df['Date_Obj'].unique())
        if range_on: date_range = st.date_input("Select Range", value=(avail_days[0], avail_days[-1]))
        else: date_sel = st.date_input("Select Date", value=avail_days[-1])
        
        map_df = filt_df[(filt_df['Date_Obj'] >= date_range[0]) & (filt_df['Date_Obj'] <= date_range[1])] if range_on and len(date_range) == 2 else filt_df[filt_df['Date_Obj'] == date_sel] if not range_on else filt_df
        speed_sets = {"1x": {"delay": 0.2, "step": 1}, "2x": {"delay": 0.1, "step": 2}, "4x": {"delay": 0.01, "step": 4}}
        play_speed = st.selectbox("Playback Speed", options=list(speed_sets.keys()), index=1)
        if st.button("📺 FULL SCREEN MODE"): st.session_state.full_screen = not st.session_state.full_screen; st.rerun()

    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        pb1, pb2, pb_txt = st.columns([1, 1, 3])
        if pb1.button("▶ PLAY"): st.session_state.playing = True; st.session_state.p_idx = 0; st.rerun()
        if pb2.button("⏹ STOP"): st.session_state.playing = False; st.rerun()
        current_time = times[st.session_state.p_idx] if st.session_state.playing else hc2.select_slider("Time", options=["SHOW ALL"] + times, value="SHOW ALL")
        pb_txt.write(f"## 🕒 CURRENT TIME: {current_time}")

        # TYPE ERROR SHIELD
        m_cl = map_df.dropna(subset=['Mid_Lat', 'Mid_Lon', dx_lat, dx_lon, st_lat, st_lon])
        render_df = m_cl if current_time == "SHOW ALL" else m_cl[m_cl['Time_Str'] == current_time]
        
        layers = []
        if view_mode == "Es Cloud Location Heatmap":
            layers.append(pdk.Layer('HeatmapLayer', data=render_df, get_position='[Mid_Lon, Mid_Lat]', radius_pixels=65, intensity=2.0, color_range=[[183, 28, 28, 60], [211, 47, 47, 150], [244, 67, 54, 200], [255, 235, 238, 230], [255, 255, 255, 255]]))
        else:
            layers.append(pdk.Layer('LineLayer', data=render_df, get_source_position=f'[{dx_lon}, {dx_lat}]', get_target_position=f'[{st_lon}, {st_lat}]', get_width=1, get_color=[211, 47, 47, 45]))
        st.pydeck_chart(pdk.Deck(map_style='mapbox://styles/mapbox/dark-v11', layers=layers, initial_view_state=pdk.ViewState(latitude=32, longitude=-95, zoom=3.4), height=1000))

        if st.session_state.playing:
            conf = speed_sets[play_speed]
            if st.session_state.p_idx + conf['step'] < len(times):
                st.session_state.p_idx += conf['step']; time.sleep(conf['delay']); st.rerun()
            else: st.session_state.playing = False; st.rerun()

# --- 7. GEOGRAPHIC ANALYSIS (REBUILT & PURIFIED) ---
elif selected_page == "GEOGRAPHIC ANALYSIS":
    st.header("Geographic Analysis Suite")
    tab1, tab2, tab3 = st.tabs(["🌎 Country Stats (Excl. USA)", "🍁 Canadian Stats", "🇺🇸 US State Stats"])
    
    with tab1: # Country Stats
        intl_df = filt_df[filt_df['Country'] != 'USA']
        st.subheader("International Logs")
        c_l = intl_df.groupby('Country').size().reset_index(name='Logs').sort_values('Logs', ascending=False)
        col1, col2 = st.columns([1, 2])
        col1.dataframe(c_l, column_config={"Logs": st.column_config.ProgressColumn("Logs", min_value=0, max_value=int(c_l['Logs'].max() if not c_l.empty else 1))}, hide_index=True)
        
        intl_m = intl_df.groupby(['Country', 'Local_Month_Name']).size().reset_index(name='Logs')
        fig = px.bar(intl_m, x="Local_Month_Name", y="Logs", color="Country", barmode="stack", color_discrete_sequence=px.colors.sequential.Reds_r)
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_family='Oswald', font_color='white', bargap=0.3)
        col2.plotly_chart(fig, use_container_width=True)

    with tab2: # Canadian Stats
        can_df = filt_df[filt_df['Country'] == 'Canada'].dropna(subset=[st_lat, st_lon])
        st.metric("Total Canadian Logs", f"{len(can_df):,}")
        p_l = can_df.groupby('State').size().reset_index(name='Logs').sort_values('Logs', ascending=False)
        c_can1, c_can2 = st.columns(2)
        c_can1.dataframe(p_l, column_config={"Logs": st.column_config.ProgressColumn("Logs", min_value=0, max_value=int(p_l['Logs'].max() if not p_l.empty else 1))}, hide_index=True)
        if not can_df.empty:
            c_can2.pydeck_chart(pdk.Deck(map_style='mapbox://styles/mapbox/dark-v11', initial_view_state=pdk.ViewState(latitude=55, longitude=-95, zoom=2.5),
                layers=[pdk.Layer('ScatterplotLayer', can_df, get_position=f'[{st_lon}, {st_lat}]', get_color='[211, 47, 47, 160]', get_radius=30000)]))

    with tab3: # US Stats
        us_df = filt_df[filt_df['Country'] == 'USA'].dropna(subset=[st_lat, st_lon])
        st.pydeck_chart(pdk.Deck(map_style='mapbox://styles/mapbox/dark-v11', initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=3.5),
            layers=[pdk.Layer('HeatmapLayer', us_df, get_position=f'[{st_lon}, {st_lat}]', radius_pixels=40)]))
        u_s = us_df.groupby('State').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(20)
        fig_u = px.bar(u_s, x='State', y='Logs', color_discrete_sequence=['#D32F2F'])
        fig_u.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_family='Oswald', font_color='white', bargap=0.4)
        st.plotly_chart(fig_u, use_container_width=True)
