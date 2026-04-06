import streamlit as st
import pandas as pd
import pydeck as pdk
from google.cloud import bigquery
from google.oauth2 import service_account
from streamlit_option_menu import option_menu
import time

# 1. THEME & UI STYLING (The "Tron" Console Look)
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

    /* THE FINAL SHIELD: Eliminates "keyboard_double_a" and "arro" leaks */
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stSidebarCollapseButton"] span,
    [data-testid="stExpanderIcon"],
    .st-emotion-cache-p5msec,
    .st-emotion-cache-1vt4y6f,
    .st-emotion-cache-6q9sum,
    .st-emotion-cache-ue6h4q { 
        display: none !important; 
        visibility: hidden !important;
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

    /* Centering Data in Table */
    [data-testid="stDataFrame"] div[role="gridcell"] > div {
        justify-content: center !important;
        text-align: center !important;
    }

    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; font-weight: 200; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; }

    div.stButton > button {
        background-color: #D32F2F !important;
        color: white !important;
        border-radius: 4px !important;
        border: none !important;
        padding: 8px 25px !important;
        font-family: 'Oswald', sans-serif !important;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING (Flexible Join Engine)
@st.cache_data(ttl=2592000)
def load_data():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/bigquery", "https://www.googleapis.com/auth/drive.readonly"]
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = bigquery.Client(credentials=credentials, project=credentials.project_id, location="US")
        
        # 1. Pull Logs & Coords
        df_logs = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_data_raw`").to_dataframe()
        df_coords = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_coords`").to_dataframe()
        
        # 2. Flexible Column Discovery (Finds 'Concatenated' regardless of underscores or order)
        log_dx_col = [c for c in df_logs.columns if 'DXer' in c and 'Concatenated' in c][0]
        log_st_col = [c for c in df_logs.columns if 'Station' in c and 'Concatenated' in c][0]
        
        coord_dx_col = [c for c in df_coords.columns if 'DXer' in c and 'Concatenated' in c][0]
        coord_st_col = [c for c in df_coords.columns if 'Station' in c and 'Concatenated' in c][0]

        # 3. Perform Join
        df = df_logs.merge(
            df_coords, 
            left_on=[log_dx_col, log_st_col], 
            right_on=[coord_dx_col, coord_st_col], 
            how='left'
        )

        # 4. Process Time/Date
        df['Local_Date'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Clean_Time'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.time
        
        # Standardize Map Variable Names
        # Scans for Lat/Lon in joined results and assigns them to internal names
        lat_cols = [c for c in df.columns if 'Lat' in c]
        lon_cols = [c for c in df.columns if 'Lon' in c or 'Long' in c]
        
        df = df.rename(columns={
            [c for c in lat_cols if 'DXer' in c][0]: 'DX_Lat',
            [c for c in lon_cols if 'DXer' in c][0]: 'DX_Lon',
            [c for c in lat_cols if 'Station' in c][0]: 'ST_Lat',
            [c for c in lon_cols if 'Station' in c][0]: 'ST_Lon'
        })
        
        # Midpoint Calculation for Heatmap
        df['Mid_Lat'] = (df['DX_Lat'] + df['ST_Lat']) / 2
        df['Mid_Lon'] = (df['DX_Lon'] + df['ST_Lon']) / 2
            
        return df, df['Local_Date'].max()
    except Exception as e:
        st.error(f"System Link Failure: {e}")
        return pd.DataFrame(), "Error"

df, last_log_date = load_data()
if df.empty: st.stop()

# 3. SIDEBAR NAVIGATION
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(
        menu_title="DATA MODULES",
        options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC RADIUS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"],
        icons=["house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], 
        menu_icon="terminal",
        default_index=0,
        styles={
            "container": {"background-color": "#0A0A0A", "padding": "0px"},
            "nav-link": {"color": "white", "font-family": "Oswald, sans-serif", "font-size": "13px", "text-align": "left", "letter-spacing": "1.5px", "text-transform": "uppercase", "white-space": "nowrap"},
            "nav-link-selected": {"background-color": "#D32F2F"},
            "menu-title": {"color": "#D32F2F", "font-family": "Oswald", "font-size": "11px", "letter-spacing": "3px"}
        }
    )
    st.markdown("---")
    st.caption(f"LOGS THROUGH: {last_log_date}")

# 4. STATIC HEADER & FILTERS
st.image("SEDAP Banner.png", width=600)

def reset_all():
    for key in st.session_state.keys():
        if key.startswith("filt_"): st.session_state[key] = "All"

with st.expander(label="GLOBAL FILTERS", expanded=True):
    r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
    f_freq = r1c1.selectbox("Frequency", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key="filt_freq")
    f_dxer = r1c2.selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().tolist()), key="filt_dxer")
    f_station = r1c3.selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().tolist()), key="filt_station")
    f_state = r1c4.selectbox("State", ["All"] + sorted(df['State'].dropna().unique().tolist()), key="filt_state")
    f_country = r1c5.selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().tolist()), key="filt_country")

    r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
    f_dxer_co = r2c1.selectbox("DXer Country", ["All"] + sorted(df['DXer_Country'].dropna().unique().tolist()), key="filt_dx_co")
    f_dxer_st = r2c2.selectbox("DXer State", ["All"] + sorted(df['DXer_State_Prov'].dropna().unique().tolist()), key="filt_dx_st")
    f_month = r2c3.selectbox("Local Month", ["All"] + sorted(df['Local_Month'].dropna().unique().astype(str).tolist()), key="filt_month")
    f_year = r2c4.selectbox("Local Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key="filt_year")
    f_day = r2c5.selectbox("Month Day", ["All"] + sorted(df['Month_Day'].dropna().unique().astype(str).tolist()), key="filt_day")

    r3c1, r3c2, r3c3 = st.columns(3)
    f_dist = r3c1.selectbox("Distance Distribution", ["All"] + sorted(df['Distance_Distribution'].dropna().unique().tolist()), key="filt_dist")
    f_reg = r3c2.selectbox("DXer Region", ["All"] + sorted(df['DXer_Region'].dropna().unique().tolist()), key="filt_reg")
    rds_col = 'RDS_Decode_' if 'RDS_Decode_' in df.columns else 'RDS_Decode'
    f_rds = r3c3.selectbox("RDS Decode?", ["All"] + sorted(df[rds_col].dropna().unique().tolist()), key="filt_rds")

    bt_left, bt_mid, bt_right = st.columns([2, 1, 2])
    bt_mid.button("RESET ALL FILTERS", on_click=reset_all)

# APPLY GLOBAL FILTERS
filt_df = df.copy()
filter_map = {'Frequency': f_freq, 'DXer': f_dxer, 'Station': f_station, 'State': f_state, 'Country': f_country, 'DXer_Country': f_dxer_co, 'DXer_State_Prov': f_dxer_st, 'Local_Month': f_month, 'Local_Year': f_year, 'Month_Day': f_day, 'Distance_Distribution': f_dist, 'DXer_Region': f_reg, rds_col: f_rds}
for col, val in filter_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == str(val)]

st.markdown("---")

# 5. DATA MODULES
if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Total Logs", f"{len(filt_df):,}")
    m2.metric("Unique Stations", f"{filt_df['Station'].nunique():,}")
    m3.metric("US States", filt_df[filt_df['Country'] == 'USA']['State'].nunique())
    m4.metric("Canadian Provinces", filt_df[filt_df['Country'] == 'Canada']['State'].nunique())
    m5.metric("Mexican States", filt_df[filt_df['Country'] == 'Mexico']['State'].nunique())
    m6.metric("Total Countries", filt_df['Country'].nunique())
    dist_col = 'Distance__mi_' if 'Distance__mi_' in df.columns else 'Distance'
    m7.metric("Furthest Reception", f"{filt_df[dist_col].max() if not filt_df.empty else 0:,.0f} mi")

    st.subheader("Submitted Logs")
    row_count = st.slider("Select rows:", 1, max(len(filt_df), 10), min(len(filt_df), 100))
    st.dataframe(filt_df.head(row_count), use_container_width=True, hide_index=True)

elif selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    
    view_mode = st.radio("SELECT MAP LAYER", ["Midpoint Heatmap (Es-Cloud)", "Path Line Analysis (Signal Grid)"], horizontal=True)
    
    # Time-Lapse Controls
    hc1, hc2 = st.columns([1, 2])
    target_date = hc1.date_input("Event Date", value=last_log_date)
    day_df = filt_df[filt_df['Local_Date'] == target_date].dropna(subset=['Clean_Time', 'DX_Lat'])
    
    if not day_df.empty:
        times = sorted(day_df['Clean_Time'].unique())
        if 'anim_idx' not in st.session_state: st.session_state.anim_idx = 0
        
        selected_time = st.select_slider("Temporal Scrub", options=times, value=times[min(st.session_state.anim_idx, len(times)-1)])
        st.session_state.anim_idx = times.index(selected_time)
        
        # Player
        p1, p2 = st.columns(2)
        if p1.button("▶ PLAY"):
            for i in range(st.session_state.anim_idx, len(times)):
                st.session_state.anim_idx = i
                time.sleep(0.05)
                st.rerun()
        if p2.button("⏹ RESET"): st.session_state.anim_idx = 0; st.rerun()

        # Window: 60 min persistence
        window_start = (pd.to_datetime(str(selected_time)) - pd.Timedelta(minutes=60)).time()
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
            path_counts = map_data.groupby(['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']).size().reset_index(name='density')
            layers.append(pdk.Layer(
                'ArcLayer', data=path_counts,
                get_source_position='[DX_Lon, DX_Lat]', get_target_position='[ST_Lon, ST_Lat]',
                get_width='density * 2.5',
                get_source_color=[211, 47, 47, 140], get_target_color=[255, 255, 255, 140],
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
