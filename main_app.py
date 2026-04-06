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
    h1, h2, h3, h4 { color: #D32F2F !important; font-family: 'Oswald', sans-serif !important; text-transform: uppercase; letter-spacing: 3px; }
    [data-testid="stSidebar"] { background-color: #0A0A0A; border-right: 1px solid #1A1A1A; min-width: 320px !important; }
    [data-testid="stDataFrame"] div[role="gridcell"] > div { text-align: center !important; justify-content: center !important; }
    div.stButton > button { background-color: #D32F2F !important; color: white !important; border-radius: 4px !important; border: none !important; padding: 8px 25px !important; font-family: 'Oswald', sans-serif !important; text-transform: uppercase; }
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
        
        # JOIN using exact BQ underscored names
        df = df_logs.merge(
            df_coords, 
            left_on=['Concatenated_DXer_Location', 'Concatenated_Station_Location'], 
            right_on=['DXer_Concatenated_Location', 'Station_Concatenated_Location'], 
            how='left'
        )

        # Coordinate Standardization
        df['DX_Lat'] = pd.to_numeric(df['DXer_Latitude'], errors='coerce')
        df['DX_Lon'] = pd.to_numeric(df['DXer_Longitude'], errors='coerce')
        df['ST_Lat'] = pd.to_numeric(df['Station_Lat'], errors='coerce')
        df['ST_Lon'] = pd.to_numeric(df['Station_Long'], errors='coerce')
        df['Mid_Lat'] = (df['DX_Lat'] + df['ST_Lat']) / 2
        df['Mid_Lon'] = (df['DX_Lon'] + df['ST_Lon']) / 2
        
        # Keep Date/Time as Strings ONLY
        df['Formatted_Date'] = pd.to_datetime(df['Local_Date']).dt.strftime('%Y-%m-%d')
        df['Time_Str'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
            
        return df, df['Formatted_Date'].max()
    except Exception as e:
        st.error(f"Critical System Error: {e}")
        return pd.DataFrame(), "Error"

df, last_log_date = load_data()

# 3. SIDEBAR NAVIGATION
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(menu_title="DATA MODULES", options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC RADIUS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"], icons=["house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], default_index=0)

# 4. GLOBAL FILTERS
st.image("SEDAP Banner.png", width=600)
with st.expander(label="GLOBAL FILTERS", expanded=True):
    c1, c2, c3, c4, c5 = st.columns(5)
    f_freq = c1.selectbox("Frequency", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key="filt_freq")
    f_dxer = c2.selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().tolist()), key="filt_dxer")
    f_station = c3.selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().tolist()), key="filt_station")
    f_year = c4.selectbox("Local Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key="filt_year")
    f_country = c5.selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().tolist()), key="filt_country")

filt_df = df.copy()
if f_freq != "All": filt_df = filt_df[filt_df['Frequency'].astype(str) == f_freq]
if f_dxer != "All": filt_df = filt_df[filt_df['DXer'] == f_dxer]
if f_station != "All": filt_df = filt_df[filt_df['Station'] == f_station]
if f_year != "All": filt_df = filt_df[filt_df['Local_Year'].astype(str) == f_year]
if f_country != "All": filt_df = filt_df[filt_df['Country'] == f_country]

st.markdown("---")

# 5. PAGE LOGIC
if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    # Metric logic...
    st.dataframe(filt_df.head(100), width='stretch', hide_index=True)

elif selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    view_mode = st.radio("SELECT MAP LAYER", ["Midpoint Heatmap (Es-Cloud)", "Path Line Analysis (Signal Grid)"], horizontal=True)
    
    # 5a. DYNAMIC CONTROLS
    hc1, hc2 = st.columns([1, 2])
    avail_dates = sorted(filt_df['Formatted_Date'].unique())
    date_sel = hc1.date_input("Event Date Range", value=(pd.to_datetime(avail_dates[0]), pd.to_datetime(avail_dates[-1])))
    
    # Filter map_df
    start_str = date_sel[0].strftime('%Y-%m-%d')
    end_str = date_sel[1].strftime('%Y-%m-%d') if len(date_sel) > 1 else start_str
    map_df = filt_df[(filt_df['Formatted_Date'] >= start_str) & (filt_df['Formatted_Date'] <= end_str)]

    if not map_df.empty:
        time_options = ["SHOW ALL"] + sorted(map_df['Time_Str'].dropna().unique().tolist())
        selected_time = hc2.select_slider("Timing Control", options=time_options, value="SHOW ALL")
        
        # 5b. PREPARE THE DATA FOR PYDECK (CRITICAL: NUMERIC ONLY)
        if selected_time != "SHOW ALL":
            render_df = map_df[map_df['Time_Str'] == selected_time]
        else:
            render_df = map_df

        layers = []
        if view_mode == "Midpoint Heatmap (Es-Cloud)":
            # WE ONLY PASS THE COORDS TO PYDECK TO AVOID SERIALIZATION ERRORS
            map_ready = render_df[['Mid_Lat', 'Mid_Lon']].dropna()
            map_ready = map_ready[map_ready['Mid_Lat'] > 0]
            
            layers.append(pdk.Layer(
                'HeatmapLayer', data=map_ready, get_position='[Mid_Lon, Mid_Lat]',
                radius_pixels=80, intensity=1, threshold=0.03,
                color_range=[[211, 47, 47, 50], [211, 47, 47, 180], [255, 255, 255, 255]]
            ))
            ttip = True
        else:
            # Arc Layer Cleanup - PASS ONLY REQUIRED NUMERIC COLUMNS
            map_ready = render_df[['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']].dropna()
            map_ready = map_ready[map_ready['DX_Lat'] > 0]
            path_data = map_ready.groupby(['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']).size().reset_index(name='density')
            
            layers.append(pdk.Layer(
                'ArcLayer', data=path_data,
                get_source_position='[DX_Lon, DX_Lat]', get_target_position='[ST_Lon, ST_Lat]',
                get_width='density * 2.0',
                get_source_color=[211, 47, 47, 140], get_target_color=[255, 255, 255, 140],
                pickable=True
            ))
            ttip = {"text": "Logs on this path: {density}"}

        # FINAL RENDER
        st.pydeck_chart(pdk.Deck(
            map_style='mapbox://styles/mapbox/dark-v10',
            initial_view_state=pdk.ViewState(latitude=39, longitude=-98, zoom=3.8, pitch=45),
            layers=layers,
            tooltip=ttip
        ))
