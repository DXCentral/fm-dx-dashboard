import streamlit as st
import pandas as pd
import pydeck as pdk
import time
import datetime
import plotly.express as px
import numpy as np
import folium
from streamlit_folium import st_folium
from google.cloud import bigquery
from google.oauth2 import service_account 

# 1. THEME & UI STYLING
st.set_page_config(layout="wide", page_title="SEDAP Control Center")

if 'full_screen' not in st.session_state: st.session_state.full_screen = False
if 'p_idx' not in st.session_state: st.session_state.p_idx = 0
if 'playing' not in st.session_state: st.session_state.playing = False
if 'reset_count' not in st.session_state: st.session_state.reset_count = 0
if 'selected_region' not in st.session_state: st.session_state.selected_region = None
if 'map_key' not in st.session_state: st.session_state.map_key = 10000

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

# 4. GLOBAL FILTERS
if not st.session_state.full_screen:
    rk = f"v{st.session_state.reset_count}"
    with st.expander("GLOBAL FILTERS", expanded=True):
        r1 = st.columns(5)
        f_freq = r1[0].selectbox("Freq", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key=f"f1_{rk}")
        f_dxer = r1[1].selectbox("DXer", ["All"] + sorted(df['DXer'].dropna().unique().astype(str).tolist()), key=f"f2_{rk}")
        f_station = r1[2].selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().astype(str).tolist()), key=f"f3_{rk}")
        f_state = r1[3].selectbox("State", ["All"] + sorted(df['State'].dropna().unique().astype(str).tolist()), key=f"f4_{rk}")
        f_country = r1[4].selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().astype(str).tolist()), key=f"f5_{rk}")
        if st.button("RESET ALL"): st.session_state.reset_count += 1; st.rerun()
else: f_freq, f_dxer, f_station, f_state, f_country = ["All"]*5

filt_df = df.copy()
f_map = {'Frequency':f_freq, 'DXer':f_dxer, 'Station':f_station, 'State':f_state, 'Country':f_country}
for col, val in f_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# 5. DASHBOARD OVERVIEW
if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m = st.columns(7)
    m[0].metric("Total Logs", f"{len(filt_df):,}"); m[1].metric("Unique Stations", f"{filt_df['Station'].nunique():,}")
    m[2].metric("US States", filt_df[filt_df['Country']=='USA']['State'].nunique())
    m[3].metric("CA Prov", filt_df[filt_df['Country']=='Canada']['State'].nunique())
    m[4].metric("MX States", filt_df[filt_df['Country']=='Mexico']['State'].nunique())
    m[5].metric("Countries", filt_df['Country'].nunique())
    m[6].metric("Max Dist", f"{filt_df[d_col].max() if not filt_df.empty else 0:,.0f} mi")
    st.dataframe(filt_df[['Local_Date', 'Frequency', 'Station', 'City', 'State', 'DXer', d_col]].head(100), use_container_width=True)

# 6. MODULE 3: GEOGRAPHIC ANALYSIS
elif selected_page == "GEOGRAPHIC ANALYSIS":
    st.markdown("<h2 style='text-align: center; color: #D32F2F;'>GEOGRAPHIC ANALYSIS SUITE</h2>", unsafe_allow_html=True)
    gv = st.pills("SELECT VIEW", options=["US STATES", "CANADIAN PROVINCES", "MEXICAN STATES", "DISTANCE STATS"], default="US STATES")
    st.markdown("---")
    
    dx_st_col = next((c for c in filt_df.columns if 'DXer' in c and ('State' in c or 'Prov' in c)), 'DXer_State_Prov')
    mo_col, yr_col = next((c for c in filt_df.columns if 'Local' in c and 'Month' in c and 'Name' in c), 'Local_Month_Name'), next((c for c in filt_df.columns if 'Local' in c and 'Year' in c), 'Local_Year')
    dt_col, tm_col = next((c for c in filt_df.columns if 'Local' in c and 'Date' in c), 'Local_Date'), next((c for c in filt_df.columns if 'Local' in c and 'Time' in c), 'Local_Time')
    gs = [[0, 'rgb(100,0,0)'], [0.2, 'rgb(183,28,28)'], [0.5, 'rgb(211,47,47)'], [0.8, 'rgb(255,69,0)'], [1, 'rgb(255,165,0)']]

    # LOGIC GATE: US MAP (PLOTLY) vs CAN/MEX (FOLIUM/SELECT)
    if gv == "US STATES":
        if not st.session_state.selected_region: col_m, col_f = st.columns([1, 0.001])
        else: col_m, col_f = st.columns([3, 1])
        with col_m:
            us_d = filt_df[filt_df['Country'] == 'USA']
            counts = us_d.groupby('State').size().reset_index(name='Logs')
            fig = px.choropleth(counts, locations='State', locationmode="USA-states", color='Logs', scope="usa", color_continuous_scale=gs, template="plotly_dark")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor='black'), margin={"r":0,"t":0,"l":0,"b":0}, height=700)
            ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=f"us_map_{st.session_state.map_key}")
            if ev and ev.get("selection") and ev["selection"].get("points"):
                st.session_state.selected_region = ev["selection"]["points"][0]["location"]; st.rerun()

    elif gv in ["CANADIAN PROVINCES", "MEXICAN STATES"]:
        target_country = 'Canada' if gv == "CANADIAN PROVINCES" else 'Mexico'
        c_data = filt_df[filt_df['Country'] == target_country]
        sel_name = st.selectbox(f"SELECT {target_country.upper()} REGION FOR INTEL", ["NONE"] + sorted(c_data['State'].dropna().unique().tolist()))
        
        if sel_name == "NONE": col_m, col_f = st.columns([1, 0.001])
        else: 
            st.session_state.selected_region = sel_name
            col_m, col_f = st.columns([3, 1])
        
        with col_m:
            # FOLIUM MAP INTEGRATION
            center = [56, -106] if target_country == 'Canada' else [23, -102]
            m = folium.Map(location=center, zoom_start=4, tiles="CartoDB dark_matter")
            for _, row in c_data.sample(n=min(len(c_data), 500)).iterrows():
                folium.CircleMarker([row[st_lat], row[st_lon]], radius=2, color="#D32F2F", fill=True).add_to(m)
            st_folium(m, width=1200, height=700)

    # SHARED FLYOUT ENGINE (FULL INTEL RESTORATION)
    if st.session_state.selected_region:
        with col_f:
            sel = st.session_state.selected_region
            st.markdown(f"### {sel} INTEL")
            if st.button("❌ CLEAR SELECTION"): st.session_state.selected_region = None; st.rerun()
            
            s_of = filt_df[filt_df['State'] == sel]
            s_fr = filt_df[filt_df[dx_st_col] == sel]

            if not s_of.empty:
                top = s_of.groupby(['Frequency', 'Station', 'City']).size().idxmax()
                st.markdown('<div class="stat-header">MOST HEARD STATION</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{top[1]}</div><div class="stat-label">{top[0]} MHz • {top[2]} • {s_of.groupby(["Frequency", "Station", "City"]).size().max()} Logs</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="stat-header">PEAK SEASONALITY</div>', unsafe_allow_html=True)
                m_c = s_of[mo_col].value_counts()
                st.markdown(f'<div class="stat-val">{str(m_c.idxmax()).upper()}</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="window-box">', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-label" style="color:#D32F2F">SIGNAL PROPAGATION WINDOW</div>', unsafe_allow_html=True)
                of_dates = pd.to_datetime(s_of['Local_Date'])
                st.markdown(f'<div class="stat-label">Start: {get_avg_date(of_dates.groupby(s_of["Local_Year"]).min())} | Peak: {get_avg_date(of_dates)} | End: {get_avg_date(of_dates.groupby(s_of["Local_Year"]).max())}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True)
                f = s_of.sort_values(d_col, ascending=False).iloc[0]
                st.markdown(f'<div class="stat-val">{f[d_col]:,.0f} MILES</div><div class="stat-label">{f["Station"]} by {f["DXer"]}</div>', unsafe_allow_html=True)

                st.markdown('<div class="stat-header">TOP PATHS</div>', unsafe_allow_html=True)
                p_in = s_fr.groupby('State').size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                st.dataframe(p_in, column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)
