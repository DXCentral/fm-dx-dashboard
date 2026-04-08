import streamlit as st
import pandas as pd
import pydeck as pdk
import time
import datetime
import plotly.express as px
import numpy as np
from google.cloud import bigquery
from google.oauth2 import service_account 

# 1. THEME & UI STYLING
st.set_page_config(layout="wide", page_title="SEDAP Control Center")

if 'full_screen' not in st.session_state: st.session_state.full_screen = False
if 'p_idx' not in st.session_state: st.session_state.p_idx = 0
if 'playing' not in st.session_state: st.session_state.playing = False
if 'reset_count' not in st.session_state: st.session_state.reset_count = 0
if 'selected_state' not in st.session_state: st.session_state.selected_state = None
if 'map_render_key' not in st.session_state: st.session_state.map_render_key = 1000

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
    
    /* Stats Sidebar Styling */
    .stat-header { color: #D32F2F; font-size: 0.9rem; font-weight: 400; margin-bottom: 5px; border-bottom: 1px solid #333; letter-spacing: 1px; padding-top: 15px; }
    .stat-val { font-size: 1.2rem; color: #FFF; font-weight: 300; margin-top: 5px;}
    .stat-label { font-size: 0.7rem; color: #888; text-transform: uppercase; margin-bottom: 10px; line-height: 1.1; }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING (Force Numeric & JSON-Safe)
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
        
        # Scrub DMS symbols and force numeric
        for c in [dx_lat, dx_lon, st_lat, st_lon]:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace('°', '').str.strip(), errors='coerce').astype('float32')
            
        df['Mid_Lat'] = (df[dx_lat] + df[st_lat]) / 2
        df['Mid_Lon'] = (df[dx_lon] + df[st_lon]) / 2
        df['Date_Obj'] = pd.to_datetime(df['Local_Date']).dt.date.astype(str)
        df['Time_Str'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
        dist_col = [c for c in df.columns if 'Distance' in c and 'mi' in c][0]
        
        return df, df['Local_Date'].max(), dist_col, dx_lat, dx_lon, st_lat, st_lon
    except Exception as e:
        st.error(f"System Link Failure: {e}")
        return pd.DataFrame(), None, "Distance", None, None, None, None

df, last_log_date, d_col, dx_lat, dx_lon, st_lat, st_lon = load_data()
if df.empty: st.stop()

# 3. SIDEBAR NAVIGATION
with st.sidebar:
    from streamlit_option_menu import option_menu
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(menu_title="DATA MODULES", options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC RADIUS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"], icons=["house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], default_index=2)

# 4. GLOBAL FILTERS
if not st.session_state.full_screen:
    try: st.image("SEDAP Banner.png", width=600)
    except: st.markdown("<h1 style='color: #D32F2F;'>SEDAP</h1>", unsafe_allow_html=True)
    rk = f"v{st.session_state.reset_count}"
    with st.expander(label="GLOBAL FILTERS", expanded=True):
        r1 = st.columns(5)
        f_freq = r1[0].selectbox("Frequency", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key=f"f_{rk}")
        f_dxer = r1[1].selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().astype(str).tolist()), key=f"d_{rk}")
        f_station = r1[2].selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().astype(str).tolist()), key=f"s_{rk}")
        f_state = r1[3].selectbox("State", ["All"] + sorted(df['State'].dropna().unique().astype(str).tolist()), key=f"st_{rk}")
        f_country = r1[4].selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().astype(str).tolist()), key=f"c_{rk}")
        if st.button("RESET ALL FILTERS"): st.session_state.reset_count += 1; st.rerun()

filt_df = df.copy()
f_map = {'Frequency': f_freq, 'DXer': f_dxer, 'Station': f_station, 'State': f_state, 'Country': f_country}
for col, val in f_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# 5. MODULE 2: ES-CLOUD TRACKER (RESTORED)
if selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    view_mode = st.pills("MAP LAYER", ["Es Cloud Location Heatmap", "Path Line Analysis"], default="Es Cloud Location Heatmap")
    
    hc1, hc2 = st.columns([1, 2])
    avail_days = sorted(filt_df['Local_Date'].unique())
    date_range = hc1.date_input("Select Date Range", value=(pd.to_datetime(avail_days[0]), pd.to_datetime(avail_days[-1])))
    
    if len(date_range) == 2:
        map_df = filt_df[(pd.to_datetime(filt_df['Local_Date']) >= pd.to_datetime(date_range[0])) & (pd.to_datetime(filt_df['Local_Date']) <= pd.to_datetime(date_range[1]))]
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        current_time = hc2.select_slider("Time", options=["SHOW ALL"] + times, value="SHOW ALL")
        render_df = map_df if current_time == "SHOW ALL" else map_df[map_df['Time_Str'] == current_time]
        
        # --- TYPE ERROR FIX: Clean room for Pydeck ---
        # 1. Force drop any non-numeric coordinates
        # 2. Remove actual Date Objects that break JSON
        m_pure = render_df.dropna(subset=['Mid_Lat', 'Mid_Lon', dx_lat, dx_lon, st_lat, st_lon]).copy()
        if 'Local_Date' in m_pure.columns: m_pure['Local_Date'] = m_pure['Local_Date'].astype(str)
        
        layers = []
        if view_mode == "Es Cloud Location Heatmap":
            layers.append(pdk.Layer('HeatmapLayer', data=m_pure, get_position='[Mid_Lon, Mid_Lat]', radius_pixels=65, intensity=2.0))
        else:
            layers.append(pdk.Layer('LineLayer', data=m_pure, get_source_position=f'[{dx_lon}, {dx_lat}]', get_target_position=f'[{st_lon}, {st_lat}]', get_width=1, get_color=[211, 47, 47, 45]))
        
        st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=32, longitude=-95, zoom=3.4), layers=layers, height=1000))

# 6. MODULE 3: GEOGRAPHIC RADIUS (FLYOUT FIX)
elif selected_page == "GEOGRAPHIC RADIUS":
    st.markdown("<h2 style='text-align: center; color: #D32F2F;'>GEOGRAPHIC ANALYSIS SUITE</h2>", unsafe_allow_html=True)
    geo_view = st.pills("SELECT ANALYSIS MODULE", options=["Country Stats", "Canadian Stats", "Mexican Stats", "US States", "Distance Stats"], default="US States")
    
    if geo_view == "US States":
        dx_st_col = next((c for c in filt_df.columns if 'DXer' in c and ('State' in c or 'Prov' in c)), 'DXer_State_Prov')
        mo_col = next((c for c in filt_df.columns if 'Local' in c and 'Month' in c and 'Name' in c), 'Local_Month_Name')
        yr_col = next((c for c in filt_df.columns if 'Local' in c and 'Year' in c), 'Local_Year')
        
        if not st.session_state.selected_state:
            st.info("💡 **INTERACTIVE MODE:** Click a state on the map to fly out Path Intelligence.")
            m_cols = st.columns([1])
        else:
            m_cols = st.columns([3, 1])
        
        with m_cols[0]:
            us_data = filt_df[filt_df['Country'] == 'USA']
            state_counts = us_data.groupby('State').size().reset_index(name='Logs')
            fig = px.choropleth(state_counts, locations='State', locationmode="USA-states", color='Logs', scope="usa", color_continuous_scale='Reds', template="plotly_dark")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor='black'), margin={"r":0,"t":0,"l":0,"b":0}, height=700)
            
            # Key forces re-draw only when state changes
            ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=f"us_map_{st.session_state.map_render_key}")
            if ev and ev.get("selection") and ev["selection"].get("points"):
                new_state = ev["selection"]["points"][0]["location"]
                if st.session_state.selected_state != new_state:
                    st.session_state.selected_state = new_state
                    st.rerun()

        if st.session_state.selected_state:
            with m_cols[1]:
                sel = st.session_state.selected_state
                st.markdown(f"### {sel} INTEL")
                if st.button("❌ CLEAR SELECTION", use_container_width=True):
                    st.session_state.selected_state = None
                    st.session_state.map_render_key += 1
                    st.rerun()
                
                s_of = us_data[us_data['State'] == sel]
                s_from = filt_df[filt_df[dx_st_col] == sel]

                if not s_of.empty:
                    st.markdown('<div class="stat-header">TOP RECEPTION PATHS</div>', unsafe_allow_html=True)
                    paths_in = s_from[s_from['Country'] == 'USA'].groupby('State').size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                    st.dataframe(paths_in, column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)
                    
                    st.markdown('<div class="stat-header">TOP TRANSMISSION PATHS</div>', unsafe_allow_html=True)
                    paths_out = s_of[s_of['DXer Country'] == 'USA'].groupby(dx_st_col).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                    st.dataframe(paths_out, column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)

                    st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True)
                    f = s_of.sort_values(d_col, ascending=False).iloc[0]
                    st.markdown(f'<div class="stat-val">{f[d_col]:,.0f} MILES</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-label">{f["Station"]} caught by {f["DXer"]}</div>', unsafe_allow_html=True)

# Dashboard & Metrics
elif selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    st.metric("Total Logs", f"{len(filt_df):,}")
    st.dataframe(filt_df.head(100), width=1500, hide_index=True)
