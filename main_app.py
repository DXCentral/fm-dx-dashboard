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
if 'selected_prov' not in st.session_state: st.session_state.selected_prov = None
if 'map_key' not in st.session_state: st.session_state.map_key = 2000

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
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
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
    selected_page = option_menu("MODULES", ["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC ANALYSIS"], icons=["house", "cloud", "geo"], default_index=0)

# 4. GLOBAL FILTERS
if not st.session_state.full_screen:
    st.image("SEDAP Banner.png", width=600)
    rk = f"v{st.session_state.reset_count}"
    with st.expander("GLOBAL FILTERS", expanded=True):
        r1 = st.columns(5)
        f_freq = r1[0].selectbox("Freq", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key=f"fq_{rk}")
        f_dxer = r1[1].selectbox("DXer", ["All"] + sorted(df['DXer'].dropna().unique().astype(str).tolist()), key=f"dx_{rk}")
        f_station = r1[2].selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().astype(str).tolist()), key=f"st_{rk}")
        f_state = r1[3].selectbox("State", ["All"] + sorted(df['State'].dropna().unique().astype(str).tolist()), key=f"ste_{rk}")
        f_country = r1[4].selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().astype(str).tolist()), key=f"cy_{rk}")
        if st.button("RESET ALL"): st.session_state.reset_count += 1; st.rerun()
else: f_freq, f_dxer, f_station, f_state, f_country = ["All"]*5

filt_df = df.copy()
f_map = {'Frequency':f_freq, 'DXer':f_dxer, 'Station':f_station, 'State':f_state, 'Country':f_country}
for col, val in f_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# 5. DASHBOARD
if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Logs", f"{len(filt_df):,}"); m2.metric("Stations", f"{filt_df['Station'].nunique():,}")
    st.dataframe(filt_df[['Local_Date', 'Frequency', 'Station', 'City', 'State', 'DXer', d_col]].head(100), use_container_width=True)

# 6. ES-CLOUD TRACKER
elif selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Analysis")
    view_mode = st.pills("LAYER", ["Heatmap", "Paths"], default="Heatmap")
    hc1, hc2 = st.columns([1, 2])
    with hc1:
        range_on = st.checkbox("Range Mode", value=True) 
        avail = sorted(filt_df['Date_Obj'].unique()) 
        if range_on:
            dr = st.date_input("Select Range", value=(avail[0], avail[-1]))
            map_df = filt_df[(filt_df['Date_Obj'] >= dr[0]) & (filt_df['Date_Obj'] <= dr[1])] if len(dr)==2 else filt_df
        else:
            ds = st.date_input("Select Date", value=avail[-1])
            map_df = filt_df[filt_df['Date_Obj'] == ds]
    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        current_time = hc2.select_slider("Time", options=["SHOW ALL"] + times, value="SHOW ALL")
        r_df = map_df if current_time == "SHOW ALL" else map_df[map_df['Time_Str'] == current_time]
        layers = [pdk.Layer('HeatmapLayer', data=r_df[['Mid_Lat', 'Mid_Lon']].dropna(), get_position='[Mid_Lon, Mid_Lat]', radius_pixels=65)]
        st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', initial_view_state=pdk.ViewState(latitude=32, longitude=-95, zoom=3.4), layers=layers, height=1000))

# 7. MODULE 3: GEOGRAPHIC ANALYSIS
elif selected_page == "GEOGRAPHIC ANALYSIS":
    st.markdown("<h2 style='text-align: center; color: #D32F2F;'>GEOGRAPHIC ANALYSIS SUITE</h2>", unsafe_allow_html=True)
    gv = st.pills("MODULE", options=["US States", "Canadian Stats", "Mexican Stats"], default="US States")
    
    dx_st_col = next((c for c in filt_df.columns if 'DXer' in c and ('State' in c or 'Prov' in c)), 'DXer_State_Prov')
    dx_co_col = next((c for c in filt_df.columns if 'DXer' in c and 'Country' in c), 'DXer_Country')
    mo_col, yr_col = next((c for c in filt_df.columns if 'Local' in c and 'Month' in c and 'Name' in c), 'Local_Month_Name'), next((c for c in filt_df.columns if 'Local' in c and 'Year' in c), 'Local_Year')
    gs = [[0, 'rgb(100,0,0)'], [0.2, 'rgb(183,28,28)'], [0.5, 'rgb(211,47,47)'], [0.8, 'rgb(255,69,0)'], [1, 'rgb(255,165,0)']]

    # LAYOUT ENGINE: Strict re-rendering of columns
    main_placeholder = st.container()
    
    if gv == "US States":
        if not st.session_state.selected_state:
            c1, c2 = main_placeholder.columns([1, 0.001])
        else: c1, c2 = main_placeholder.columns([3, 1])
        
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
                s_of = us_d[us_d['State'] == sel]
                s_fr = filt_df[filt_df[dx_st_col] == sel]
                st.markdown('<div class="stat-header">MOST HEARD</div>', unsafe_allow_html=True)
                if not s_of.empty:
                    top = s_of.groupby(['Frequency', 'Station', 'City']).size().idxmax()
                    st.markdown(f'<div class="stat-val">{top[1]}</div><div class="stat-label">{top[0]} MHz • {top[2]}</div>', unsafe_allow_html=True)
                st.markdown('<div class="stat-header">TOP PATHS (US/CA)</div>', unsafe_allow_html=True)
                p_in = s_fr[s_fr['Country'].isin(['USA', 'Canada'])].groupby('State').size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                st.dataframe(p_in, column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)

    elif gv == "Canadian Stats":
        if not st.session_state.selected_prov:
            c1, c2 = main_placeholder.columns([1, 0.001])
        else: c1, c2 = main_placeholder.columns([3, 1])
        
        with c1:
            ca_d = filt_df[filt_df['Country'] == 'Canada']
            counts = ca_d.groupby('State').size().reset_index(name='Logs')
            # Canada Specific Map
            fig = px.choropleth(counts, locations='State', locationmode="country names", color='Logs', scope="north america", color_continuous_scale=gs, template="plotly_dark")
            fig.update_geos(fitbounds="locations", visible=False)
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor='black'), margin={"r":0,"t":0,"l":0,"b":0}, height=700)
            ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=f"c_{st.session_state.map_key}")
            if ev and ev.get("selection") and ev["selection"].get("points"):
                st.session_state.selected_prov = ev["selection"]["points"][0]["location"]; st.rerun()

        if st.session_state.selected_prov:
            with c2:
                sel = st.session_state.selected_prov
                st.markdown(f"### {sel} INTEL")
                if st.button("❌ CLEAR"): st.session_state.selected_prov = None; st.session_state.map_key += 1; st.rerun()
                s_of = ca_d[ca_d['State'] == sel]
                s_fr = filt_df[filt_df[dx_st_col] == sel]
                st.markdown('<div class="stat-header">MOST HEARD</div>', unsafe_allow_html=True)
                if not s_of.empty:
                    top = s_of.groupby(['Frequency', 'Station', 'City']).size().idxmax()
                    st.markdown(f'<div class="stat-val">{top[1]}</div><div class="stat-label">{top[0]} MHz • {top[2]}</div>', unsafe_allow_html=True)
                st.markdown('<div class="stat-header">TOP PATHS (US/CA)</div>', unsafe_allow_html=True)
                p_in = s_fr[s_fr['Country'].isin(['USA', 'Canada'])].groupby('State').size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                st.dataframe(p_in, column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)
