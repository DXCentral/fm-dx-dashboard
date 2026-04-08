import streamlit as st
import pandas as pd
import pydeck as pdk
import time
import datetime
import plotly.express as px
from google.cloud import bigquery
from google.oauth2 import service_account 

# --- 1. THEME & UI STYLING (The SEDAP "Cinematic" Look) ---
st.set_page_config(layout="wide", page_title="SEDAP Control Center v77.0")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@200;300;400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Oswald', sans-serif !important; background-color: #000000; color: #FFFFFF; font-weight: 300; }
    
    /* Stealth Buttons */
    div.stButton > button {
        background-color: #000000 !important; color: #FFFFFF !important;
        border: 1px solid #444444 !important; border-radius: 25px !important;
        padding: 8px 25px !important; text-transform: uppercase;
        font-family: 'Oswald', sans-serif !important; letter-spacing: 1px;
    }
    div.stButton > button:hover { border-color: #D32F2F !important; color: #D32F2F !important; }
    
    /* Looker-Style Headers */
    h1, h2, h3, h4 { color: #D32F2F !important; text-transform: uppercase; letter-spacing: 3px; font-family: 'Oswald', sans-serif !important; }
    
    /* Metric Styling */
    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; font-weight: 200; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; }
    
    /* Map Height Override */
    .stPydeckChart { height: 800px !important; }
    </style>
    """, unsafe_allow_html=True)

# State initialization
if 'full_screen' not in st.session_state: st.session_state.full_screen = False
if 'p_idx' not in st.session_state: st.session_state.p_idx = 0
if 'playing' not in st.session_state: st.session_state.playing = False
if 'reset_count' not in st.session_state: st.session_state.reset_count = 0

if st.session_state.full_screen:
    st.markdown("""<style>[data-testid="stSidebar"], [data-testid="stHeader"] { display: none !important; } .stMain { padding: 0 !important; }</style>""", unsafe_allow_html=True)

# --- 2. DATA LOADING (The "Coordinate Detective" & Drive Scope Fix) ---
@st.cache_data(ttl=600)
def load_data():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        # Scopes for BigQuery + Google Sheets Access
        scopes = ["https://www.googleapis.com/auth/bigquery", "https://www.googleapis.com/auth/drive.readonly"]
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = bigquery.Client(credentials=credentials, project=credentials.project_id)
        
        # Pull Data
        df_logs = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_data_raw`").to_dataframe()
        df_coords = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_coords`").to_dataframe()
        
        # Dynamic Column detection for Join
        l_dx = [c for c in df_logs.columns if 'Concatenated' in c and 'DX' in c][0]
        l_st = [c for c in df_logs.columns if 'Concatenated' in c and 'Station' in c][0]
        c_dx = [c for c in df_coords.columns if 'Concatenated' in c and 'DX' in c][0]
        c_st = [c for c in df_coords.columns if 'Concatenated' in c and 'Station' in c][0]

        df_coords = df_coords.drop_duplicates(subset=[c_dx, c_st])
        df = df_logs.merge(df_coords, left_on=[l_dx, l_st], right_on=[c_dx, c_st], how='left')
        
        # Coordinate Detective: Find Lat/Lon regardless of name
        def find_col(keywords, df):
            for c in df.columns:
                if all(k.lower() in c.lower() for k in keywords): return c
            return None

        dx_lat = find_col(['DX', 'Lat'], df) or 'Mid_Lat'
        dx_lon = find_col(['DX', 'Lon'], df) or 'Mid_Long'
        st_lat = find_col(['Station', 'Lat'], df) or 'Mid_Lat'
        st_lon = find_col(['Station', 'Long'], df) or 'Mid_Long'
        
        # THE TYPE-ERROR FIX: Clean symbols, force numeric, and drop NaNs
        for c in [dx_lat, dx_lon, st_lat, st_lon, 'Mid_Lat', 'Mid_Long']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace('°', '').str.strip(), errors='coerce')
        
        # Drop rows with broken coordinates to prevent Pydeck crash
        df = df.dropna(subset=['Mid_Lat', 'Mid_Long'])
        
        df['Date_Obj'] = pd.to_datetime(df['Local_Date']).dt.date
        df['Time_Str'] = pd.to_datetime(df['Local_Time'], errors='coerce').dt.strftime('%H:%M')
        
        dist_col = [c for c in df.columns if 'Distance' in c and 'mi' in c][0]
        return df, df['Date_Obj'].max(), dist_col, dx_lat, dx_lon, st_lat, st_lon
    except Exception as e:
        st.error(f"System Link Failure: {e}")
        return pd.DataFrame(), None, "Distance", None, None, None, None

df, last_log_date, d_col, dx_lat, dx_lon, st_lat, st_lon = load_data()
if df.empty: st.stop()

# --- 3. SIDEBAR NAVIGATION & GLOBAL FILTERS ---
from streamlit_option_menu import option_menu
with st.sidebar:
    selected_page = option_menu(
        menu_title="DATA MODULES", 
        options=["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC ANALYSIS"], 
        icons=["house-fill", "cloud-haze2", "geo-alt"], 
        default_index=0
    )

if not st.session_state.full_screen:
    rk = f"v{st.session_state.reset_count}"
    with st.expander(label="GLOBAL FILTERS", expanded=True):
        r1, r2, r3 = st.columns(3), st.columns(3), st.columns(3)
        f_freq = r1[0].selectbox("Freq", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key=f"fr_{rk}")
        f_dxer = r1[1].selectbox("DXer", ["All"] + sorted(df['DXer'].dropna().unique().astype(str).tolist()), key=f"dx_{rk}")
        f_state = r1[2].selectbox("State", ["All"] + sorted(df['State'].dropna().unique().astype(str).tolist()), key=f"st_{rk}")
        f_country = r2[0].selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().astype(str).tolist()), key=f"co_{rk}")
        f_month = r2[1].selectbox("Month", ["All"] + sorted(df['Local_Month'].dropna().unique().astype(str).tolist()), key=f"mo_{rk}")
        f_year = r2[2].selectbox("Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key=f"yr_{rk}")
        if st.button("RESET FILTERS"): st.session_state.reset_count += 1; st.rerun()

# Apply Filters
filt_df = df.copy()
f_map = {'Frequency': f_freq, 'DXer': f_dxer, 'State': f_state, 'Country': f_country, 'Local_Month': f_month, 'Local_Year': f_year}
for col, val in f_map.items():
    if val != "All": filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# --- 4. MODULE 1: DASHBOARD ---
if selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("TOTAL LOGS", f"{len(filt_df):,}")
    m2.metric("UNIQUE STATIONS", f"{filt_df['Station'].nunique():,}")
    m3.metric("COUNTRIES", filt_df['Country'].nunique())
    m4.metric("MAX DISTANCE", f"{filt_df[d_col].max():,.0f} mi")
    st.dataframe(filt_df.head(100), use_container_width=True)

# --- 5. MODULE 2: ES-CLOUD TRACKER (PRESERVED LOGIC) ---
elif selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    view_mode = st.pills("MAP LAYER", ["Es Cloud Location Heatmap", "Path Line Analysis"], default="Es Cloud Location Heatmap")
    
    hc1, hc2 = st.columns([1, 2])
    avail_days = sorted(filt_df['Date_Obj'].unique())
    date_range = hc1.date_input("Date Range", value=(avail_days[0], avail_days[-1]))
    map_df = filt_df[(filt_df['Date_Obj'] >= date_range[0]) & (filt_df['Date_Obj'] <= date_range[1])] if len(date_range) == 2 else filt_df
    
    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        current_time = hc2.select_slider("Time", options=["SHOW ALL"] + times, value="SHOW ALL")
        render_df = map_df if current_time == "SHOW ALL" else map_df[map_df['Time_Str'] == current_time]
        
        layers = []
        if view_mode == "Es Cloud Location Heatmap":
            layers.append(pdk.Layer('HeatmapLayer', data=render_df[['Mid_Lat', 'Mid_Long']], get_position='[Mid_Long, Mid_Lat]', radius_pixels=60))
        else:
            layers.append(pdk.Layer('LineLayer', data=render_df, get_source_position=f'[{dx_lon}, {dx_lat}]', get_target_position=f'[{st_lon}, {st_lat}]', get_width=1.5, get_color=[211, 47, 47, 100]))
        
        st.pydeck_chart(pdk.Deck(map_style='mapbox://styles/mapbox/dark-v11', layers=layers, initial_view_state=pdk.ViewState(latitude=32, longitude=-95, zoom=3.4)))

# --- 6. MODULE 3: GEOGRAPHIC ANALYSIS (NEW SUITE) ---
elif selected_page == "GEOGRAPHIC ANALYSIS":
    st.header("Geographic Analysis Suite")
    
    # Implementing the specific tabs from the blueprint
    tab1, tab2, tab3 = st.tabs(["🌎 Country Stats", "🍁 Canadian Stats", "🇺🇸 US State Stats"])
    
    with tab1: # Country Stats
        st.subheader("Global Distribution & Trends")
        c_logs = filt_df.groupby('Country').size().reset_index(name='Logs').sort_values('Logs', ascending=False)
        st.metric("Total Countries Heard", len(c_logs))
        
        col_c1, col_c2 = st.columns([1, 2])
        col_c1.dataframe(c_logs, column_config={"Logs": st.column_config.ProgressColumn("Volume", min_value=0, max_value=int(c_logs['Logs'].max()))}, hide_index=True)
        
        # Logs by Country and Month (Stacked Bar)
        country_month = filt_df.groupby(['Country', 'Local_Month']).size().reset_index(name='Logs')
        fig = px.bar(country_month, x="Local_Month", y="Logs", color="Country", barmode="stack", color_discrete_sequence=px.colors.sequential.Reds_r)
        fig.update_layout(paper_bgcolor='black', plot_bgcolor='black', font_color='white', font_family='Oswald', bargap=0.3)
        col_c2.plotly_chart(fig, use_container_width=True)

    with tab2: # Canadian Stats
        can_df = filt_df[filt_df['Country'] == 'Canada']
        st.metric("Total Canadian Logs", len(can_df))
        prov_logs = can_df.groupby('State').size().reset_index(name='Logs').sort_values('Logs', ascending=False)
        
        col_can1, col_can2 = st.columns(2)
        col_can1.markdown("#### Logs by Province")
        col_can1.dataframe(prov_logs, column_config={"Logs": st.column_config.ProgressColumn("Logs", min_value=0, max_value=int(prov_logs['Logs'].max() if not prov_logs.empty else 1))}, hide_index=True)
        
        # Province Map
        col_can2.pydeck_chart(pdk.Deck(
            map_style='mapbox://styles/mapbox/dark-v11',
            initial_view_state=pdk.ViewState(latitude=55, longitude=-95, zoom=2.5),
            layers=[pdk.Layer('ScatterplotLayer', can_df, get_position=f'[{st_lon}, {st_lat}]', get_color='[211, 47, 47, 160]', get_radius=30000)]
        ))

    with tab3: # US State Stats
        us_df = filt_df[filt_df['Country'] == 'USA']
        st.subheader("US Log Density & Reach")
        
        # Floating Overlay for US Page
        st.markdown(f"""
            <div style="background-color: rgba(211,47,47,0.1); border: 1px solid #D32F2F; padding: 10px; border-radius: 5px; width: fit-content;">
                <span style="color: #D32F2F; font-weight: bold; font-size: 20px;">{us_df['State'].nunique()}</span> <span style="color: white;">US STATES LOGGED</span>
            </div>
        """, unsafe_allow_html=True)
        
        st.pydeck_chart(pdk.Deck(
            map_style='mapbox://styles/mapbox/dark-v11',
            initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=3.5),
            layers=[pdk.Layer('HeatmapLayer', us_df, get_position=f'[{st_lon}, {st_lat}]', radius_pixels=50)]
        ))
        
        # State Bar Chart (Top 20)
        state_logs = us_df.groupby('State').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(20)
        fig_st = px.bar(state_logs, x='State', y='Logs', color_discrete_sequence=['#D32F2F'])
        fig_st.update_layout(paper_bgcolor='black', plot_bgcolor='black', font_color='white', font_family='Oswald', bargap=0.4)
        st.plotly_chart(fig_st, use_container_width=True)
