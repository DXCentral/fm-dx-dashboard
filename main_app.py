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
if 'selected_region' not in st.session_state: st.session_state.selected_region = None
if 'map_key' not in st.session_state: st.session_state.map_key = 6000

if st.session_state.full_screen:
    st.markdown("""<style>[data-testid="stSidebar"], [data-testid="stHeader"] { display: none !important; } .stMain { padding: 0 !important; }</style>""", unsafe_allow_html=True)

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
    h1, h2, h3, h4 { color: #D32F2F !important; text-transform: uppercase; letter-spacing: 3px; }
    [data-testid="stSidebar"] { background-color: #0A0A0A; border-right: 1px solid #1A1A1A; }
    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; font-weight: 200; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; }
    .stat-header { color: #D32F2F; font-size: 0.95rem; font-weight: 400; margin-bottom: 5px; border-bottom: 1px solid #333; letter-spacing: 1px; padding-top: 15px; }
    .stat-val { font-size: 1.3rem; color: #FFF; font-weight: 300; margin-top: 5px;}
    .stat-label { font-size: 0.75rem; color: #888; text-transform: uppercase; margin-bottom: 8px; line-height: 1.2; }
    .window-box { border-left: 2px solid #D32F2F; padding-left: 10px; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

def get_avg_date(dates_series):
    if dates_series.empty: return "N/A"
    ds = pd.to_datetime(dates_series)
    return (datetime.datetime(2024, 1, 1) + datetime.timedelta(days=int(ds.dt.dayofyear.mean()) - 1)).strftime('%b %d')

# 2. DATA LOADING (V2.1 PERMISSIONS)
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
        l_dx, l_st = [c for c in df_logs.columns if 'Concatenated' in c and 'DX' in c][0], [c for c in df_logs.columns if 'Concatenated' in c and 'Station' in c][0]
        c_dx, c_st = [c for c in df_coords.columns if 'Concatenated' in c and 'DX' in c][0], [c for c in df_coords.columns if 'Concatenated' in c and 'Station' in c][0]
        df_coords = df_coords.drop_duplicates(subset=[c_dx, c_st])
        df = df_logs.merge(df_coords, left_on=[l_dx, l_st], right_on=[c_dx, c_st], how='left')
        dx_lat, dx_lon = [c for c in df.columns if 'DXer_Latitude' in c or ('DX' in c and 'Lat' in c)][0], [c for c in df.columns if 'DXer_Longitude' in c or ('DX' in c and 'Lon' in c)][0]
        st_lat, st_lon = [c for c in df.columns if 'Station_Lat' in c or ('ST' in c and 'Lat' in c)][0], [c for c in df.columns if 'Station_Long' in c or ('ST' in c and 'Lon' in c)][0]
        for c in [dx_lat, dx_lon, st_lat, st_lon]: df[c] = pd.to_numeric(df[c].astype(str).str.replace('°', '').str.strip(), errors='coerce').astype('float32')
        df['Mid_Lat'], df['Mid_Lon'] = (df[dx_lat] + df[st_lat]) / 2, (df[dx_lon] + df[st_lon]) / 2
        df['Date_Obj'], df['Time_Str'] = pd.to_datetime(df['Local_Date']).dt.date, pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
        dist_col = [c for c in df.columns if 'Distance' in c and 'mi' in c][0]
        return df, df['Date_Obj'].max(), dist_col, dx_lat, dx_lon, st_lat, st_lon
    except Exception as e:
        st.error(f"System Link Failure: {e}"); return pd.DataFrame(), None, "Distance", None, None, None, None

df, last_date, d_col, dx_lat, dx_lon, st_lat, st_lon = load_data()
if df.empty: st.stop()

# 3. SIDEBAR NAVIGATION
from streamlit_option_menu import option_menu
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu("MODULES", ["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC ANALYSIS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"], 
        icons=["house", "cloud", "geo", "clock", "graph-up", "broadcast", "diagram-3"], default_index=0)

# 4. GLOBAL FILTERS
if not st.session_state.full_screen:
    st.image("SEDAP Banner.png", width=600)
    rk = f"v{st.session_state.reset_count}"
    with st.expander("GLOBAL FILTERS", expanded=True):
        r1 = st.columns(5)
        f_freq = r1[0].selectbox("Frequency", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key=f"f1_{rk}")
        f_dxer = r1[1].selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().astype(str).tolist()), key=f"f2_{rk}")
        f_station = r1[2].selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().astype(str).tolist()), key=f"f3_{rk}")
        f_state = r1[3].selectbox("State", ["All"] + sorted(df['State'].dropna().unique().astype(str).tolist()), key=f"f4_{rk}")
        f_country = r1[4].selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().astype(str).tolist()), key=f"f5_{rk}")
        if st.button("RESET ALL FILTERS"): st.session_state.reset_count += 1; st.rerun()
else: f_freq, f_dxer, f_station, f_state, f_country = ["All"]*5

filt_df = df.copy()
f_map = {'Frequency':f_freq, 'DXer':f_dxer, 'Station':f_station, 'State':f_state, 'Country':f_country}
for col, val in f_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# 5. MODULE 1: DASHBOARD
if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m = st.columns(7)
    m[0].metric("Total Logs", f"{len(filt_df):,}"); m[1].metric("Unique Stations", f"{filt_df['Station'].nunique():,}")
    m[2].metric("US States", filt_df[filt_df['Country']=='USA']['State'].nunique()); m[3].metric("CA Prov", filt_df[filt_df['Country']=='Canada']['State'].nunique())
    m[4].metric("MX States", filt_df[filt_df['Country']=='Mexico']['State'].nunique()); m[5].metric("Countries", filt_df['Country'].nunique())
    m[6].metric("Max Dist", f"{filt_df[d_col].max() if not filt_df.empty else 0:,.0f} mi")
    st.dataframe(filt_df[['Local_Date', 'Frequency', 'Station', 'City', 'State', 'DXer', d_col]].head(100), use_container_width=True)

# 6. MODULE 2: ES-CLOUD TRACKER
elif selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    vm = st.pills("LAYER", ["Es Cloud Location Heatmap", "Path Line Analysis"], default="Es Cloud Location Heatmap")
    hc1, hc2 = st.columns([1, 2])
    with hc1:
        range_on = st.checkbox("Enable Range", value=True) 
        avail = sorted(filt_df['Date_Obj'].unique()) 
        if range_on:
            dr = st.date_input("Select Range", value=(avail[0], avail[-1]))
            map_df = filt_df[(filt_df['Date_Obj'] >= dr[0]) & (filt_df['Date_Obj'] <= dr[1])] if len(dr)==2 else filt_df
        else:
            ds = st.date_input("Select Date", value=avail[-1]); map_df = filt_df[filt_df['Date_Obj'] == ds]
        speed_sets = {"1x": {"delay": 0.2, "step": 1}, "2x": {"delay": 0.1, "step": 2}, "4x": {"delay": 0.01, "step": 4}}
        play_speed = st.selectbox("Speed", options=list(speed_sets.keys()), index=1)
        if st.button("📺 FULL SCREEN"): st.session_state.full_screen = not st.session_state.full_screen; st.rerun()

    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        pb1, pb2, pb_txt = st.columns([1, 1, 3])
        if pb1.button("▶ PLAY"): st.session_state.playing = True; st.session_state.p_idx = 0; st.rerun()
        if pb2.button("⏹ STOP"): st.session_state.playing = False; st.rerun()
        current_time = times[st.session_state.p_idx] if st.session_state.playing else hc2.select_slider("Time", options=["SHOW ALL"] + times, value="SHOW ALL")
        pb_txt.write(f"## 🕒 CURRENT TIME: {current_time}")
        r_df = map_df if current_time == "SHOW ALL" else map_df[map_df['Time_Str'] == current_time]
        layers = [pdk.Layer('HeatmapLayer', data=r_df[['Mid_Lat', 'Mid_Lon']].dropna(), get_position='[Mid_Lon, Mid_Lat]', radius_pixels=65, intensity=2.0, color_range=[[183, 28, 28, 60], [211, 47, 47, 150], [244, 67, 54, 200], [255, 235, 238, 230], [255, 255, 255, 255]])]
        st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=32, longitude=-95, zoom=3.4), layers=layers, height=1000))
        if st.session_state.playing:
            conf = speed_sets[play_speed]; time.sleep(conf['delay'])
            if st.session_state.p_idx + conf['step'] < len(times): st.session_state.p_idx += conf['step']; st.rerun()
            else: st.session_state.playing = False; st.rerun()

# 7. MODULE 3: GEOGRAPHIC ANALYSIS (UNIFIED NORTH AMERICA)
elif selected_page == "GEOGRAPHIC ANALYSIS":
    st.markdown("<h2 style='text-align: center; color: #D32F2F;'>NORTH AMERICAN GEOGRAPHIC INTEL</h2>", unsafe_allow_html=True)
    gv = st.pills("MODULE", options=["Continental Map", "Distance Stats"], default="Continental Map")
    st.markdown("---")
    
    if gv == "Continental Map":
        dx_st_col = next((c for c in filt_df.columns if 'DXer' in c and ('State' in c or 'Prov' in c)), 'DXer_State_Prov')
        mo_col, yr_col = next((c for c in filt_df.columns if 'Local' in c and 'Month' in c and 'Name' in c), 'Local_Month_Name'), next((c for c in filt_df.columns if 'Local' in c and 'Year' in c), 'Local_Year')
        gs = [[0, 'rgb(100,0,0)'], [0.2, 'rgb(183,28,28)'], [0.5, 'rgb(211,47,47)'], [0.8, 'rgb(255,69,0)'], [1, 'rgb(255,165,0)']]

        if not st.session_state.selected_region: col_m, col_f = st.columns([1, 0.001])
        else: col_m, col_f = st.columns([3, 1])
        
        with col_m:
            counts = filt_df.groupby(['State']).size().reset_index(name='Logs')
            # Bulletproof GeoJSON link for Continental Borders (USA + CANADA + MEXICO)
            geojson_url = "https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json" # Foundation
            # Note: For pure Streamlit reliability, we use locationmode 'country names' for Canada/MX and standard map for US.
            fig = px.choropleth(counts, locations='State', locationmode="country names", color='Logs', scope="north america", color_continuous_scale=gs, template="plotly_dark")
            fig.update_geos(lataxis_range=[15, 75], lonaxis_range=[-170, -50], showcountries=True, countrycolor="#444", showsubunits=True, subunitcolor="#222")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)'), margin={"r":0,"t":0,"l":0,"b":0}, height=800)
            ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=f"unified_{st.session_state.map_key}")
            if ev and ev.get("selection") and ev["selection"].get("points"):
                st.session_state.selected_region = ev["selection"]["points"][0]["location"]; st.rerun()

        if st.session_state.selected_region:
            with col_f:
                sel = st.session_state.selected_region
                st.markdown(f"### {sel} INTEL")
                if st.button("❌ CLEAR SELECTION"): st.session_state.selected_region = None; st.session_state.map_key += 1; st.rerun()
                
                s_of = filt_df[filt_df['State'] == sel]
                s_from = filt_df[filt_df[dx_st_col] == sel]

                # HERO STATION
                st.markdown('<div class="stat-header">MOST HEARD STATION</div>', unsafe_allow_html=True)
                if not s_of.empty:
                    top = s_of.groupby(['Frequency', 'Station', 'City']).size().idxmax()
                    st.markdown(f'<div class="stat-val">{top[1]}</div><div class="stat-label">{top[0]} MHz • {top[2]}</div>', unsafe_allow_html=True)
                
                # PEAK SEASONALITY & WINDOW
                st.markdown('<div class="stat-header">PEAK SEASONALITY</div>', unsafe_allow_html=True)
                if not s_of.empty:
                    m_c = s_of[mo_col].value_counts()
                    st.markdown(f'<div class="stat-val">{str(m_c.idxmax()).upper()} ({m_c.max()} Logs)</div>', unsafe_allow_html=True)
                    st.markdown('<div class="window-box">', unsafe_allow_html=True)
                    of_dates = pd.to_datetime(s_of['Local_Date'])
                    st.markdown(f'<div class="stat-label">Start: {get_avg_date(of_dates.groupby(s_of["Local_Year"]).min())} | Peak: {get_avg_date(of_dates)} | End: {get_avg_date(of_dates.groupby(s_of["Local_Year"]).max())}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                # TOP PATHS
                st.markdown('<div class="stat-header">TOP PATHS (US/CA/MX)</div>', unsafe_allow_html=True)
                p_in = s_from.groupby('State').size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                st.dataframe(p_in, column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)

                # TOP 5 STATIONS
                st.markdown('<div class="stat-header">TOP 5 STATIONS</div>', unsafe_allow_html=True)
                if not s_of.empty:
                    t5 = s_of.groupby(['Frequency', 'Station']).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                    st.dataframe(t5, column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)
