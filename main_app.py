import streamlit as st
import pandas as pd
import pydeck as pdk
import time
import datetime
import plotly.express as px
import numpy as np
from google.cloud import bigquery
from google.oauth2 import service_account 

# 1. THEME & UI STYLING (RESTORED V2.1 CORE)
st.set_page_config(layout="wide", page_title="SEDAP Control Center")

if 'full_screen' not in st.session_state: st.session_state.full_screen = False
if 'p_idx' not in st.session_state: st.session_state.p_idx = 0
if 'playing' not in st.session_state: st.session_state.playing = False
if 'reset_count' not in st.session_state: st.session_state.reset_count = 0
if 'selected_state' not in st.session_state: st.session_state.selected_state = None
if 'map_key' not in st.session_state: st.session_state.map_key = 2800

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
    day_of_year = pd.to_datetime(dates_series).dt.dayofyear
    avg_day = int(day_of_year.mean())
    return (datetime.datetime(2024, 1, 1) + datetime.timedelta(days=avg_day - 1)).strftime('%b %d')

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
        st.error(f"Link Failure: {e}"); return pd.DataFrame(), None, "Distance", None, None, None, None

df, last_date, d_col, dx_lat, dx_lon, st_lat, st_lon = load_data()
if df.empty: st.stop()

# 3. SIDEBAR NAVIGATION
from streamlit_option_menu import option_menu
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu("DATA MODULES", ["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC ANALYSIS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"], 
        icons=["house", "cloud", "geo", "clock", "graph-up", "broadcast", "diagram-3"], default_index=0)

# 4. GLOBAL FILTERS (ALL 13)
if not st.session_state.full_screen:
    rk = f"v{st.session_state.reset_count}"
    with st.expander("GLOBAL FILTERS", expanded=True):
        r1 = st.columns(5)
        f_freq = r1[0].selectbox("Frequency", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key=f"f1_{rk}")
        f_dxer = r1[1].selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().astype(str).tolist()), key=f"f2_{rk}")
        f_station = r1[2].selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().astype(str).tolist()), key=f"f3_{rk}")
        f_state = r1[3].selectbox("State", ["All"] + sorted(df['State'].dropna().unique().astype(str).tolist()), key=f"f4_{rk}")
        f_country = r1[4].selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().astype(str).tolist()), key=f"f5_{rk}")
        r2 = st.columns(5)
        f_dxco = r2[0].selectbox("DXer Country", ["All"] + sorted(df['DXer_Country'].dropna().unique().astype(str).tolist()), key=f"f6_{rk}")
        f_dxst = r2[1].selectbox("DXer State", ["All"] + sorted(df['DXer_State_Prov'].dropna().unique().astype(str).tolist()), key=f"f7_{rk}")
        f_month = r2[2].selectbox("Local Month", ["All"] + sorted(df['Local_Month'].dropna().unique().astype(str).tolist()), key=f"f8_{rk}")
        f_year = r2[3].selectbox("Local Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key=f"f9_{rk}")
        f_day = r2[4].selectbox("Month Day", ["All"] + sorted(df['Month_Day'].dropna().unique().astype(str).tolist()), key=f"f10_{rk}")
        r3 = st.columns(3)
        f_dist = r3[0].selectbox("Distance Distribution", ["All"] + sorted(df['Distance_Distribution'].dropna().unique().astype(str).tolist()), key=f"f11_{rk}")
        f_reg = r3[1].selectbox("DXer Region", ["All"] + sorted(df['DXer_Region'].dropna().unique().astype(str).tolist()), key=f"f12_{rk}")
        rds_c = 'RDS Decode?' if 'RDS Decode?' in df.columns else 'RDS Decode'
        f_rds = r3[2].selectbox("RDS Decode?", ["All"] + (sorted(df[rds_c].dropna().unique().astype(str).tolist()) if rds_c in df.columns else []), key=f"f13_{rk}")
        if st.button("RESET ALL FILTERS"): st.session_state.reset_count += 1; st.rerun()
else: f_freq, f_dxer, f_station, f_state, f_country, f_dxco, f_dxst, f_month, f_year, f_day, f_dist, f_reg, f_rds = ["All"]*13

filt_df = df.copy()
f_map = {'Frequency':f_freq, 'DXer':f_dxer, 'Station':f_station, 'State':f_state, 'Country':f_country, 'DXer_Country':f_dxco, 'DXer_State_Prov':f_dxst, 'Local_Month':f_month, 'Local_Year':f_year, 'Month_Day':f_day, 'Distance_Distribution':f_dist, 'DXer_Region':f_reg, rds_c:f_rds}
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

# 6. MODULE 2: ES-CLOUD TRACKER (LOCKED PLAYBACK ENGINE)
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
        layers = []
        if vm == "Es Cloud Location Heatmap":
            layers.append(pdk.Layer('HeatmapLayer', data=r_df[['Mid_Lat', 'Mid_Lon']].dropna(), get_position='[Mid_Lon, Mid_Lat]', radius_pixels=65, intensity=2.0, color_range=[[183, 28, 28, 60], [211, 47, 47, 150], [244, 67, 54, 200], [255, 235, 238, 230], [255, 255, 255, 255]]))
        else:
            layers.append(pdk.Layer('LineLayer', data=r_df[[dx_lat, dx_lon, st_lat, st_lon]].dropna(), get_source_position=f'[{dx_lon}, {dx_lat}]', get_target_position=f'[{st_lon}, {st_lat}]', get_width=1, get_color=[211, 47, 47, 45]))
        st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=32, longitude=-95, zoom=3.4), layers=layers, height=1000))
        if st.session_state.playing:
            conf = speed_sets[play_speed]
            if st.session_state.p_idx + conf['step'] < len(times): st.session_state.p_idx += conf['step']; time.sleep(conf['delay']); st.rerun()
            else: st.session_state.playing = False; st.rerun()

# 7. MODULE 3: GEOGRAPHIC ANALYSIS
elif selected_page == "GEOGRAPHIC ANALYSIS":
    st.markdown("<h2 style='text-align: center; color: #D32F2F;'>GEOGRAPHIC ANALYSIS SUITE</h2>", unsafe_allow_html=True)
    gv = st.pills("MODULE", options=["Country Stats", "Canadian Stats", "Mexican Stats", "US States", "Distance Stats"], default="US States")
    dx_st_col = next((c for c in filt_df.columns if 'DXer' in c and ('State' in c or 'Prov' in c)), 'DXer_State_Prov')
    dx_co_col = next((c for c in filt_df.columns if 'DXer' in c and 'Country' in c), 'DXer_Country')
    mo_col, yr_col = next((c for c in filt_df.columns if 'Local' in c and 'Month' in c and 'Name' in c), 'Local_Month_Name'), next((c for c in filt_df.columns if 'Local' in c and 'Year' in c), 'Local_Year')
    dt_col, tm_col = next((c for c in filt_df.columns if 'Local' in c and 'Date' in c), 'Local_Date'), next((c for c in filt_df.columns if 'Local' in c and 'Time' in c), 'Local_Time')
    gs = [[0, 'rgb(100,0,0)'], [0.2, 'rgb(183,28,28)'], [0.5, 'rgb(211,47,47)'], [0.8, 'rgb(255,69,0)'], [1, 'rgb(255,165,0)']]

    if gv == "US States":
        if not st.session_state.selected_state: c1, c2 = st.columns([1, 0.001])
        else: c1, c2 = st.columns([3, 1])
        with c1:
            us_d = filt_df[filt_df['Country'] == 'USA']
            counts = us_d.groupby('State').size().reset_index(name='Logs')
            fig = px.choropleth(counts, locations='State', locationmode="USA-states", color='Logs', scope="usa", color_continuous_scale=gs, template="plotly_dark")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor='black'), margin={"r":0,"t":0,"l":0,"b":0}, height=700)
            ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=f"u_{st.session_state.map_key}")
            if ev and ev.get("selection") and ev["selection"].get("points"):
                st.session_state.selected_state = ev["selection"]["points"][0]["location"]; st.rerun()
        if st.session_state.selected_state:
            with c2:
                sel = st.session_state.selected_state
                st.markdown(f"### {sel} INTEL")
                if st.button("❌ CLEAR"): st.session_state.selected_state = None; st.session_state.map_key += 1; st.rerun()
                s_of, s_fr = us_d[us_d['State'] == sel], filt_df[filt_df[dx_st_col] == sel]
                # 1. Hero Station
                if not s_of.empty:
                    top = s_of.groupby(['Frequency', 'Station', 'City']).size().idxmax()
                    st.markdown(f'<div class="stat-header">MOST HEARD</div><div class="stat-val">{top[1]}</div><div class="stat-label">{top[0]} MHz • {top[2]}</div>', unsafe_allow_html=True)
                # 2. Season Window
                st.markdown('<div class="stat-header">SEASON WINDOW</div>', unsafe_allow_html=True)
                of_dates = pd.to_datetime(s_of['Local_Date'])
                st.markdown(f'<div class="stat-label">Start: {get_avg_date(of_dates.groupby(s_of["Local_Year"]).min())} | Peak: {get_avg_date(of_dates)} | End: {get_avg_date(of_dates.groupby(s_of["Local_Year"]).max())}</div>', unsafe_allow_html=True)
                # 3. Path Intel
                st.markdown('<div class="stat-header">TOP PATHS (US/CA)</div>', unsafe_allow_html=True)
                p_in = s_fr[s_fr['Country'].isin(['USA', 'Canada'])].groupby('State').size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                st.dataframe(p_in, column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)

    elif gv == "Canadian Stats":
        ca_d = filt_df[filt_df['Country'] == 'Canada']
        sel_p = st.selectbox("SELECT PROVINCE FOR INTEL", ["NONE"] + sorted(ca_d['State'].dropna().astype(str).unique().tolist()))
        if sel_p == "NONE": c1, c2 = st.columns([1, 0.001])
        else: c1, c2 = st.columns([3, 1])
        with c1:
            layers = [pdk.Layer('HeatmapLayer', data=ca_d[['Mid_Lat', 'Mid_Lon']].dropna(), get_position='[Mid_Lon, Mid_Lat]', radius_pixels=40)]
            st.pydeck_chart(pdk.Deck(map_style='mapbox://styles/mapbox/dark-v10', initial_view_state=pdk.ViewState(latitude=56, longitude=-106, zoom=3), layers=layers, height=700))
        if sel_p != "NONE":
            with c2:
                st.markdown(f"### {sel_p} INTEL")
                s_of, s_fr = ca_d[ca_d['State'] == sel_p], filt_df[filt_df[dx_st_col] == sel_p]
                if not s_of.empty:
                    top = s_of.groupby(['Frequency', 'Station']).size().idxmax()
                    st.markdown(f'<div class="stat-header">MOST HEARD</div><div class="stat-val">{top[1]}</div>', unsafe_allow_html=True)
                st.markdown('<div class="stat-header">SEASON WINDOW</div>', unsafe_allow_html=True)
                of_dates = pd.to_datetime(s_of['Local_Date'])
                st.markdown(f'<div class="stat-label">Start: {get_avg_date(of_dates.groupby(s_of["Local_Year"]).min())} | Peak: {get_avg_date(of_dates)} | End: {get_avg_date(of_dates.groupby(s_of["Local_Year"]).max())}</div>', unsafe_allow_html=True)
                st.markdown('<div class="stat-header">TOP PATHS (US/CA)</div>', unsafe_allow_html=True)
                p_in = s_fr[s_fr['Country'].isin(['USA', 'Canada'])].groupby('State').size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                st.dataframe(p_in, column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)
