import streamlit as st
import pandas as pd
import pydeck as pdk
import time
import datetime
from google.cloud import bigquery
from google.oauth2 import service_account 

# 1. THEME & UI STYLING
st.set_page_config(layout="wide", page_title="SEDAP Control Center")

# Force Dark Mode CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@200;300;400;700&display=swap');
    html, body, [class*="st-"], div {
        font-family: 'Oswald', sans-serif !important;
        background-color: #000000 !important;
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] { background-color: #0A0A0A !important; border-right: 1px solid #1A1A1A; }
    h1, h2, h3, h4 { color: #D32F2F !important; text-transform: uppercase; letter-spacing: 2px; }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING (With Duplication Guard)
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
        
        # KEY FIX: Remove duplicates from coordinate table before joining to prevent 644k blow-up
        df_coords = df_coords.drop_duplicates(subset=['DXer_Concatenated_Location', 'Station_Concatenated_Location'])
        
        df = df_logs.merge(df_coords, left_on=['Concatenated_DXer_Location', 'Concatenated_Station_Location'], 
                           right_on=['DXer_Concatenated_Location', 'Station_Concatenated_Location'], how='left')
        
        # Coordinate Numbers
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
        st.error(f"Data Link Error: {e}")
        return pd.DataFrame(), "Error", "Distance"

df, last_log_date, d_col = load_data()

# 3. SIDEBAR
from streamlit_option_menu import option_menu
with st.sidebar:
    selected_page = option_menu(menu_title="DATA MODULES", options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER"], icons=["house-fill", "cloud-haze2"], default_index=1)

# 4. ES-CLOUD TRACKER
if selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    
    # Date Range - Defaults to show ALL data first
    avail_dates = sorted(df['Date_Obj'].unique())
    date_range = st.date_input("Filter Dates", value=(avail_dates[0], avail_dates[-1]))
    
    if isinstance(date_range, tuple) and len(date_range) == 2:
        map_df = df[(df['Date_Obj'] >= date_range[0]) & (df['Date_Obj'] <= date_range[1])]
    else:
        map_df = df[df['Date_Obj'] == date_range]

    times = sorted(map_df['Time_Str'].dropna().unique().tolist())
    
    # 5. THE MAP & PLAYBACK ENGINE
    map_container = st.empty()
    control_container = st.container()

    with control_container:
        hc1, hc2, hc3 = st.columns([2, 1, 1])
        sel_time = hc1.select_slider("Timing Control", options=["SHOW ALL"] + times, value="SHOW ALL")
        play_btn = hc2.button("▶ PLAY")
        stop_btn = hc3.button("⏹ STOP")

    # Heatmap Logic
    def draw_map(time_val):
        if time_val == "SHOW ALL":
            render_df = map_df
        else:
            # 60 min window
            t_obj = datetime.datetime.strptime(time_val, '%H:%M')
            t_min = (t_obj - datetime.timedelta(minutes=60)).strftime('%H:%M')
            render_df = map_df[(map_df['Time_Str'] <= time_val) & (map_df['Time_Str'] >= t_min)]
        
        map_ready = render_df[['Mid_Lat', 'Mid_Lon']].dropna()
        
        layer = pdk.Layer(
            'HeatmapLayer', data=map_ready, get_position='[Mid_Lon, Mid_Lat]',
            radius_pixels=60, intensity=2, threshold=0.03,
            color_range=[[183, 28, 28, 50], [211, 47, 47, 150], [255, 255, 255, 255]]
        )
        
        # MAPBOX STYLE (Force Dark with Borders)
        view = pdk.ViewState(latitude=38, longitude=-95, zoom=3.5, pitch=0)
        return pdk.Deck(layers=[layer], initial_view_state=view, map_style='mapbox://styles/mapbox/dark-v10')

    if play_btn:
        for t in times:
            with map_container:
                st.pydeck_chart(draw_map(t))
                st.write(f"### 🕒 CURRENT TIME: {t}")
            time.sleep(0.1)
    else:
        with map_container:
            st.pydeck_chart(draw_map(sel_time))

# 6. DASHBOARD
elif selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    st.metric("Total Clean Logs", f"{len(df):,}")
    st.dataframe(df.head(100), width='stretch')
