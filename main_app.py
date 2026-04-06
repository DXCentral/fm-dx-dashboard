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
    html, body, [class*="st-"] { font-family: 'Oswald', sans-serif !important; background-color: #000000; color: #FFFFFF; font-weight: 300; }
    [data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarCollapseButton"] span, [data-testid="stExpanderIcon"], .st-emotion-cache-p5msec, .st-emotion-cache-1vt4y6f { display: none !important; visibility: hidden !important; }
    h1, h2, h3, h4 { color: #D32F2F !important; font-family: 'Oswald', sans-serif !important; font-weight: 400; text-transform: uppercase; letter-spacing: 3px; }
    [data-testid="stSidebar"] { background-color: #0A0A0A; border-right: 1px solid #1A1A1A; min-width: 320px !important; }
    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; font-weight: 200; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; }
    div.stButton > button { background-color: #D32F2F !important; color: white !important; border-radius: 4px !important; border: none !important; padding: 8px 25px !important; font-family: 'Oswald', sans-serif !important; letter-spacing: 2px; text-transform: uppercase; }
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
        
        # Discovery & Join
        log_dx_col = [c for c in df_logs.columns if 'DXer' in c and 'Concatenated' in c][0]
        log_st_col = [c for c in df_logs.columns if 'Station' in c and 'Concatenated' in c][0]
        coord_dx_col = [c for c in df_coords.columns if 'DXer' in c and 'Concatenated' in c][0]
        coord_st_col = [c for c in df_coords.columns if 'Station' in c and 'Concatenated' in c][0]

        df = df_logs.merge(df_coords, left_on=[log_dx_col, log_st_col], right_on=[coord_dx_col, coord_st_col], how='left')

        # Clean Headers & Numeric Conversion
        lat_cols = [c for c in df.columns if 'Lat' in c]
        lon_cols = [c for c in df.columns if 'Lon' in c or 'Long' in c]
        
        df = df.rename(columns={
            [c for c in lat_cols if 'DXer' in c][0]: 'DX_Lat',
            [c for c in lon_cols if 'DXer' in c][0]: 'DX_Lon',
            [c for c in lat_cols if 'Station' in c][0]: 'ST_Lat',
            [c for c in lon_cols if 'Station' in c][0]: 'ST_Lon'
        })
        
        for col in ['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df['Mid_Lat'] = (df['DX_Lat'] + df['ST_Lat']) / 2
        df['Mid_Lon'] = (df['DX_Lon'] + df['ST_Lon']) / 2
        df['Local_Date'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Clean_Time'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.time
            
        return df, df['Local_Date'].max()
    except Exception as e:
        st.error(f"System Link Failure: {e}")
        return pd.DataFrame(), "Error"

df, last_log_date = load_data()

# 3. NAVIGATION & GLOBAL FILTERS
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(menu_title="DATA MODULES", options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC RADIUS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"], icons=["house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], default_index=0)

# (Insert standard filter grid here as in v18.0)
filt_df = df.copy() 

# 5. ES-CLOUD TRACKER
if selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    view_mode = st.radio("SELECT MAP LAYER", ["Midpoint Heatmap (Es-Cloud)", "Path Line Analysis (Signal Grid)"], horizontal=True)
    
    # 5a. DYNAMIC CONTROLS
    hc1, hc2 = st.columns([1, 3])
    
    # Date Range - Default to All
    available_dates = sorted(filt_df['Local_Date'].unique())
    date_selection = hc1.date_input("Event Date Range", value=(available_dates[0], available_dates[-1]), min_value=available_dates[0], max_value=available_dates[-1])
    
    # Apply date filter immediately
    if isinstance(date_selection, tuple) and len(date_selection) == 2:
        map_df = filt_df[(filt_df['Local_Date'] >= date_selection[0]) & (filt_df['Local_Date'] <= date_selection[1])]
    else:
        map_df = filt_df[filt_df['Local_Date'] == date_selection]

    # Timing Control (Scrubber)
    if not map_df.empty:
        times = sorted(map_df['Clean_Time'].unique())
        # Default to All Times unless moved
        if 'anim_idx' not in st.session_state: st.session_state.anim_idx = -1 
        
        options_with_all = ["SHOW ALL"] + [t.strftime("%H:%M") for t in times]
        selected_time_str = hc2.select_slider("Timing Control", options=options_with_all, value="SHOW ALL")
        
        # 5b. MAP DATA PREP
        if selected_time_str != "SHOW ALL":
            sel_time = pd.to_datetime(selected_time_str).time()
            window_start = (pd.to_datetime(selected_time_str) - pd.Timedelta(minutes=60)).time()
            map_data = map_df[(map_df['Clean_Time'] <= sel_time) & (map_df['Clean_Time'] >= window_start)]
        else:
            map_data = map_df

        # 5c. RENDER LAYERS (Strict Numeric Cleanup)
        layers = []
        if view_mode == "Midpoint Heatmap (Es-Cloud)":
            # Filter for rows that have BOTH valid lat and lon
            clean_heat = map_data.dropna(subset=['Mid_Lat', 'Mid_Lon'])
            clean_heat = clean_heat[(clean_heat['Mid_Lat'] != 0) & (clean_heat['Mid_Lon'] != 0)]
            
            layers.append(pdk.Layer(
                'HeatmapLayer', data=clean_heat, get_position='[Mid_Lon, Mid_Lat]',
                radius_pixels=80, intensity=1, threshold=0.03,
                color_range=[[211, 47, 47, 50], [211, 47, 47, 180], [255, 255, 255, 255]]
            ))
            ttip = True
        else:
            # Arc Layer Cleanup
            clean_arc = map_data.dropna(subset=['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon'])
            clean_arc = clean_arc[(clean_arc['DX_Lat'] != 0) & (clean_arc['ST_Lat'] != 0)]
            
            path_counts = clean_arc.groupby(['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']).size().reset_index(name='density')
            layers.append(pdk.Layer(
                'ArcLayer', data=path_counts,
                get_source_position='[DX_Lon, DX_Lat]', get_target_position='[ST_Lon, ST_Lat]',
                get_width='density * 2.0',
                get_source_color=[211, 47, 47, 140], get_target_color=[255, 255, 255, 140],
                pickable=True
            ))
            ttip = {"text": "Logs on this path: {density}"}

        st.pydeck_chart(pdk.Deck(
            map_style='mapbox://styles/mapbox/dark-v10',
            initial_view_state=pdk.ViewState(latitude=39, longitude=-98, zoom=3.8, pitch=45),
            layers=layers,
            tooltip=ttip
        ))
    else:
        st.warning("No sensor data found for the selected temporal window.")
