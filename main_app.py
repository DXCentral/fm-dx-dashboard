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

# EXPLICIT SESSION STATE INITIALIZATION (LOCKED)
if 'full_screen' not in st.session_state: st.session_state.full_screen = False
if 'p_idx' not in st.session_state: st.session_state.p_idx = 0
if 'playing' not in st.session_state: st.session_state.playing = False
if 'reset_count' not in st.session_state: st.session_state.reset_count = 0
if 'selected_state' not in st.session_state: st.session_state.selected_state = None
if 'selected_tier' not in st.session_state: st.session_state.selected_tier = None
if 'selected_hour' not in st.session_state: st.session_state.selected_hour = None
if 'selected_year' not in st.session_state: st.session_state.selected_year = None
if 'selected_intl_country' not in st.session_state: st.session_state.selected_intl_country = None
if 'map_key' not in st.session_state: st.session_state.map_key = 500000
if 'hour_map_key' not in st.session_state: st.session_state.hour_map_key = 600000
if 'year_map_key' not in st.session_state: st.session_state.year_map_key = 700000
if 'dist_map_key' not in st.session_state: st.session_state.dist_map_key = 800000
if 'intl_map_key' not in st.session_state: st.session_state.intl_map_key = 900000
if 'almanac_month' not in st.session_state: st.session_state.almanac_month = "June"

if st.session_state.full_screen:
    st.markdown("""<style>[data-testid="stSidebar"], [data-testid="stHeader"], .st-emotion-cache-zq5m06 { display: none !important; } .stMain { padding: 0 !important; } .watermark { bottom: 120px !important; } </style>""", unsafe_allow_html=True)

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

def get_avg_date(dates_series):
    if dates_series.empty: return "N/A"
    try:
        ds = pd.to_datetime(dates_series)
        return (datetime.datetime(2024, 1, 1) + datetime.timedelta(days=int(ds.dt.dayofyear.mean()) - 1)).strftime('%b %d')
    except: return "N/A"

# 2. DATA LOADING (GEOMETRIC RECOVERY ENGINE)
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
        
        l_dx = next((c for c in df_logs.columns if 'Concatenated' in c and 'DX' in c), 'Concatenated_DXer_Location')
        l_st = next((c for c in df_logs.columns if 'Concatenated' in c and 'Station' in c), 'Concatenated_Station_Location')
        c_dx = next((c for c in df_coords.columns if 'Concatenated' in c and 'DX' in c), 'Concatenated_DXer_Location')
        c_st = next((c for c in df_coords.columns if 'Concatenated' in c and 'Station' in c), 'Concatenated_Station_Location')

        df_logs['join_dx'], df_logs['join_st'] = df_logs[l_dx].str.upper().str.strip(), df_logs[l_st].str.upper().str.strip()
        df_coords[c_dx] = df_coords[c_dx].str.upper().str.strip(); df_coords[c_st] = df_coords[c_st].str.upper().str.strip()

        dx_base = df_coords[[c_dx, 'DXer_Latitude', 'DXer_Longitude']].rename(columns={c_dx: 'Loc', 'DXer_Latitude': 'Lat', 'DXer_Longitude': 'Lon'})
        st_base = df_coords[[c_st, 'Station_Lat', 'Station_Long']].rename(columns={c_st: 'Loc', 'Station_Lat': 'Lat', 'Station_Long': 'Lon'})
        master_map = pd.concat([dx_base, st_base]).dropna().drop_duplicates(subset=['Loc'])

        df = df_logs.merge(master_map, left_on='join_dx', right_on='Loc', how='left').rename(columns={'Lat': 'DX_Lat', 'Lon': 'DX_Lon'}).drop(columns=['Loc'])
        df = df.merge(master_map, left_on='join_st', right_on='Loc', how='left').rename(columns={'Lat': 'ST_Lat', 'Lon': 'ST_Lon'}).drop(columns=['Loc'])

        for c in ['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon', 'Mid_Lat', 'Mid_Long']:
            if c in df.columns: df[c] = pd.to_numeric(df[c].astype(str).str.replace('°', '').str.strip(), errors='coerce').astype('float32')

        m_st = df['ST_Lat'].isna() & df['DX_Lat'].notna() & df['Mid_Lat'].notna()
        df.loc[m_st, 'ST_Lat'] = 2 * df['Mid_Lat'] - df['DX_Lat']
        df.loc[m_st, 'ST_Lon'] = 2 * df['Mid_Long'] - df['DX_Lon']
        
        m_dx = df['DX_Lat'].isna() & df['ST_Lat'].notna() & df['Mid_Lat'].notna()
        df.loc[m_dx, 'DX_Lat'] = 2 * df['Mid_Lat'] - df['ST_Lat']
        df.loc[m_dx, 'DX_Lon'] = 2 * df['Mid_Long'] - df['ST_Lon']

        df['Final_Mid_Lat'] = df['Mid_Lat'].fillna((df['DX_Lat'] + df['ST_Lat']) / 2)
        df['Final_Mid_Lon'] = df['Mid_Long'].fillna((df['DX_Lon'] + df['ST_Lon']) / 2)

        df['Date_Obj'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Time_Str'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
        df['Date_Str'] = pd.to_datetime(df['Local_Date']).dt.strftime('%m/%d/%Y')
        
        dist_col = [c for c in df.columns if 'Distance' in c and 'mi' in c][0]
        dd_col = [c for c in df.columns if 'Distance' in c and 'Distribution' in c][0]
        h_col = next((c for c in df.columns if 'Local' in c and 'Hour' in c), 'Local_Hour')
        y_col = next((c for c in df.columns if 'Local' in c and 'Year' in c), 'Local_Year')
        dom_col = next((c for c in df.columns if 'Local' in c and 'Day' in c and 'Month' in c), 'Local_Day_of_Month')
        m_name_col = next((c for c in df.columns if 'Local' in c and 'Month' in c and 'Name' in c), 'Local_Month_Name')
        dx_st_col = next((c for c in df.columns if 'DXer' in c and ('State' in c or 'Prov' in c)), 'DXer_State_Prov')
        
        return df, df['Date_Obj'].max(), dist_col, dd_col, 'DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon', l_dx, h_col, y_col, dom_col, m_name_col, dx_st_col
    except Exception as e:
        st.error(f"Link Failure: {e}"); return pd.DataFrame(), None, "Distance", "Distribution", None, None, None, None, "DX", "Hour", "Year", "Day", "Month", "DXer_State"

df, last_date, d_col, dd_col, dx_lat_f, dx_lon_f, st_lat_f, st_lon_f, dx_loc_col, h_col, y_col, dom_col, m_name_col, dx_st_col = load_data()
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
        f_dxst = r2[1].selectbox("DXer State/Prov", ["All"] + sorted(df[dx_st_col].dropna().unique().astype(str).tolist()), key=f"f7_{rk}")
        f_month = r2[2].selectbox("Local Month", ["All"] + sorted(df['Local_Month'].dropna().unique().astype(str).tolist()), key=f"f8_{rk}")
        f_year = r2[3].selectbox("Local Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key=f"f9_{rk}")
        f_day = r2[4].selectbox("Month Day", ["All"] + sorted(df['Month_Day'].dropna().unique().astype(str).tolist()), key=f"f10_{rk}")
        f_dist = r3[0].selectbox("Distance Dist.", ["All"] + sorted(df[dd_col].dropna().unique().astype(str).tolist()), key=f"f11_{rk}")
        f_reg = r3[1].selectbox("DXer Region", ["All"] + sorted(df['DXer_Region'].dropna().unique().astype(str).tolist()), key=f"f12_{rk}")
        rds_c = 'RDS Decode?' if 'RDS Decode?' in df.columns else 'RDS Decode'
        f_rds = r3[2].selectbox("RDS Decode?", ["All"] + (sorted(df[rds_c].dropna().unique().astype(str).tolist()) if rds_c in df.columns else []), key=f"f13_{rk}")
        if st.button("RESET ALL FILTERS"): st.session_state.reset_count += 1; st.rerun()
else:
    f_freq, f_dxer, f_stat, f_state, f_ctry, f_dxco, f_dxst, f_month, f_year, f_day, f_dist, f_reg, f_rds = ["All"] * 13

filt_df = df.copy()
f_map = {'Frequency':f_freq, 'DXer':f_dxer, 'Station':f_stat, 'State':f_state, 'Country':f_ctry, 'DXer_Country':f_dxco, dx_st_col:f_dxst, 'Local_Month':f_month, 'Local_Year':f_year, 'Month_Day':f_day, dd_col:f_dist, 'DXer_Region':f_reg, rds_c:f_rds}
for col, val in f_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# 5. MODULES
if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m = st.columns(7)
    m[0].metric("Total Logs", f"{len(filt_df):,}"); m[1].metric("Unique Stations", f"{filt_df['Station'].nunique():,}")
    m[2].metric("US States Heard", filt_df[filt_df['Country'] == 'USA']['State'].nunique())
    m[3].metric("Canadian Provinces", filt_df[filt_df['Country'] == 'Canada']['State'].nunique())
    m[4].metric("Mexican States", filt_df[filt_df['Country'] == 'Mexico']['State'].nunique())
    m[5].metric("Countries Heard", filt_df['Country'].nunique())
    m[6].metric("Furthest Reception", f"{filt_df[d_col].max() if not filt_df.empty else 0:,.0f} mi")
    st.dataframe(filt_df[['Local_Date', 'Local_Time', 'Frequency', 'Station', 'City', 'State', 'Country', 'DXer', d_col]].head(100), use_container_width=True, hide_index=True)

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
            if len(date_range) == 2: map_df = filt_df[(filt_df['Date_Obj'] >= date_range[0]) & (filt_df['Date_Obj'] <= date_range[1])]
            else: map_df = filt_df[filt_df['Date_Obj'] == date_range[0]]
        speed_sets = {"1x": {"delay": 0.2, "step": 1}, "2x": {"delay": 0.1, "step": 2}, "3x": {"delay": 0.05, "step": 3}, "4x": {"delay": 0.01, "step": 4}}
        play_speed = st.selectbox("Playback Speed", options=list(speed_sets.keys()), index=1)
        if st.button("📺 VIEW FULL SCREEN" if not st.session_state.full_screen else "❌ EXIT"): st.session_state.full_screen = not st.session_state.full_screen; st.rerun()

    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        pb1, pb2, pb_txt = st.columns([1, 1, 3])
        if pb1.button("▶ PLAY"): st.session_state.playing = True; st.session_state.p_idx = 0; st.rerun()
        if pb2.button("⏹ STOP"): st.session_state.playing = False; st.rerun()
        current_time = times[st.session_state.p_idx] if st.session_state.playing else hc2.select_slider("Time Control", options=["SHOW ALL"] + times, value="SHOW ALL")
        pb_txt.write(f"## 🕒 CURRENT TIME: {current_time}")
        render_df = map_df if current_time == "SHOW ALL" else map_df[(map_df['Time_Str'] <= current_time) & (map_df['Time_Str'] >= (datetime.datetime.strptime(current_time, '%H:%M') - datetime.timedelta(minutes=60)).strftime('%H:%M'))]
        
        layers = [pdk.Layer('HeatmapLayer' if vm == "Es Cloud Location Heatmap" else 'LineLayer', 
                            data=render_df[['Final_Mid_Lat', 'Final_Mid_Lon']].dropna() if vm == "Es Cloud Location Heatmap" else render_df[[dx_lat_f, dx_lon_f, st_lat_f, st_lon_f]].dropna(), 
                            get_position='[Final_Mid_Lon, Final_Mid_Lat]' if vm == "Es Cloud Location Heatmap" else None, 
                            get_source_position=f'[{dx_lon_f}, {dx_lat_f}]' if vm != "Es Cloud Location Heatmap" else None, 
                            get_target_position=f'[{st_lon_f}, {st_lat_f}]' if vm != "Es Cloud Location Heatmap" else None, 
                            radius_pixels=65, intensity=2.0, threshold=0.03, 
                            color_range=[[183, 28, 28, 60], [211, 47, 47, 150], [244, 67, 54, 200], [255, 235, 238, 230], [255, 255, 255, 255]] if vm == "Es Cloud Location Heatmap" else None, 
                            get_width=1, get_color=[211, 47, 47, 45])]
                            
        # HEIGHT STRETCH: Set to 1800 for cinematic vertical scope
        st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=32, longitude=-95, zoom=3.4), layers=layers, height=1800))
        st.markdown("""<div class="watermark"><img src="https://raw.githubusercontent.com/dxcentral/fm-dx-dashboard/main/SEDAP%20Banner.png" style="width: 250px;"></div>""", unsafe_allow_html=True)
        if st.session_state.playing:
            conf = speed_sets[play_speed]
            if st.session_state.p_idx + conf['step'] < len(times): st.session_state.p_idx += conf['step']; time.sleep(conf['delay']); st.rerun()
            else: st.session_state.playing = False; st.rerun()

elif selected_page == "GEOGRAPHIC ANALYSIS":
    st.markdown("<h2 style='text-align: center; color: #D32F2F;'>GEOGRAPHIC ANALYSIS SUITE</h2>", unsafe_allow_html=True)
    gv = st.pills("MODULE", options=["International Stats", "Canadian Stats", "US States", "Distance Stats"], default="US States")
    st.markdown("---")
    geo_df = filt_df.copy(); geo_df = geo_df[geo_df['State'] != 'AM']
    gs = [[0, '#640000'], [0.25, '#D32F2F'], [0.5, '#FF4500'], [0.75, '#FFA500'], [1, '#FFFF00']]

    if gv == "Distance Stats":
        col_m, col_f = st.columns([3, 1]) if st.session_state.selected_tier else st.columns([1, 0.001])
        with col_m:
            st.markdown("### DISTANCE DISTRIBUTION HUB"); st.caption("👈 Click on a Distance Distribution category for more details and statistics")
            d_counts = geo_df.groupby(dd_col).size().reset_index(name='Logs').dropna().sort_values('Logs', ascending=False)
            if not d_counts.empty:
                fig_hub = px.bar(d_counts, x='Logs', y=dd_col, orientation='h', color='Logs', color_continuous_scale=gs, template="plotly_dark")
                fig_hub.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=400, showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))
                ev_hub = st.plotly_chart(fig_hub, use_container_width=True, on_select="rerun", key=f"dist_hub_{st.session_state.dist_map_key}")
                if ev_hub and "selection" in ev_hub and ev_hub["selection"]["points"]:
                    nt = ev_hub["selection"]["points"][0]["y"]
                    if st.session_state.selected_tier != nt: st.session_state.selected_tier = nt; st.rerun()
            pulse_data = geo_df.groupby(['Local_Month', dd_col]).size().reset_index(name='Logs'); fig_pulse = px.area(pulse_data, x='Local_Month', y='Logs', color=dd_col, groupnorm='percent', line_shape='spline', color_discrete_sequence=['#D32F2F', '#FFA500', '#FFFFFF', '#888888'], template="plotly_dark"); st.plotly_chart(fig_pulse, use_container_width=True)
        if st.session_state.selected_tier:
            with col_f:
                tier = st.session_state.selected_tier; st.markdown(f"### {tier.upper()} INTEL")
                if st.button("❌ CLEAR SELECTION", key="cl_dst", use_container_width=True): st.session_state.selected_tier = None; st.session_state.dist_map_key += 1; st.rerun()
                s_of = geo_df[geo_df[dd_col] == tier]
                st.markdown('<div class="stat-header">TOTAL LOGS IN TIER</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-val">{len(s_of):,}</div>', unsafe_allow_html=True)
                st.markdown('<div class="stat-header">LIKELIHOOD SCORE</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-val">{(s_of["DXer"].nunique() / geo_df["DXer"].nunique()) * 100:.1f}%</div><div class="stat-label">Of DXers have caught this</div>', unsafe_allow_html=True)
                st.markdown('<div class="stat-header">TIER KINGS</div>', unsafe_allow_html=True); st.dataframe(s_of.groupby('DXer').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)
                st.markdown('<div class="stat-header">ORIGIN HOTSPOTS</div>', unsafe_allow_html=True); st.dataframe(s_of.groupby('State').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)
                st.markdown('<div class="stat-header">TOP 5 STATIONS</div>', unsafe_allow_html=True); t5 = s_of.groupby(['Frequency', 'Station']).size().reset_index(name='L').sort_values('L', ascending=False).head(5); t5['M'] = t5['L']; st.dataframe(t5, column_config={"Frequency":"MHz", "L":st.column_config.NumberColumn("Logs", format="%d"), "M":st.column_config.ProgressColumn("", format="%d", min_value=0, max_value=int(t5['L'].max() if not t5.empty else 100))}, hide_index=True)
    else:
        if gv == "US States": target, scope, loc_mode, gj_url, gj_key = 'USA', 'usa', 'USA-states', None, None
        elif gv == "Canadian Stats": target, scope, loc_mode, gj_url, gj_key = 'Canada', 'north america', 'geojson-id', "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/canada.geojson", "properties.name"
        elif gv == "International Stats": target, scope, loc_mode, gj_url, gj_key = 'World', 'world', 'country names', None, None
        col_m, col_f = st.columns([3, 1]) if st.session_state.selected_state else st.columns([1, 0.001])
        with col_m:
            if target == 'World':
                pm = {'Azores':'Portugal', 'Canary Islands':'Spain', 'Cayman Island':'Cayman Islands', 'Saint Pierre and Miquelon':'France'}; geo_df['MapCountry'] = geo_df['Country'].replace(pm); counts = geo_df.groupby('MapCountry').size().reset_index(name='Logs'); fig = px.choropleth(counts, locations='MapCountry', locationmode="country names", color='Logs', color_continuous_scale=gs, template="plotly_dark"); fig.update_geos(projection_type="equirectangular", visible=True, lataxis_range=[-45, 75], lonaxis_range=[-130, 20])
            else:
                c_data = geo_df[geo_df['Country'] == target]; cam = {'ON':'Ontario','QC':'Quebec','NS':'Nova Scotia','NB':'New Brunswick','MB':'Manitoba','BC':'British Columbia','PE':'Prince Edward Island','SK':'Saskatchewan','AB':'Alberta','NL':'Newfoundland and Labrador','NU':'Nunavut','NT':'Northwest Territories','YT':'Yukon'} if target == 'Canada' else {}; c_data['MapLoc'] = c_data['State'].map(cam) if target == 'Canada' else c_data['State']; counts = c_data.groupby('MapLoc').size().reset_index(name='Logs').dropna(); fig = px.choropleth(counts, geojson=gj_url, locations='MapLoc', featureidkey=gj_key, locationmode=loc_mode, color='Logs', scope=scope, color_continuous_scale=gs, template="plotly_dark")
                if target != 'USA': fig.update_geos(fitbounds="locations", visible=True, showsubunits=True, subunitcolor="#333")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor='black'), margin={"r":0,"t":0,"l":0,"b":0}, height=750); ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=f"m_{gv}_{st.session_state.map_key}")
            if ev and ev.get("selection") and ev["selection"].get("points"):
                raw = ev["selection"]["points"][0]["location"]; new_sel = raw
                if target == 'Canada': inv = {v: k for k, v in cam.items()}; new_sel = inv.get(raw, raw)
                if st.session_state.selected_state != new_sel: st.session_state.selected_state = new_sel; st.rerun()
        if st.session_state.selected_state:
            with col_f:
                sel = st.session_state.selected_state; st.markdown(f"### {sel} INTEL")
                if st.button("❌ CLEAR SELECTION", key="cl_map", use_container_width=True): st.session_state.selected_state = None; st.session_state.map_key += 1; st.rerun()
                if target == 'World': s_of, s_fr = geo_df[geo_df['MapCountry'] == sel], geo_df[geo_df['DXer_Country'] == sel]
                else: s_of, s_fr = geo_df[geo_df['Country'] == target][geo_df['State'] == sel], geo_df[geo_df[dx_st_col] == sel]
                st.markdown('<div class="stat-header">TOTAL LOGS IN DATASET</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-val">{len(s_of):,}</div>', unsafe_allow_html=True)
                if not s_of.empty:
                    top_st = s_of.groupby(['Frequency', 'Station', 'City']).size().idxmax()
                    st.markdown('<div class="stat-header">MOST HEARD STATION</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-val">{top_st[1]}</div><div class="stat-label">{top_st[0]} MHz • {top_st[2]} • {s_of.groupby(["Frequency", "Station", "City"]).size().max()} Logs</div>', unsafe_allow_html=True)
                    st.markdown('<div class="stat-header">PEAK SEASONALITY</div>', unsafe_allow_html=True); m_c, y_c = s_of[m_name_col].value_counts(), s_of[y_col].value_counts()
                    st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Month</div><div class="stat-val" style="margin-top:0px;">{str(m_c.idxmax()).upper()} ({m_c.max()})</div></div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Year</div><div class="stat-val" style="margin-top:0px;">{y_c.idxmax()} ({y_c.max()})</div></div>', unsafe_allow_html=True)
                    st.markdown('<div class="window-box">', unsafe_allow_html=True); st.markdown('<div class="stat-label" style="color:#D32F2F">Season Window - Stations From Region</div>', unsafe_allow_html=True)
                    od = pd.to_datetime(s_of['Local_Date']); st.markdown(f'<div class="stat-label">Start: {get_avg_date(od.groupby(s_of[y_col]).min())} | Peak: {get_avg_date(od)} | End: {get_avg_date(od.groupby(s_of[y_col]).max())}</div>', unsafe_allow_html=True)
                    st.markdown('<div class="stat-label" style="color:#D32F2F">Season Window - DXers In Region</div>', unsafe_allow_html=True)
                    fd = pd.to_datetime(s_fr['Local_Date']); st.markdown(f'<div class="stat-label">Start: {get_avg_date(fd.groupby(s_fr[y_col]).min())} | Peak: {get_avg_date(fd)} | End: {get_avg_date(fd.groupby(s_fr[y_col]).max())}</div>', unsafe_allow_html=True); st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True); f = s_of.sort_values(d_col, ascending=False).iloc[0]; st.markdown(f'<div class="stat-val">{f[d_col]:,.0f} MILES</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-label">{f["Frequency"]} - {f["Station"]} by {f["DXer"]}, {f[dx_loc_col]} on {f["Date_Str"]} at {f["Local_Time"]}</div>', unsafe_allow_html=True)
                st.markdown('<div class="stat-header">LOCAL DXER ACTIVITY</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-val">{s_fr["DXer"].nunique()} UNIQUE DXERS</div>', unsafe_allow_html=True); st.markdown('<div class="stat-header">TOP RECEPTION PATHS</div>', unsafe_allow_html=True); st.dataframe(s_fr.groupby('State' if target != 'World' else 'Country').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True); st.markdown('<div class="stat-header">TOP TRANSMISSION PATHS</div>', unsafe_allow_html=True); st.dataframe(s_of.groupby(dx_st_col if target != 'World' else 'DXer_Country').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True); st.markdown('<div class="stat-header">TOP 5 STATIONS</div>', unsafe_allow_html=True); t5 = s_of.groupby(['Frequency', 'Station']).size().reset_index(name='L').sort_values('L', ascending=False).head(5); t5['M'] = t5['L']; st.dataframe(t5, column_config={"Frequency":"MHz", "L":st.column_config.NumberColumn("Logs", format="%d"), "M":st.column_config.ProgressColumn("", format="%d", min_value=0, max_value=int(t5['L'].max() if not t5.empty else 100))}, hide_index=True)

elif selected_page == "TEMPORAL TRENDS":
    st.header("Temporal Intelligence Suite")
    tv = st.pills("MODULE", options=["Yearly Trends", "Monthly Almanac", "Hourly Analysis"], default="Hourly Analysis")
    st.info("⚠️ TIME SYNC NOTE: All temporal data is expressed in the Local Time of the DXer’s receiver location.")
    st.markdown("---")
    
    if tv == "Hourly Analysis":
        col_m, col_f = st.columns([3, 1]) if st.session_state.selected_hour is not None else st.columns([1, 0.001])
        with col_m:
            st.markdown("### DIURNAL VOLUME CURVE & HISTORY TIMELINE"); st.caption("👈 CLICK ANY BAR OR POINT TO ANALYZE HOURLY INTELLIGENCE")
            h_data = filt_df.groupby(h_col).size().reset_index(name='Logs').sort_values(h_col)
            fig_h = go.Figure(); fig_h.add_trace(go.Bar(x=h_data[h_col], y=h_data['Logs'], name='Log Volume', marker_color='#D32F2F', opacity=0.3, hoverinfo='x+y')); fig_h.add_trace(go.Scatter(x=h_data[h_col], y=h_data['Logs'], mode='markers+lines', name='Hour Mark', marker=dict(size=12, color='#D32F2F', line=dict(width=2, color='white')), line=dict(width=1, color='#444'))); fig_h.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=600, showlegend=False, xaxis=dict(title="Local Hour (0-23)", tickmode='array', tickvals=list(range(24)), range=[-0.5, 23.5], rangeslider=dict(visible=True), type='linear'), yaxis=dict(title="Total Log Volume", showgrid=False))
            ev_hour = st.plotly_chart(fig_h, use_container_width=True, on_select="rerun", key=f"h_chart_{st.session_state.hour_map_key}")
            if ev_hour and "selection" in ev_hour and ev_hour["selection"]["points"]:
                new_h = int(ev_hour["selection"]["points"][0]["x"])
                if st.session_state.selected_hour != new_h: st.session_state.selected_hour = new_h; st.rerun()
        if st.session_state.selected_hour is not None:
            with col_f:
                h = st.session_state.selected_hour; st.markdown(f"### HOUR {h:02d}:00 INTEL")
                if st.button("❌ CLEAR HOUR", key="cl_hr", use_container_width=True): st.session_state.selected_hour = None; st.session_state.hour_map_key += 1; st.rerun()
                s_h = filt_df[filt_df[h_col].astype(int) == int(h)]
                st.markdown('<div class="stat-header">HOUR MISSION SUMMARY</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-val">{len(s_h):,} LOGS</div><div class="stat-label">{(len(s_h)/len(filt_df))*100:.1f}% of Global Volume</div>', unsafe_allow_html=True)
                if not s_h.empty:
                    st.markdown('<div class="stat-header">PEAK SEASONALITY</div>', unsafe_allow_html=True); m_h, y_h = s_h[m_name_col].value_counts(), s_h[y_col].value_counts()
                    st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Month</div><div class="stat-val" style="margin-top:0px;">{str(m_h.idxmax()).upper()} ({m_h.max()})</div></div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Year</div><div class="stat-val" style="margin-top:0px;">{y_h.idxmax()} ({y_h.max()})</div></div>', unsafe_allow_html=True)
                    st.markdown('<div class="stat-header">LOCATION DOMINANCE</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-val">{s_h[dx_loc_col].mode().iloc[0]}</div><div class="stat-label">Most Active DXer Location</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-val">{s_h["State"].mode().iloc[0]}</div><div class="stat-label">Most Active Station State</div>', unsafe_allow_html=True)
                    st.markdown('<div class="stat-header">TOP 5 PATHS (DXER ➔ STATION STATE/PROV)</div>', unsafe_allow_html=True); paths = s_h.groupby([dx_st_col, 'State']).size().reset_index(name='L').sort_values('L', ascending=False).head(5); paths['Path'] = paths[dx_st_col].astype(str) + " ➔ " + paths['State'].astype(str); st.dataframe(paths[['Path', 'L']], column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)
                    st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True); f = s_h.sort_values(d_col, ascending=False).iloc[0]; st.markdown(f'<div class="stat-val">{f[d_col]:,.0f} MILES</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-label">{f["Frequency"]} - {f["Station"]} by {f["DXer"]}, {f[dx_loc_col]} on {f["Date_Str"]} at {f["Local_Time"]}</div>', unsafe_allow_html=True)

    elif tv == "Monthly Almanac":
        st.markdown("### MONTHLY LOG ALMANAC"); st.caption("Select a month to view seasonal density. Pick a date below to view tactical reports.")
        sel_m_name = st.pills("SELECT MONTH", ["May", "June", "July", "August"], default=st.session_state.almanac_month)
        st.session_state.almanac_month = sel_m_name
        avail_m_df = filt_df[filt_df[m_name_col] == sel_m_name]
        if not avail_m_df.empty:
            st.markdown("#### 📅 TACTICAL DATE FORENSICS")
            sel_date = st.date_input("SELECT DATE FOR INTEL REPORT", value=None, min_value=avail_m_df['Date_Obj'].min(), max_value=avail_m_df['Date_Obj'].max())
            cm, ci = st.columns([3, 1]) if sel_date else st.columns([1, 0.001])
            with cm:
                pivot = avail_m_df.pivot_table(index=dom_col, columns=y_col, values='Station', aggfunc='count').fillna(0).astype(int).reindex(range(1, 32), fill_value=0)
                pivot['TOTAL LOGS'] = pivot.sum(axis=1); pivot['ACTIVE YEARS'] = (pivot.drop(columns=['TOTAL LOGS']) > 0).sum(axis=1); pivot['AVG/YR'] = (pivot['TOTAL LOGS'] / pivot['ACTIVE YEARS']).replace([np.inf, -np.inf], 0).fillna(0).round(0).astype(int)
                f_rows = ['TOTAL LOGS', 'ACTIVE DAYS', 'AVG/DAY', 'DAYS >= 100', 'DAYS >= 500']; footer = pd.DataFrame(index=f_rows, columns=pivot.columns).fillna(0)
                for col in pivot.columns:
                    d_slice = pivot.loc[1:31, col]; active_count = (d_slice > 0).sum()
                    footer.at['TOTAL LOGS', col] = int(d_slice.sum()); footer.at['ACTIVE DAYS', col] = int(active_count); footer.at['AVG/DAY', col] = int(round(d_slice.sum() / active_count if active_count > 0 else 0))
                    footer.at['DAYS >= 100', col] = int((d_slice >= 100).sum()); footer.at['DAYS >= 500', col] = int((d_slice >= 500).sum())
                final_pivot = pd.concat([pivot, footer]).reset_index().rename(columns={'index': 'DAY/METRIC'})
                def style_almanac(df):
                    styles = pd.DataFrame('', index=df.index, columns=df.columns); core_y = [c for c in df.columns if str(c).isdigit()]; core_matrix = df.iloc[:31].get(core_y, pd.DataFrame()); max_v = core_matrix.max().max() if not core_matrix.empty else 100
                    for r_idx in df.index:
                        label = df.at[r_idx, 'DAY/METRIC']
                        for c in df.columns:
                            val = df.at[r_idx, c]
                            if isinstance(label, int) and 1 <= label <= 31 and c in core_y:
                                if val > 0:
                                    rel = val / max_v; bg = '#FFFF00' if rel > 0.8 else ('#FFA500' if rel > 0.5 else ('#D32F2F' if rel > 0.2 else '#640000'))
                                    fg = 'black' if rel > 0.5 else 'white'; styles.at[r_idx, c] = f'background-color: {bg}; color: {fg};'
                            else: styles.at[r_idx, c] = 'background-color: #000000; color: #FFFFFF; font-weight: bold;'
                    return styles
                st.dataframe(final_pivot.style.apply(style_almanac, axis=None), use_container_width=True, height=1250, hide_index=True)
            if sel_date:
                with ci:
                    st.markdown(f"### 📡 TACTICAL REPORT: {sel_date.strftime('%b %d, %Y')}"); s_day = avail_m_df[avail_m_df['Date_Obj'] == sel_date]
                    if not s_day.empty:
                        st.metric("Total Logs", f"{len(s_day):,}"); st.metric("MUF Recorded", f"{s_day['Frequency'].max()} MHz"); st.metric("Unique DXers", s_day['DXer'].nunique())
                        st.markdown('<div class="stat-header">LOCATION DOMINANCE</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-val">{s_day[dx_loc_col].mode().iloc[0]}</div><div class="stat-label">Most Active DXer Location</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-val">{s_day["State"].mode().iloc[0]}</div><div class="stat-label">Most Active Station State</div>', unsafe_allow_html=True)
                        st.markdown('<div class="stat-header">TOP 5 PATHS (DXER ➔ STATION STATE/PROV)</div>', unsafe_allow_html=True); m_paths = s_day.groupby([dx_st_col, 'State']).size().reset_index(name='L').sort_values('L', ascending=False).head(5); m_paths['Path'] = m_paths[dx_st_col].astype(str) + " ➔ " + m_paths['State'].astype(str); st.dataframe(m_paths[['Path', 'L']], hide_index=True)
                        st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True); f = s_day.sort_values(d_col, ascending=False).iloc[0]; st.markdown(f'<div class="stat-val">{f[d_col]:,.0f} MILES</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-label">{f["Frequency"]} - {f["Station"]} by {f["DXer"]}, {f[dx_loc_col]} on {f["Date_Str"]} at {f["Local_Time"]}</div>', unsafe_allow_html=True)
                        intl = s_day[~s_day['Country'].isin(['USA', 'Canada'])]
                        if not intl.empty: st.markdown('<div class="stat-header">TOP INTERNATIONAL COUNTRIES</div>', unsafe_allow_html=True); st.dataframe(intl.groupby('Country').size().reset_index(name='L').sort_values('L', ascending=False).head(3), hide_index=True)
                    else: st.warning("No signal intelligence for selected date.")
        st.markdown("#### 📊 SEASONAL DENSITY MATRIX"); st.caption("👈 Percentage of days in each month/year with at least one reported Es log. Red/Yellow intensity indicates high density.")
        m_days = {"May": 31, "June": 30, "July": 31, "August": 31}
        density_data = filt_df[filt_df[m_name_col].isin(list(m_days.keys()))]
        if not density_data.empty:
            years_v = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
            density_pivot = density_data.groupby([m_name_col, y_col])['Date_Obj'].nunique().unstack(fill_value=0).astype(float)
            density_pivot = density_pivot.reindex(columns=years_v, fill_value=0)
            for m in m_days:
                if m in density_pivot.index: density_pivot.loc[m] = (density_pivot.loc[m] / m_days[m]) * 100
            density_pivot.loc['SEASON TOTAL'] = (density_data.groupby(y_col)['Date_Obj'].nunique() / 123) * 100
            density_pivot['AVERAGES'] = density_pivot.mean(axis=1); density_pivot.columns = [str(c) for c in density_pivot.columns]
            dens_text = density_pivot.map(lambda x: f"{x:.1f}%")
            fig_dens = px.imshow(density_pivot, text_auto=False, color_continuous_scale='YlOrRd_r', labels=dict(color="% Density"), template="plotly_dark")
            fig_dens.update_traces(text=dens_text.values, texttemplate="%{text}"); fig_dens.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', coloraxis_showscale=False)
            st.plotly_chart(fig_dens, use_container_width=True)
        st.markdown("#### 🌎 INTERNATIONAL SEASONAL FLOW"); st.caption("👈 Click anywhere on a country's horizontal bar for tactical intelligence.")
        intl_raw = filt_df[~filt_df['Country'].isin(['USA', 'Canada'])].copy()
        if not intl_raw.empty:
            intl_raw['Country'] = intl_raw['Country'].astype(str); intl_raw[m_name_col] = intl_raw[m_name_col].astype(str)
            intl_flow = intl_raw.groupby(['Country', m_name_col]).size().reset_index(name='Logs'); intl_flow = intl_flow.sort_values('Country', ascending=False)
            col_intl_m, col_intl_f = st.columns([3, 1]) if st.session_state.selected_intl_country else st.columns([1, 0.001])
            with col_intl_m:
                fig_intl = px.bar(intl_flow, x='Logs', y='Country', color=m_name_col, orientation='h', template='plotly_dark', color_discrete_sequence=['#640000', '#D32F2F', '#FFA500', '#FFFF00'])
                fig_intl.update_layout(barnorm='percent', height=500, barmode='stack', clickmode='event+select', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_title="% Monthly Distribution")
                ev_intl = st.plotly_chart(fig_intl, use_container_width=True, on_select="rerun", key=f"intl_bar_{st.session_state.intl_map_key}")
                if ev_intl and ev_intl.get("selection") and ev_intl["selection"].get("points"):
                    new_intl = ev_intl["selection"]["points"][0]["y"]
                    if st.session_state.selected_intl_country != new_intl: st.session_state.selected_intl_country = new_intl; st.rerun()
            if st.session_state.selected_intl_country:
                with col_intl_f:
                    c_sel = st.session_state.selected_intl_country; st.markdown(f"### {c_sel.upper()} INTEL")
                    if st.button("❌ CLEAR COUNTRY", use_container_width=True): st.session_state.selected_intl_country = None; st.session_state.intl_map_key += 1; st.rerun()
                    c_df = intl_raw[intl_raw['Country'] == c_sel]
                    st.markdown('<div class="stat-header">MONTHLY DISTRIBUTION</div>', unsafe_allow_html=True)
                    c_grp = c_df.groupby(m_name_col).size().reset_index(name='Logs'); c_grp['% of Total'] = (c_grp['Logs'] / len(c_df)) * 100; c_grp['M'] = c_grp['% of Total']
                    st.dataframe(c_grp, column_config={m_name_col: "Month", "Logs": "Total Logs", "% of Total": st.column_config.NumberColumn("%", format="%.1f%%"), "M": st.column_config.ProgressColumn("", format="", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)
                    st.markdown(f'<div class="stat-header">TOP 5 HUBS HEARING {c_sel.upper()}</div>', unsafe_allow_html=True)
                    intl_paths = c_df.groupby([dx_st_col]).size().reset_index(name='L').sort_values('L', ascending=False).head(5); intl_paths['M'] = intl_paths['L']
                    st.dataframe(intl_paths, column_config={dx_st_col: "Origin State/Prov", "L": "Logs", "M": st.column_config.ProgressColumn("", format="", min_value=0, max_value=int(intl_paths['L'].max() if not intl_paths.empty else 10))}, hide_index=True, use_container_width=True)
                    st.markdown('<div class="stat-header">PEAK SIGNAL INTEL</div>', unsafe_allow_html=True); muf_row = c_df.sort_values('Frequency', ascending=False).iloc[0]; st.markdown(f'<div class="stat-val">{muf_row["Frequency"]} MHz</div><div class="stat-label">MAX MUF: {muf_row["Station"]} caught by {muf_row["DXer"]} ({muf_row[dx_loc_col]}) on {muf_row["Date_Str"]} at {muf_row["Local_Time"]} • {muf_row[d_col]:,.0f} MI</div>', unsafe_allow_html=True)
                    dist_row = c_df.sort_values(d_col, ascending=False).iloc[0]; st.markdown(f'<div class="stat-val">{dist_row[d_col]:,.0f} MILES</div><div class="stat-label">MAX DISTANCE: {dist_row["Frequency"]} MHz - {dist_row["Station"]} caught by {dist_row["DXer"]} ({dist_row[dx_loc_col]}) on {dist_row["Date_Str"]} at {dist_row["Local_Time"]}</div>', unsafe_allow_html=True)

    elif tv == "Yearly Trends":
        st.markdown("### SEASONAL VOLUME TRENDS"); y_data = filt_df.groupby(y_col).size().reset_index(name='Logs').sort_values(y_col)
        fig_y = go.Figure(); fig_y.add_trace(go.Bar(x=y_data[y_col], y=y_data['Logs'], marker_color='#D32F2F', opacity=0.3))
        fig_y.add_trace(go.Scatter(x=y_data[y_col], y=y_data['Logs'], mode='markers+lines', marker=dict(size=12, color='#D32F2F', line=dict(width=2, color='white'))))
        fig_y.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=600, showlegend=False, xaxis=dict(title="Local Year", rangeslider=dict(visible=True)))
        ev_year = st.plotly_chart(fig_y, use_container_width=True, on_select="rerun", key=f"y_chart_{st.session_state.year_map_key}")
        if ev_year and "selection" in ev_year and ev_year["selection"]["points"]: st.session_state.selected_year = int(ev_year["selection"]["points"][0]["x"]); st.rerun()
        if st.session_state.selected_year is not None:
            yr = st.session_state.selected_year; st.markdown(f"### {yr} SEASON INTEL")
            if st.button("❌ CLEAR YEAR", use_container_width=True): st.session_state.selected_year = None; st.session_state.year_map_key += 1; st.rerun()
            s_y = filt_df[filt_df[y_col].astype(int) == int(yr)]; st.markdown(f'<div class="stat-header">SEASON VOLUME</div><div class="stat-val">{len(s_y):,} LOGS</div>', unsafe_allow_html=True)
            if not s_y.empty:
                m_y = s_y[m_name_col].value_counts()
                st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Month</div><div class="stat-val" style="margin-top:0px;">{str(m_y.idxmax()).upper()} ({m_y.max()})</div></div>', unsafe_allow_html=True)
                f_y = s_y.sort_values(d_col, ascending=False).iloc[0]; st.markdown(f'<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True); st.markdown(f'<div class="stat-val">{f_y[d_col]:,.0f} MILES</div><div class="stat-label">{f_y["Station"]} by {f_y["DXer"]}</div>', unsafe_allow_html=True)

elif selected_page == "FREQUENCY & MUF": st.header("Frequency & MUF Analysis Dashboard"); st.info("Module under construction for Phase 2 Deployment.")
elif selected_page == "STATION & RDS IQ": st.header("Station & RDS Intelligence Hub"); st.info("Module under construction for Phase 2 Deployment.")
