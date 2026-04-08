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
if 'map_key' not in st.session_state: st.session_state.map_key = 1500

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
    day_of_year = dates_series.dt.dayofyear
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
        for c in [dx_lat, dx_lon, st_lat, st_lon]:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace('°', '').str.strip(), errors='coerce').astype('float32')
        df['Mid_Lat'] = (df[dx_lat] + df[st_lat]) / 2
        df['Mid_Lon'] = (df[dx_lon] + df[st_lon]) / 2
        df['Date_Obj'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Time_Str'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
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
    selected_page = option_menu(menu_title="DATA MODULES", 
        options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC ANALYSIS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "STATION & RDS IQ", "RECEPTION DYNAMICS"], 
        icons=["house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "broadcast-pin", "diagram-3"], 
        default_index=0)

# 4. GLOBAL FILTERS
if not st.session_state.full_screen:
    st.image("SEDAP Banner.png", width=600)
    rk = f"v{st.session_state.reset_count}" 
    with st.expander(label="GLOBAL FILTERS", expanded=True):
        r1 = st.columns(5)
        f_freq = r1[0].selectbox("Frequency", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key=f"freq_{rk}")
        f_dxer = r1[1].selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().astype(str).tolist()), key=f"dxer_{rk}")
        f_station = r1[2].selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().astype(str).tolist()), key=f"stat_{rk}")
        f_state = r1[3].selectbox("State", ["All"] + sorted(df['State'].dropna().unique().astype(str).tolist()), key=f"stte_{rk}")
        f_country = r1[4].selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().astype(str).tolist()), key=f"ctry_{rk}")
        r2 = st.columns(5)
        f_dxco = r2[0].selectbox("DXer Country", ["All"] + sorted(df['DXer_Country'].dropna().unique().astype(str).tolist()), key=f"dxco_{rk}")
        f_dxst = r2[1].selectbox("DXer State", ["All"] + sorted(df['DXer_State_Prov'].dropna().unique().astype(str).tolist()), key=f"dxst_{rk}")
        f_month = r2[2].selectbox("Local Month", ["All"] + sorted(df['Local_Month'].dropna().unique().astype(str).tolist()), key=f"moth_{rk}")
        f_year = r2[3].selectbox("Local Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key=f"year_{rk}")
        f_day = r2[4].selectbox("Month Day", ["All"] + sorted(df['Month_Day'].dropna().unique().astype(str).tolist()), key=f"day_{rk}")
        r3 = st.columns(3)
        f_dist = r3[0].selectbox("Distance Dist.", ["All"] + sorted(df['Distance_Distribution'].dropna().unique().astype(str).tolist()), key=f"dist_{rk}")
        f_reg = r3[1].selectbox("DXer Region", ["All"] + sorted(df['DXer_Region'].dropna().unique().astype(str).tolist()), key=f"regn_{rk}")
        rds_c = 'RDS Decode?' if 'RDS Decode?' in df.columns else 'RDS Decode'
        f_rds = r3[2].selectbox("RDS Decode?", ["All"] + (sorted(df[rds_c].dropna().unique().astype(str).tolist()) if rds_c in df.columns else []), key=f"rds_{rk}")
        if st.button("RESET ALL FILTERS", key="global_reset"): st.session_state.reset_count += 1; st.rerun()
else:
    f_freq, f_dxer, f_station, f_state, f_country, f_dxco, f_dxst, f_month, f_year, f_day, f_dist, f_reg, f_rds = ["All"] * 13

filt_df = df.copy()
f_map = {'Frequency':f_freq, 'DXer':f_dxer, 'Station':f_station, 'State':f_state, 'Country':f_country, 'DXer_Country':f_dxco, 'DXer_State_Prov':f_dxst, 'Local_Month':f_month, 'Local_Year':f_year, 'Month_Day':f_day, 'Distance_Distribution':f_dist, 'DXer_Region':f_reg, rds_c:f_rds}
for col, val in f_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# 5. MODULE 1: DASHBOARD OVERVIEW
if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Total Logs", f"{len(filt_df):,}")
    m2.metric("Unique Stations", f"{filt_df['Station'].nunique():,}")
    m3.metric("US States Heard", filt_df[filt_df['Country'] == 'USA']['State'].nunique())
    m4.metric("CA Provinces", filt_df[filt_df['Country'] == 'Canada']['State'].nunique())
    m5.metric("MX States", filt_df[filt_df['Country'] == 'Mexico']['State'].nunique())
    m6.metric("Countries Heard", filt_df['Country'].nunique())
    m7.metric("Max Distance", f"{filt_df[d_col].max() if not filt_df.empty else 0:,.0f} mi")
    
    st.markdown("### Recent Log Stream")
    table_cols = ['Local_Date', 'Local_Time', 'Frequency', 'Station', 'City', 'State', 'Country', 'DXer', d_col]
    st.dataframe(filt_df[table_cols].head(100), use_container_width=True, hide_index=True, column_config={
        "Local_Date": "Date", "Local_Time": "Time", "Frequency": "MHz", 
        d_col: st.column_config.ProgressColumn("Distance (mi)", format="%d", min_value=0, max_value=int(filt_df[d_col].max() if not filt_df.empty else 3000))
    })

# 6. MODULE 2: ES-CLOUD TRACKER
elif selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    view_mode = st.pills("MAP LAYER SELECTION", ["Es Cloud Location Heatmap", "Path Line Analysis"], default="Es Cloud Location Heatmap")
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
        speed_sets = {"1x": {"delay": 0.2, "step": 1}, "2x": {"delay": 0.1, "step": 2}, "4x": {"delay": 0.01, "step": 4}}
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
        layers = []
        if view_mode == "Es Cloud Location Heatmap":
            layers.append(pdk.Layer('HeatmapLayer', data=render_df[['Mid_Lat', 'Mid_Lon']].dropna(), get_position='[Mid_Lon, Mid_Lat]', radius_pixels=65, intensity=2.0, threshold=0.03, color_range=[[183, 28, 28, 60], [211, 47, 47, 150], [244, 67, 54, 200], [255, 235, 238, 230], [255, 255, 255, 255]]))
        else:
            layers.append(pdk.Layer('LineLayer', data=render_df[[dx_lat, dx_lon, st_lat, st_lon]].dropna(), get_source_position=f'[{dx_lon}, {dx_lat}]', get_target_position=f'[{st_lon}, {st_lat}]', get_width=1, get_color=[211, 47, 47, 45]))
        st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=32, longitude=-95, zoom=3.4), layers=layers, height=1000))
        st.markdown("""<div class="watermark"><img src="https://raw.githubusercontent.com/dxcentral/fm-dx-dashboard/main/SEDAP%20Banner.png" style="width: 250px;"></div>""", unsafe_allow_html=True)
        if st.session_state.playing:
            conf = speed_sets[play_speed]
            if st.session_state.p_idx + conf['step'] < len(times): st.session_state.p_idx += conf['step']; time.sleep(conf['delay']); st.rerun()
            else: st.session_state.playing = False; st.rerun()

# 7. MODULE 3: GEOGRAPHIC ANALYSIS
elif selected_page == "GEOGRAPHIC ANALYSIS":
    st.markdown("<h2 style='text-align: center; color: #D32F2F;'>GEOGRAPHIC ANALYSIS SUITE</h2>", unsafe_allow_html=True)
    geo_view = st.pills("MODULE", options=["Country Stats", "Canadian Stats", "Mexican Stats", "US States", "Distance Stats"], default="US States")
    st.markdown("---")
    
    if geo_view == "US States":
        dx_st_col = next((c for c in filt_df.columns if 'DXer' in c and ('State' in c or 'Prov' in c)), 'DXer_State_Prov')
        dx_co_col = next((c for c in filt_df.columns if 'DXer' in c and 'Country' in c), 'DXer_Country')
        mo_col = next((c for c in filt_df.columns if 'Local' in c and 'Month' in c and 'Name' in c), 'Local_Month_Name')
        yr_col = next((c for c in filt_df.columns if 'Local' in c and 'Year' in c), 'Local_Year')
        dt_col = next((c for c in filt_df.columns if 'Local' in c and 'Date' in c), 'Local_Date')
        tm_col = next((c for c in filt_df.columns if 'Local' in c and 'Time' in c), 'Local_Time')
        
        if not st.session_state.selected_state:
            st.info("💡 **INTERACTIVE MODE:** Click a state on the map below to fly out Path Intelligence.")
            col_map, col_stats = st.columns([1, 0.001])
        else: col_map, col_stats = st.columns([3, 1])
        
        with col_map:
            us_data = filt_df[filt_df['Country'] == 'USA']
            if not us_data.empty:
                state_counts = us_data.groupby('State').size().reset_index(name='Logs')
                glow_scale = [[0, 'rgb(100,0,0)'], [0.2, 'rgb(183,28,28)'], [0.5, 'rgb(211,47,47)'], [0.8, 'rgb(255,69,0)'], [1, 'rgb(255,165,0)']]
                fig = px.choropleth(state_counts, locations='State', locationmode="USA-states", color='Logs', scope="usa", color_continuous_scale=glow_scale, template="plotly_dark")
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor='black'), margin={"r":0,"t":0,"l":0,"b":0}, height=700)
                ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=f"us_map_{st.session_state.map_key}")
                if ev and ev.get("selection") and ev["selection"].get("points"):
                    new_sel = ev["selection"]["points"][0]["location"]
                    if st.session_state.selected_state != new_sel: st.session_state.selected_state = new_sel; st.rerun()

        if st.session_state.selected_state:
            with col_stats:
                sel = st.session_state.selected_state
                st.markdown(f"### {sel} INTEL")
                if st.button("❌ CLEAR SELECTION", use_container_width=True): 
                    st.session_state.selected_state = None; st.session_state.map_key += 1; st.rerun()
                
                s_of = us_data[us_data['State'] == sel]
                s_from = filt_df[filt_df[dx_st_col] == sel]

                st.markdown('<div class="stat-header">MOST HEARD STATION</div>', unsafe_allow_html=True)
                if not s_of.empty:
                    top_st = s_of.groupby(['Frequency', 'Station', 'City']).size().idxmax()
                    st.markdown(f'<div class="stat-val">{top_st[1]}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-label">{top_st[0]} MHz • {top_st[2]} • {s_of.groupby(["Frequency", "Station", "City"]).size().max()} Logs</div>', unsafe_allow_html=True)

                st.markdown('<div class="stat-header">PEAK SEASONALITY</div>', unsafe_allow_html=True)
                if not s_of.empty:
                    m_c, y_c = s_of[mo_col].value_counts(), s_of[yr_col].value_counts()
                    st.markdown(f'<div class="stat-val">{str(m_c.idxmax()).upper()} ({m_c.max()})</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{y_c.idxmax()} ({y_c.max()})</div>', unsafe_allow_html=True)
                    st.markdown('<div class="window-box">', unsafe_allow_html=True)
                    st.markdown('<div class="stat-label" style="color:#D32F2F">Season Window - Signals From This State</div>', unsafe_allow_html=True)
                    of_dates = pd.to_datetime(s_of['Local_Date'])
                    st.markdown(f'<div class="stat-label">Start: {get_avg_date(of_dates.groupby(s_of["Local_Year"]).min())} | Peak: {get_avg_date(of_dates)} | End: {get_avg_date(of_dates.groupby(s_of["Local_Year"]).max())}</div>', unsafe_allow_html=True)
                    st.markdown('<div class="stat-label" style="color:#D32F2F">Season Window - DXers From This State</div>', unsafe_allow_html=True)
                    from_dates = pd.to_datetime(s_from['Local_Date'])
                    st.markdown(f'<div class="stat-label">Start: {get_avg_date(from_dates.groupby(s_from["Local_Year"]).min())} | Peak: {get_avg_date(from_dates)} | End: {get_avg_date(from_dates.groupby(s_from["Local_Year"]).max())}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True)
                if not s_of.empty:
                    f = s_of.sort_values(d_col, ascending=False).iloc[0]
                    st.markdown(f'<div class="stat-val">{f[d_col]:,.0f} MILES</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-label">{f["Station"]} caught by {f["DXer"]} on {f[dt_col]} @ {f[tm_col]}</div>', unsafe_allow_html=True)

                st.markdown('<div class="stat-header">LOCAL DXER ACTIVITY</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{s_from["DXer"].nunique()} UNIQUE DXERS</div>', unsafe_allow_html=True)

                st.markdown('<div class="stat-header">TOP RECEPTION PATHS</div>', unsafe_allow_html=True)
                p_in = s_from[s_from['Country'] == 'USA'].groupby('State').size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                if not p_in.empty: st.dataframe(p_in, column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)
                
                st.markdown('<div class="stat-header">TOP INTERNATIONAL REACH</div>', unsafe_allow_html=True)
                p_intl = s_from[s_from['Country'] != 'USA'].groupby('Country').size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                if not p_intl.empty: st.dataframe(p_intl, column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)
                st.markdown(f'<div class="stat-label">Non-US countries heard in {sel}</div>', unsafe_allow_html=True)

                st.markdown('<div class="stat-header">TOP TRANSMISSION PATHS</div>', unsafe_allow_html=True)
                p_out = s_of[s_of[dx_co_col] == 'USA'].groupby(dx_st_col).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                if not p_out.empty: st.dataframe(p_out, column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)

                st.markdown('<div class="stat-header">TOP 5 STATIONS</div>', unsafe_allow_html=True)
                if not s_of.empty:
                    t5 = s_of.groupby(['Frequency', 'Station']).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                    st.dataframe(t5, column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)
