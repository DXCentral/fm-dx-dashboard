import streamlit as st
import pandas as pd
import pydeck as pdk
import time
import datetime
import plotly.express as px
import plotly.graph_objects as go
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
if 'selected_tier' not in st.session_state: st.session_state.selected_tier = None
if 'selected_hour' not in st.session_state: st.session_state.selected_hour = None
if 'selected_year' not in st.session_state: st.session_state.selected_year = None
if 'sel_alm_d' not in st.session_state: st.session_state.sel_alm_d = None
if 'sel_alm_y' not in st.session_state: st.session_state.sel_alm_y = None
if 'map_key' not in st.session_state: st.session_state.map_key = 500000
if 'hour_map_key' not in st.session_state: st.session_state.hour_map_key = 600000
if 'year_map_key' not in st.session_state: st.session_state.year_map_key = 700000
if 'dist_map_key' not in st.session_state: st.session_state.dist_map_key = 800000
if 'alm_key' not in st.session_state: st.session_state.alm_key = 900000

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
    .watermark { position: absolute; bottom: 80px; right: 40px; z-index: 1000; pointer-events: none; opacity: 0.4; }
    .stat-header { color: #D32F2F; font-size: 0.95rem; font-weight: 400; margin-bottom: 5px; border-bottom: 1px solid #333; letter-spacing: 1px; padding-top: 15px; }
    .stat-val { font-size: 1.3rem; color: #FFF; font-weight: 300; margin-top: 5px;}
    .stat-label { font-size: 0.75rem; color: #888; text-transform: uppercase; margin-bottom: 8px; line-height: 1.2; }
    .window-box { border-left: 2px solid #D32F2F; padding-left: 10px; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

if st.session_state.full_screen:
    st.markdown("""<style>[data-testid="stSidebar"], [data-testid="stHeader"], .st-emotion-cache-zq5m06 { display: none !important; } .stMain { padding: 0 !important; } .watermark { bottom: 120px !important; } </style>""", unsafe_allow_html=True)

def get_avg_date(dates_series):
    if dates_series.empty: return "N/A"
    try:
        ds = pd.to_datetime(dates_series)
        return (datetime.datetime(2024, 1, 1) + datetime.timedelta(days=int(ds.dt.dayofyear.mean()) - 1)).strftime('%b %d')
    except: return "N/A"

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
        df_logs['join_dx'], df_logs['join_st'] = df_logs[l_dx].str.upper().str.strip(), df_logs[l_st].str.upper().str.strip()
        df_coords['join_dx'], df_coords['join_st'] = df_coords[c_dx].str.upper().str.strip(), df_coords[c_st].str.upper().str.strip()
        df_coords = df_coords.drop_duplicates(subset=['join_dx', 'join_st'])
        df = df_logs.merge(df_coords, on=['join_dx', 'join_st'], how='left', suffixes=('', '_coord'))
        dx_lat, dx_lon = [c for c in df.columns if 'DXer_Latitude' in c or ('DX' in c and 'Lat' in c)][0], [c for c in df.columns if 'DXer_Longitude' in c or ('DX' in c and 'Lon' in c)][0]
        st_lat, st_lon = [c for c in df.columns if 'Station_Lat' in c or ('ST' in c and 'Lat' in c)][0], [c for c in df.columns if 'Station_Long' in c or ('ST' in c and 'Lon' in c)][0]
        for c in [dx_lat, dx_lon, st_lat, st_lon]: df[c] = pd.to_numeric(df[c].astype(str).str.replace('°', '').str.strip(), errors='coerce').astype('float32')
        df['Mid_Lat'], df['Mid_Lon'] = (df[dx_lat] + df[st_lat]) / 2, (df[dx_lon] + df[st_lon]) / 2
        df['Date_Obj'], df['Time_Str'] = pd.to_datetime(df['Local_Date']).dt.date, pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
        dist_col = [c for c in df.columns if 'Distance' in c and 'mi' in c][0]
        dd_col = [c for c in df.columns if 'Distance' in c and 'Distribution' in c][0]
        h_col = next((c for c in df.columns if 'Local' in c and 'Hour' in c), 'Local_Hour')
        y_col = next((c for c in df.columns if 'Local' in c and 'Year' in c), 'Local_Year')
        dom_col = next((c for c in df.columns if 'Local' in c and 'Day' in c and 'Month' in c), 'Local_Day_of_Month')
        m_name_col = next((c for c in df.columns if 'Local' in c and 'Month' in c and 'Name' in c), 'Local_Month_Name')
        return df, df['Date_Obj'].max(), dist_col, dd_col, dx_lat, dx_lon, st_lat, st_lon, l_dx, h_col, y_col, dom_col, m_name_col
    except Exception as e:
        st.error(f"Link Failure: {e}"); return pd.DataFrame(), None, "Distance", "Distance_Distribution", None, None, None, None, "DXer_Location", "Local_Hour", "Local_Year", "Local_Day_of_Month", "Local_Month_Name"

df, last_date, d_col, dd_col, dx_lat, dx_lon, st_lat, st_lon, dx_loc_col, h_col, y_col, dom_col, m_name_col = load_data()
if df.empty: st.stop()

# 3. SIDEBAR NAVIGATION
from streamlit_option_menu import option_menu
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu("DATA MODULES", 
        ["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC ANALYSIS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ"], 
        icons=["house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin"], 
        default_index=0)

# 4. GLOBAL FILTERS
if not st.session_state.full_screen:
    rk = f"v{st.session_state.reset_count}" 
    with st.expander(label="GLOBAL FILTERS", expanded=True):
        r1, r2, r3 = st.columns(5), st.columns(5), st.columns(3)
        f_freq = r1[0].selectbox("Frequency", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key=f"f1_{rk}")
        f_dxer = r1[1].selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().astype(str).tolist()), key=f"f2_{rk}")
        f_stat = r1[2].selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().astype(str).tolist()), key=f"f3_{rk}")
        f_state = r1[3].selectbox("State", ["All"] + sorted(df['State'].dropna().unique().astype(str).tolist()), key=f"f4_{rk}")
        f_ctry = r1[4].selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().astype(str).tolist()), key=f"f5_{rk}")
        f_dxco = r2[0].selectbox("DXer Country", ["All"] + sorted(df['DXer_Country'].dropna().unique().astype(str).tolist()), key=f"f6_{rk}")
        f_dxst = r2[1].selectbox("DXer State", ["All"] + sorted(df['DXer_State_Prov'].dropna().unique().astype(str).tolist()), key=f"f7_{rk}")
        f_month = r2[2].selectbox("Local Month", ["All"] + sorted(df['Local_Month'].dropna().unique().astype(str).tolist()), key=f"f8_{rk}")
        f_year = r2[3].selectbox("Local Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key=f"f9_{rk}")
        f_day = r2[4].selectbox("Month Day", ["All"] + sorted(df['Month_Day'].dropna().unique().astype(str).tolist()), key=f"f10_{rk}")
        f_dist = r3[0].selectbox("Distance Dist.", ["All"] + sorted(df[dd_col].dropna().unique().astype(str).tolist()), key=f"f11_{rk}")
        f_reg = r3[1].selectbox("DXer Region", ["All"] + sorted(df['DXer_Region'].dropna().unique().astype(str).tolist()), key=f"f12_{rk}")
        rds_c = 'RDS Decode?' if 'RDS Decode?' in df.columns else 'RDS Decode'
        f_rds = r3[2].selectbox("RDS Decode?", ["All"] + (sorted(df[rds_c].dropna().unique().astype(str).tolist()) if rds_c in df.columns else []), key=f"f13_{rk}")
        if st.button("RESET ALL FILTERS"): 
            st.session_state.reset_count += 1
            st.rerun()
else:
    f_freq, f_dxer, f_stat, f_state, f_ctry, f_dxco, f_dxst, f_month, f_year, f_day, f_dist, f_reg, f_rds = ["All"] * 13

filt_df = df.copy()
f_map = {'Frequency':f_freq, 'DXer':f_dxer, 'Station':f_stat, 'State':f_state, 'Country':f_ctry, 'DXer_Country':f_dxco, 'DXer_State_Prov':f_dxst, 'Local_Month':f_month, 'Local_Year':f_year, 'Month_Day':f_day, dd_col:f_dist, 'DXer_Region':f_reg, rds_c:f_rds}
for col, val in f_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# 5. DASHBOARD OVERVIEW (LOCKED)
if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m = st.columns(7)
    m[0].metric("Total Logs", f"{len(filt_df):,}")
    m[1].metric("Unique Stations", f"{filt_df['Station'].nunique():,}")
    m[2].metric("US States Heard", filt_df[filt_df['Country'] == 'USA']['State'].nunique())
    m[3].metric("Canadian Provinces", filt_df[filt_df['Country'] == 'Canada']['State'].nunique())
    m[4].metric("Mexican States", filt_df[filt_df['Country'] == 'Mexico']['State'].nunique())
    m[5].metric("Countries Heard", filt_df['Country'].nunique())
    m[6].metric("Furthest Reception", f"{filt_df[d_col].max() if not filt_df.empty else 0:,.0f} mi")
    st.dataframe(filt_df[['Local_Date', 'Local_Time', 'Frequency', 'Station', 'City', 'State', 'Country', 'DXer', d_col]].head(100), use_container_width=True, hide_index=True)

# 6. ES-CLOUD TRACKER (LOCKED)
elif selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    vm = st.pills("MAP LAYER SELECTION", ["Es Cloud Location Heatmap", "Path Line Analysis"], default="Es Cloud Location Heatmap")
    hc1, hc2 = st.columns([1, 2])
    with hc1:
        range_on = st.checkbox("Enable Date Range Mode", value=True) 
        avail_days = sorted(filt_df['Date_Obj'].unique()) 
        if not range_on:
            date_sel = st.date_input("Select Event Date", value=avail_days[-1])
            map_df = filt_df[filt_df['Date_Obj'] == date_sel]
        else:
            date_range = st.date_input("Select Date Range", value=(avail_days[0], avail_days[-1]))
            if len(date_range) == 2:
                map_df = filt_df[(filt_df['Date_Obj'] >= date_range[0]) & (filt_df['Date_Obj'] <= date_range[1])]
            else:
                map_df = filt_df[filt_df['Date_Obj'] == date_range[0]]
        speed_sets = {"1x": {"delay": 0.2, "step": 1}, "2x": {"delay": 0.1, "step": 2}, "3x": {"delay": 0.05, "step": 3}, "4x": {"delay": 0.01, "step": 4}}
        play_speed = st.selectbox("Playback Speed", options=list(speed_sets.keys()), index=1)
        if st.button("📺 VIEW FULL SCREEN" if not st.session_state.full_screen else "❌ EXIT"): 
            st.session_state.full_screen = not st.session_state.full_screen
            st.rerun()
    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        pb1, pb2, pb_txt = st.columns([1, 1, 3])
        if pb1.button("▶ PLAY"): 
            st.session_state.playing = True; st.session_state.p_idx = 0; st.rerun()
        if pb2.button("⏹ STOP"): 
            st.session_state.playing = False; st.rerun()
        current_time = times[st.session_state.p_idx] if st.session_state.playing else hc2.select_slider("Time Control", options=["SHOW ALL"] + times, value="SHOW ALL")
        pb_txt.write(f"## 🕒 CURRENT TIME: {current_time}")
        render_df = map_df if current_time == "SHOW ALL" else map_df[(map_df['Time_Str'] <= current_time) & (map_df['Time_Str'] >= (datetime.datetime.strptime(current_time, '%H:%M') - datetime.timedelta(minutes=60)).strftime('%H:%M'))]
        layers = [pdk.Layer('HeatmapLayer' if vm == "Es Cloud Location Heatmap" else 'LineLayer', data=render_df[['Mid_Lat', 'Mid_Lon']].dropna() if vm == "Es Cloud Location Heatmap" else render_df[[dx_lat, dx_lon, st_lat, st_lon]].dropna(), get_position='[Mid_Lon, Mid_Lat]' if vm == "Es Cloud Location Heatmap" else None, get_source_position=f'[{dx_lon}, {dx_lat}]' if vm != "Es Cloud Location Heatmap" else None, get_target_position=f'[{st_lon}, {st_lat}]' if vm != "Es Cloud Location Heatmap" else None, radius_pixels=65, intensity=2.0, threshold=0.03, color_range=[[183, 28, 28, 60], [211, 47, 47, 150], [244, 67, 54, 200], [255, 235, 238, 230], [255, 255, 255, 255]] if vm == "Es Cloud Location Heatmap" else None, get_width=1, get_color=[211, 47, 47, 45])]
        st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=32, longitude=-95, zoom=3.4), layers=layers, height=1000))
        st.markdown("""<div class="watermark"><img src="https://raw.githubusercontent.com/dxcentral/fm-dx-dashboard/main/SEDAP%20Banner.png" style="width: 250px;"></div>""", unsafe_allow_html=True)
        if st.session_state.playing:
            conf = speed_sets[play_speed]
            if st.session_state.p_idx + conf['step'] < len(times): 
                st.session_state.p_idx += conf['step']; time.sleep(conf['delay']); st.rerun()
            else: 
                st.session_state.playing = False; st.rerun()

# 7. GEOGRAPHIC ANALYSIS (LOCKED)
elif selected_page == "GEOGRAPHIC ANALYSIS":
    st.markdown("<h2 style='text-align: center; color: #D32F2F;'>GEOGRAPHIC ANALYSIS SUITE</h2>", unsafe_allow_html=True)
    gv = st.pills("MODULE", options=["International Stats", "Canadian Stats", "US States", "Distance Stats"], default="US States")
    st.markdown("---")
    geo_df = filt_df.copy(); geo_df = geo_df[geo_df['State'] != 'AM']
    dx_st_col = next((c for c in geo_df.columns if 'DXer' in c and ('State' in c or 'Prov' in c)), 'DXer_State_Prov')
    mo_col, yr_col = next((c for c in geo_df.columns if 'Local' in c and 'Month' in c and 'Name' in c), 'Local_Month_Name'), next((c for c in geo_df.columns if 'Local' in c and 'Year' in c), 'Local_Year')
    gs = [[0, '#640000'], [0.2, '#D32F2F'], [0.4, '#FF4500'], [0.7, '#FFA500'], [1, '#FFFF00']]

    if gv == "Distance Stats":
        col_m, col_f = st.columns([3, 1]) if st.session_state.selected_tier else st.columns([1, 0.001])
        with col_m:
            st.markdown("### DISTANCE DISTRIBUTION HUB"); st.caption("👈 Click on a Distance Distribution category for more details")
            d_counts = geo_df.groupby(dd_col).size().reset_index(name='Logs').dropna().sort_values('Logs', ascending=False)
            if not d_counts.empty:
                fig_hub = px.bar(d_counts, x='Logs', y=dd_col, orientation='h', color='Logs', color_continuous_scale=gs, template="plotly_dark")
                fig_hub.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=400, showlegend=False)
                ev_hub = st.plotly_chart(fig_hub, use_container_width=True, on_select="rerun", key=f"dist_hub_{st.session_state.dist_map_key}")
                if ev_hub and "selection" in ev_hub and ev_hub["selection"].get("points"):
                    nt = ev_hub["selection"]["points"][0]["y"]
                    if st.session_state.selected_tier != nt:
                        st.session_state.selected_tier = nt; st.rerun()
            pulse_data = geo_df.groupby(['Local_Month', dd_col]).size().reset_index(name='Logs')
            st.plotly_chart(px.area(pulse_data, x='Local_Month', y='Logs', color=dd_col, groupnorm='percent', line_shape='spline', template="plotly_dark"), use_container_width=True)
        if st.session_state.selected_tier:
            with col_f:
                tier = st.session_state.selected_tier; st.markdown(f"### {tier.upper()} INTEL")
                if st.button("❌ CLEAR SELECTION", key="cl_dst", use_container_width=True):
                    st.session_state.selected_tier = None; st.session_state.dist_map_key += 1; st.rerun()
                s_of = geo_df[geo_df[dd_col] == tier]
                st.markdown(f'<div class="stat-header">TOTAL LOGS</div><div class="stat-val">{len(s_of):,}</div>', unsafe_allow_html=True)
                st.dataframe(s_of.groupby('DXer').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)
    else:
        if gv == "US States": target, scope, loc_mode, gj_url, gj_key = 'USA', 'usa', 'USA-states', None, None
        elif gv == "Canadian Stats": target, scope, loc_mode, gj_url, gj_key = 'Canada', 'north america', 'geojson-id', "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/canada.geojson", "properties.name"
        elif gv == "International Stats": target, scope, loc_mode, gj_url, gj_key = 'World', 'world', 'country names', None, None
        col_m, col_f = st.columns([3, 1]) if st.session_state.selected_state else st.columns([1, 0.001])
        with col_m:
            if target == 'World':
                pm = {'Azores':'Portugal', 'Canary Islands':'Spain', 'Cayman Island':'Cayman Islands', 'Saint Pierre and Miquelon':'France'}
                geo_df['MapCountry'] = geo_df['Country'].replace(pm)
                counts = geo_df.groupby('MapCountry').size().reset_index(name='Logs')
                fig = px.choropleth(counts, locations='MapCountry', locationmode="country names", color='Logs', color_continuous_scale=gs, template="plotly_dark")
            else:
                c_data = geo_df[geo_df['Country'] == target]
                if target == 'Canada': cam = {'ON':'Ontario','QC':'Quebec','NS':'Nova Scotia','NB':'New Brunswick','MB':'Manitoba','BC':'British Columbia','PE':'Prince Edward Island','SK':'Saskatchewan','AB':'Alberta','NL':'Newfoundland and Labrador','NU':'Nunavut','NT':'Northwest Territories','YT':'Yukon'}
                else: cam = {}
                c_data['MapLoc'] = c_data['State'].map(cam) if target == 'Canada' else c_data['State']
                counts = c_data.groupby('MapLoc').size().reset_index(name='Logs').dropna()
                fig = px.choropleth(counts, geojson=gj_url, locations='MapLoc', featureidkey=gj_key, locationmode=loc_mode, color='Logs', scope=scope, color_continuous_scale=gs, template="plotly_dark")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)'), margin={"r":0,"t":0,"l":0,"b":0}, height=750)
            ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=f"m_{gv}_{st.session_state.map_key}")
            if ev and ev.get("selection") and ev["selection"].get("points"):
                raw = ev["selection"]["points"][0]["location"]
                new_sel = {v: k for k, v in cam.items()}.get(raw, raw) if target == 'Canada' else raw
                if st.session_state.selected_state != new_sel: st.session_state.selected_state = new_sel; st.rerun()
        if st.session_state.selected_state:
            with col_f:
                sel = st.session_state.selected_state; st.markdown(f"### {sel} INTEL")
                if st.button("❌ CLEAR SELECTION", key="cl_map", use_container_width=True):
                    st.session_state.selected_state = None; st.session_state.map_key += 1; st.rerun()
                s_of = geo_df[geo_df['State'] == sel] if target != 'World' else geo_df[geo_df['MapCountry'] == sel]
                st.markdown(f'<div class="stat-header">TOTAL LOGS</div><div class="stat-val">{len(s_of):,}</div>', unsafe_allow_html=True)
                st.dataframe(s_of.groupby('DXer').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)

# 8. TEMPORAL TRENDS
elif selected_page == "TEMPORAL TRENDS":
    st.header("Temporal Intelligence Suite")
    tv = st.pills("MODULE", options=["Yearly Trends", "Monthly Trends", "Hourly Analysis"], default="Hourly Analysis")
    st.info("⚠️ TIME SYNC NOTE: All temporal data is expressed in the Local Time of the DXer’s receiver location.")
    st.markdown("---")
    
    if tv == "Hourly Analysis":
        col_m, col_f = st.columns([3, 1]) if st.session_state.selected_hour is not None else st.columns([1, 0.001])
        with col_m:
            st.markdown("### DIURNAL VOLUME CURVE & HISTORY TIMELINE"); st.caption("👈 Click any bar or point to analyze hourly intelligence")
            h_data = filt_df.groupby(h_col).size().reset_index(name='Logs').sort_values(h_col)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=h_data[h_col], y=h_data['Logs'], name='Log Volume', marker_color='#D32F2F', opacity=0.3, hoverinfo='x+y'))
            fig.add_trace(go.Scatter(x=h_data[h_col], y=h_data['Logs'], mode='markers+lines', name='Hour Mark', marker=dict(size=12, color='#D32F2F', line=dict(width=2, color='white'))))
            fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=600, showlegend=False, xaxis=dict(title="Local Hour (0-23)", tickmode='array', tickvals=list(range(24)), range=[-0.5, 23.5], rangeslider=dict(visible=True)))
            ev_hour = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=f"h_chart_{st.session_state.hour_map_key}")
            if ev_hour and "selection" in ev_hour and ev_hour["selection"].get("points"):
                new_h = int(ev_hour["selection"]["points"][0]["x"])
                if st.session_state.selected_hour != new_h:
                    st.session_state.selected_hour = new_h; st.rerun()
        if st.session_state.selected_hour is not None:
            with col_f:
                h = st.session_state.selected_hour; st.markdown(f"### HOUR {h:02d}:00 INTEL")
                if st.button("❌ CLEAR HOUR", key="cl_hr", use_container_width=True):
                    st.session_state.selected_hour = None; st.session_state.hour_map_key += 1; st.rerun()
                s_h = filt_df[filt_df[h_col].astype(int) == int(h)]
                st.markdown(f'<div class="stat-header">LOG VOLUME</div><div class="stat-val">{len(s_h):,}</div>', unsafe_allow_html=True)
                if not s_h.empty:
                    st.markdown(f'<div class="stat-header">PEAK MONTH</div><div class="stat-val">{s_h[m_name_col].mode().iloc[0].upper()}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-header">MUF REPORTED</div><div class="stat-val">{s_h["Frequency"].max()} MHz</div>', unsafe_allow_html=True)
                    st.markdown('<div class="stat-header">TOP PATHS</div>', unsafe_allow_html=True)
                    paths = s_h.groupby(['DXer_State_Prov', 'State']).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                    paths['Path'] = paths['DXer_State_Prov'] + " ➔ " + paths['State']
                    st.dataframe(paths[['Path', 'L']], hide_index=True)

    elif tv == "Monthly Trends":
        st.markdown("### MONTHLY LOG ALMANAC")
        st.caption("👈 Click on any colored day to view a full tactical report of that day's activity.")
        sel_m_name = st.pills("SELECT MONTH", ["May", "June", "July", "August"], default="June")
        m_df = filt_df[filt_df[m_name_col] == sel_m_name]
        
        if not m_df.empty:
            pivot = m_df.pivot_table(index=dom_col, columns=y_col, values='Station', aggfunc='count').fillna(0).astype(int).reindex(range(1, 32), fill_value=0)
            # Calculations
            pivot['TOTAL LOGS'] = pivot.sum(axis=1)
            pivot['ACTIVE YEARS'] = (pivot.iloc[:, :-1] > 0).sum(axis=1)
            pivot['AVG PER YEAR'] = (pivot['TOTAL LOGS'] / pivot['ACTIVE YEARS']).replace([np.inf, -np.inf], 0).fillna(0).round(0).astype(int)
            f_rows = ['TOTAL LOGS', 'ACTIVE DAYS', 'AVG PER DAY', 'DAYS >= 100', 'DAYS >= 500', 'DAYS >= 1000']
            footer = pd.DataFrame(index=f_rows, columns=pivot.columns).fillna(0)
            for col in pivot.columns:
                if col != 'AVG PER YEAR':
                    d_slice = pivot.loc[1:31, col]
                    footer.at['TOTAL LOGS', col] = int(d_slice.sum())
                    footer.at['ACTIVE DAYS', col] = int((d_slice > 0).sum())
                    footer.at['AVG PER DAY', col] = int(round(d_slice.sum() / (d_slice > 0).sum() if (d_slice > 0).sum() > 0 else 0))
                    footer.at['DAYS >= 100', col] = int((d_slice >= 100).sum())
                    footer.at['DAYS >= 500', col] = int((d_slice >= 500).sum())
                    footer.at['DAYS >= 1000', col] = int((d_slice >= 1000).sum())
            
            full_matrix = pd.concat([pivot, footer])
            core_years = [c for c in pivot.columns if c not in ['TOTAL LOGS', 'ACTIVE YEARS', 'AVG PER YEAR']]
            max_d = pivot[core_years].max().max()

            # --- THE TACTICAL INTERACTIVE GRID (V180) ---
            z_heat = np.where((full_matrix.index.isin(range(1,32))) & (full_matrix.columns.isin(core_years)) & (full_matrix > 0), full_matrix, np.nan)
            
            fig_alm = go.Figure(data=go.Heatmap(
                z=z_heat, x=full_matrix.columns.astype(str), y=full_matrix.index.astype(str),
                colorscale=[[0, '#640000'], [0.2, '#D32F2F'], [0.5, '#FFA500'], [1, '#FFFF00']],
                showscale=False, hoverinfo='none', zmin=1, zmax=max_d
            ))
            # Text layer logic
            for i, r_name in enumerate(full_matrix.index):
                for j, c_name in enumerate(full_matrix.columns):
                    val = full_matrix.iloc[i, j]
                    is_peak = (isinstance(r_name, (int, np.integer)) and 1 <= r_name <= 31 and c_name in core_years and val/max_d > 0.8)
                    t_col = "black" if is_peak else "white"
                    fig_alm.add_annotation(x=full_matrix.columns.astype(str)[j], y=full_matrix.index.astype(str)[i], text=str(int(val)), showarrow=False, font=dict(family="Oswald", color=t_col))
            
            fig_alm.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=1100, margin=dict(l=0,r=0,t=40,b=0), xaxis=dict(side="top"), yaxis=dict(autorange="reversed", tickmode='linear'))

            cm, ci = st.columns([3, 1]) if st.session_state.sel_alm_d else st.columns([1, 0.001])
            with cm:
                ev_alm = st.plotly_chart(fig_alm, use_container_width=True, on_select="rerun", key=f"alm_{st.session_state.alm_key}")
                if ev_alm and "selection" in ev_alm and ev_alm["selection"].get("points"):
                    pt = ev_alm["selection"]["points"][0]
                    try:
                        dv = int(pt["y"])
                        if 1 <= dv <= 31: 
                            st.session_state.sel_alm_d, st.session_state.sel_alm_y = dv, int(pt["x"])
                            st.rerun()
                    except: pass

            if st.session_state.sel_alm_d:
                with ci:
                    d, yr = st.session_state.sel_alm_d, st.session_state.sel_alm_y; st.markdown(f"### 📡 {sel_m_name.upper()} {d}, {yr}")
                    if st.button("❌ CLOSE REPORT", use_container_width=True): 
                        st.session_state.sel_alm_d = None; st.rerun()
                    s_day = m_df[(m_df[dom_col] == d) & (m_df[y_col] == yr)]
                    if not s_day.empty:
                        st.markdown(f'<div class="stat-header">DAILY LOGS</div><div class="stat-val">{len(s_day):,}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-header">MUF REPORTED</div><div class="stat-val">{s_day["Frequency"].max()} MHz</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-header">UNIQUE DXERS</div><div class="stat-val">{s_day["DXer"].nunique()}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-header">WINDOW</div><div class="stat-val">{s_day["Local_Time"].min()} ➔ {s_day["Local_Time"].max()}</div>', unsafe_allow_html=True)
                        st.markdown('<div class="stat-header">TOP ORIGINS</div>', unsafe_allow_html=True); st.dataframe(s_day.groupby('DXer_State_Prov').size().sort_values(ascending=False).head(5), hide_index=True)
                        st.markdown('<div class="stat-header">FURTHEST</div>', unsafe_allow_html=True); f = s_day.sort_values(d_col, ascending=False).iloc[0]; st.markdown(f'<div class="stat-val">{f[d_col]:,.0f} MILES</div><div class="stat-label">{f["Station"]} by {f["DXer"]}</div>', unsafe_allow_html=True)
                        intl = s_day[~s_day['Country'].isin(['USA', 'Canada'])]
                        if not intl.empty: st.markdown('<div class="stat-header">TOP COUNTRIES</div>', unsafe_allow_html=True); st.dataframe(intl.groupby('Country').size().sort_values(ascending=False).head(3), hide_index=True)
                    else: st.warning("No data.")

    elif tv == "Yearly Trends":
        col_m, col_f = st.columns([3, 1]) if st.session_state.selected_year is not None else st.columns([1, 0.001])
        with col_m:
            st.markdown("### SEASONAL VOLUME TRENDS"); y_data = filt_df.groupby(y_col).size().reset_index(name='Logs').sort_values(y_col); fig_y = go.Figure(); fig_y.add_trace(go.Bar(x=y_data[y_col], y=y_data['Logs'], marker_color='#D32F2F', opacity=0.3)); fig_y.add_trace(go.Scatter(x=y_data[y_col], y=y_data['Logs'], mode='markers+lines', marker=dict(size=12, color='#D32F2F', line=dict(width=2, color='white')))); fig_y.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=600, showlegend=False, xaxis=dict(title="Local Year", rangeslider=dict(visible=True))); ev_year = st.plotly_chart(fig_y, use_container_width=True, on_select="rerun", key=f"y_chart_{st.session_state.year_map_key}")
            if ev_year and "selection" in ev_year and ev_year["selection"].get("points"):
                st.session_state.selected_year = int(ev_year["selection"]["points"][0]["x"]); st.rerun()
        if st.session_state.selected_year is not None:
            with col_f:
                yr = st.session_state.selected_year; st.markdown(f"### {yr} SEASON INTEL"); if st.button("❌ CLEAR YEAR", use_container_width=True): st.session_state.selected_year = None; st.session_state.year_map_key += 1; st.rerun()
                s_y = filt_df[filt_df[y_col].astype(int) == int(yr)]; st.markdown(f'<div class="stat-header">SEASON VOLUME</div><div class="stat-val">{len(s_y):,} LOGS</div>', unsafe_allow_html=True)
                if not s_y.empty:
                    st.markdown(f'<div class="stat-header">PEAK MONTH</div><div class="stat-val">{str(s_y[m_name_col].mode().iloc[0]).upper()}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-header">MUF REPORTED</div><div class="stat-val">{s_y["Frequency"].max()} MHz</div>', unsafe_allow_html=True)
                    st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True); f_y = s_y.sort_values(d_col, ascending=False).iloc[0]; st.markdown(f'<div class="stat-val">{f_y[d_col]:,.0f} MILES</div><div class="stat-label">{f_y["Station"]} by {f_y["DXer"]}</div>', unsafe_allow_html=True)
