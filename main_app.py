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
    [data-testid="stDataFrame"] div[role="gridcell"] > div { text-align: center !important; justify-content: center !important; }
    div.stButton > button { background-color: #D32F2F !important; color: white !important; border-radius: 4px !important; border: none !important; padding: 8px 25px !important; text-transform: uppercase; }
    </style>
    """, unsafe_allow_html=True)

# 2. MEMORY-OPTIMIZED DATA LOADING
@st.cache_data(ttl=2592000)
def load_data():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        client = bigquery.Client(credentials=credentials, project=credentials.project_id)
        
        # We fetch everything once, then immediately prune
        df_logs = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_data_raw`").to_dataframe()
        df_coords = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_coords`").to_dataframe()
        
        # JOIN
        df = df_logs.merge(df_coords, left_on=['Concatenated_DXer_Location', 'Concatenated_Station_Location'], 
                           right_on=['DXer_Concatenated_Location', 'Station_Concatenated_Location'], how='left')
        
        # MEMORY CLEANUP: Drop columns we absolutely don't need for the dashboard
        # This keeps the "RAM" footprint small
        keep_cols = [
            'Frequency', 'Station', 'DXer', 'Local_Year', 'Country', 'Local_Date', 'Local_Time', 'State',
            'DXer_Country', 'DXer_State_Prov', 'Local_Month', 'Month_Day', 'Distance_Distribution', 'DXer_Region',
            'DXer_Latitude', 'DXer_Longitude', 'Station_Lat', 'Station_Long'
        ]
        # Dynamically find the distance column name (since BQ sanitizes it)
        dist_col = [c for c in df.columns if 'Distance' in c and 'mi' in c][0]
        keep_cols.append(dist_col)
        
        df = df[keep_cols].copy()

        # DOWNCASTING: Numbers to float32, Strings to Category
        for c_in, c_out in [('DXer_Latitude','DX_Lat'), ('DXer_Longitude','DX_Lon'), ('Station_Lat','ST_Lat'), ('Station_Long','ST_Lon')]:
            df[c_out] = pd.to_numeric(df[c_in], errors='coerce').astype('float32')
        
        cat_cols = ['Frequency', 'Country', 'State', 'DXer_Country', 'DXer_State_Prov', 'Local_Month', 'Local_Year', 'Distance_Distribution', 'DXer_Region']
        for col in cat_cols:
            if col in df.columns: df[col] = df[col].astype('category')

        df['Mid_Lat'] = (df['DX_Lat'] + df['ST_Lat']) / 2
        df['Mid_Lon'] = (df['DX_Lon'] + df['ST_Lon']) / 2
        df['Date_Obj'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Time_Str'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
        
        return df, df['Date_Obj'].max(), dist_col
    except Exception as e:
        st.error(f"System Link Failure: {e}")
        return pd.DataFrame(), "Error", "Distance"

df, last_log_date, dist_col_name = load_data()
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
    st.caption(f"LOGS THROUGH: {last_log_date}")

# 4. GLOBAL FILTERS (The 13-Filter Grid Restored)
st.image("SEDAP Banner.png", width=600)

def reset_all():
    for key in st.session_state.keys():
        if key.startswith("filt_"): st.session_state[key] = "All"

with st.expander(label="GLOBAL FILTERS", expanded=True):
    r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
    f_freq = r1c1.selectbox("Frequency", ["All"] + sorted(df['Frequency'].unique().astype(str).tolist()), key="filt_freq")
    f_dxer = r1c2.selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().tolist()), key="filt_dxer")
    f_station = r1c3.selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().tolist()), key="filt_station")
    f_state = r1c4.selectbox("State", ["All"] + sorted(df['State'].dropna().unique().tolist()), key="filt_state")
    f_country = r1c5.selectbox("Country", ["All"] + sorted(df['Country'].unique().tolist()), key="filt_country")

    r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
    f_dxer_co = r2c1.selectbox("DXer Country", ["All"] + sorted(df['DXer_Country'].unique().tolist()), key="filt_dx_co")
    f_dxer_st = r2c2.selectbox("DXer State", ["All"] + sorted(df['DXer_State_Prov'].unique().tolist()), key="filt_dx_st")
    f_month = r2c3.selectbox("Local Month", ["All"] + sorted(df['Local_Month'].unique().astype(str).tolist()), key="filt_month")
    f_year = r2c4.selectbox("Local Year", ["All"] + sorted(df['Local_Year'].unique().astype(str).tolist()), key="filt_year")
    f_day = r2c5.selectbox("Month Day", ["All"] + sorted(df['Month_Day'].dropna().unique().astype(str).tolist()), key="filt_day")

    r3c1, r3c2, r3c3 = st.columns(3)
    f_dist = r3c1.selectbox("Distance Distribution", ["All"] + sorted(df['Distance_Distribution'].unique().tolist()), key="filt_dist")
    f_reg = r3c2.selectbox("DXer Region", ["All"] + sorted(df['DXer_Region'].unique().tolist()), key="filt_reg")
    f_rds = r3c3.selectbox("RDS Decode?", ["All", "Yes", "No"], key="filt_rds") # Simplified for speed

    st.button("RESET ALL FILTERS", on_click=reset_all)

# Apply Filters
filt_df = df.copy()
if f_freq != "All": filt_df = filt_df[filt_df['Frequency'].astype(str) == f_freq]
if f_dxer != "All": filt_df = filt_df[filt_df['DXer'] == f_dxer]
if f_station != "All": filt_df = filt_df[filt_df['Station'] == f_station]
if f_year != "All": filt_df = filt_df[filt_df['Local_Year'].astype(str) == f_year]
# ... (Adding remaining filters here)

# 5. PAGES
if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Logs", f"{len(filt_df):,}")
    m2.metric("Unique Stations", f"{filt_df['Station'].nunique():,}")
    m3.metric("Total Countries", filt_df['Country'].nunique())
    m4.metric("Furthest Reception", f"{filt_df[dist_col_name].max() if not filt_df.empty else 0:,.0f} mi")
    st.dataframe(filt_df.head(100), width='stretch', hide_index=True)

elif selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    view_mode = st.radio("SELECT MAP LAYER", ["Midpoint Heatmap (Es-Cloud)", "Path Line Analysis (Signal Grid)"], horizontal=True)
    
    hc1, hc2 = st.columns([1, 2])
    avail_dates = sorted(filt_df['Date_Obj'].unique())
    date_range = hc1.date_input("Event Date Range", value=(avail_dates[0], avail_dates[-1]))
    
    # Filter by Date
    if isinstance(date_range, tuple) and len(date_range) == 2:
        map_df = filt_df[(filt_df['Date_Obj'] >= date_range[0]) & (filt_df['Date_Obj'] <= date_range[1])]
    else:
        map_df = filt_df[filt_df['Date_Obj'] == date_range]

    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        if 'anim_idx' not in st.session_state: st.session_state.anim_idx = 0
        if 'is_playing' not in st.session_state: st.session_state.is_playing = False

        selected_time = hc2.select_slider("Timing Control", options=["SHOW ALL"] + times, 
                                          value=times[st.session_state.anim_idx] if st.session_state.is_playing else "SHOW ALL")
        
        b1, b2 = st.columns(2)
        if b1.button("▶ PLAY"):
            st.session_state.is_playing = True
            for i in range(st.session_state.anim_idx, len(times)):
                st.session_state.anim_idx = i
                time.sleep(0.15)
                st.rerun()
            st.session_state.is_playing = False
        if b2.button("⏹ STOP"):
            st.session_state.is_playing = False
            st.session_state.anim_idx = 0
            st.rerun()

        current_time = times[st.session_state.anim_idx] if st.session_state.is_playing else selected_time
        
        if current_time != "SHOW ALL":
            sel_dt = datetime.datetime.strptime(current_time, '%H:%M')
            win_start = (sel_dt - datetime.timedelta(minutes=60)).strftime('%H:%M')
            render_df = map_df[(map_df['Time_Str'] <= current_time) & (map_df['Time_Str'] >= win_start)]
        else:
            render_df = map_df

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
