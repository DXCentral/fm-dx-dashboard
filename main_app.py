import streamlit as st
import pandas as pd
import pydeck as pdk
import time
import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import re
from google.cloud import bigquery
from google.oauth2 import service_account 

# 1. THEME & UI STYLING
st.set_page_config(layout="wide", page_title="SEDAP Control Center")

# EXPLICIT SESSION STATE INITIALIZATION (LOCKED)
if 'full_screen' not in st.session_state: 
    st.session_state.full_screen = False
if 'p_idx' not in st.session_state: 
    st.session_state.p_idx = 0
if 'playing' not in st.session_state: 
    st.session_state.playing = False
if 'reset_count' not in st.session_state: 
    st.session_state.reset_count = 0
if 'selected_state' not in st.session_state: 
    st.session_state.selected_state = None
if 'selected_logged_county' not in st.session_state:
    st.session_state.selected_logged_county = None
if 'selected_tier' not in st.session_state: 
    st.session_state.selected_tier = None
if 'selected_hour' not in st.session_state: 
    st.session_state.selected_hour = None
if 'selected_year' not in st.session_state: 
    st.session_state.selected_year = None
if 'selected_intl_country' not in st.session_state: 
    st.session_state.selected_intl_country = None
if 'selected_mhz' not in st.session_state: 
    st.session_state.selected_mhz = "TUNE..."
if 'selected_dx_loc' not in st.session_state:
    st.session_state.selected_dx_loc = None
if 'selected_st_loc' not in st.session_state:
    st.session_state.selected_st_loc = None
if 'selected_wtfda_state' not in st.session_state:
    st.session_state.selected_wtfda_state = None
if 'selected_wtfda_state_intel' not in st.session_state:
    st.session_state.selected_wtfda_state_intel = None
if 'selected_wtfda_county_intel' not in st.session_state:
    st.session_state.selected_wtfda_county_intel = None
if 'selected_format' not in st.session_state:
    st.session_state.selected_format = None
if 'selected_slogan' not in st.session_state:
    st.session_state.selected_slogan = None
if 'dist_map_key' not in st.session_state: 
    st.session_state.dist_map_key = 0
if 'map_key' not in st.session_state: 
    st.session_state.map_key = 500000
if 'logged_county_map_key' not in st.session_state:
    st.session_state.logged_county_map_key = 550000
if 'hour_map_key' not in st.session_state: 
    st.session_state.hour_map_key = 600000
if 'year_map_key' not in st.session_state: 
    st.session_state.year_map_key = 700000
if 'freq_map_key' not in st.session_state: 
    st.session_state.freq_map_key = 800000
if 'intl_map_key' not in st.session_state: 
    st.session_state.intl_map_key = 900000
if 'dx_map_key' not in st.session_state:
    st.session_state.dx_map_key = 1000000
if 'st_map_key' not in st.session_state:
    st.session_state.st_map_key = 1100000
if 'wtfda_map_key' not in st.session_state:
    st.session_state.wtfda_map_key = 1200000
if 'wtfda_state_intel_map_key' not in st.session_state:
    st.session_state.wtfda_state_intel_map_key = 1250000
if 'wtfda_county_intel_map_key' not in st.session_state:
    st.session_state.wtfda_county_intel_map_key = 1260000
if 'format_map_key' not in st.session_state:
    st.session_state.format_map_key = 1300000
if 'slogan_map_key' not in st.session_state:
    st.session_state.slogan_map_key = 1400000
if 'almanac_month' not in st.session_state: 
    st.session_state.almanac_month = "June"
if 'muf_almanac_month' not in st.session_state: 
    st.session_state.muf_almanac_month = "June"
if 'freq_direct_entry' not in st.session_state:
    st.session_state.freq_direct_entry = ""
if 'muf_tactical_date' not in st.session_state:
    st.session_state.muf_tactical_date = None
if 'solar_overlay_mode' not in st.session_state:
    st.session_state.solar_overlay_mode = "SFI (10.7cm Radio Flux)"

# Teleport Engine Variables
if 'nav_idx' not in st.session_state:
    st.session_state.nav_idx = 0
if 'jump_to_rds' not in st.session_state:
    st.session_state.jump_to_rds = False
if 'rds_view_default' not in st.session_state:
    st.session_state.rds_view_default = "WTFDA US State Intelligence"

if st.session_state.full_screen:
    st.markdown("""<style>[data-testid="stSidebar"], [data-testid="stHeader"], .st-emotion-cache-zq5m06 { display: none !important; } .stMain { padding: 0 !important; } .watermark { bottom: 120px !important; } </style>""", unsafe_allow_html=True)

# --- GLOBAL THEME VARIABLES ---
th_bg = "#000000"
th_text = "#FFFFFF"
th_panel = "#0A0A0A"
th_border = "#1A1A1A"
th_red = "#D32F2F"
th_dark_red = "#640000"
th_yellow = "#FFFF00"
th_orange = "#FFA500"
th_gray = "#888888"
th_blue = "#00BFFF"
plotly_tmpl = "plotly_dark"
map_style_url = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
map_style_px = "carto-darkmatter"
map_line_color = [211, 47, 47, 45]

# Global Custom Heatmap Scale (Yellow/White = Low, Red = High)
global_color_scale = [
    [0.0, '#FFFFE0'], 
    [0.25, th_yellow], 
    [0.5, th_orange], 
    [0.75, th_red], 
    [1.0, th_dark_red]
]

css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@200;300;400;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

html, body, [class*="st-"] { font-family: 'Oswald', sans-serif !important; background-color: VAR_BG; color: VAR_TEXT; font-weight: 300; }
[data-testid="stDeckGlJsonChart"] { height: 1500px !important; }
[data-testid="collapsedControl"] { display: none !important; }
.lcd-screen { background-color: #a3c2c2; color: #002244; font-family: 'Share Tech Mono', monospace; font-size: 4.5rem; font-weight: bold; text-align: center; padding: 10px; border-radius: 8px; border: 4px solid #222; box-shadow: inset 0px 0px 15px rgba(0,0,0,0.6); line-height: 1.1; margin-bottom: 10px; }
.lcd-unit { font-size: 1.8rem; color: #003366; }
div.stButton > button { background-color: VAR_BG !important; color: VAR_TEXT !important; border: 1px solid VAR_BORDER !important; border-radius: 25px !important; padding: 8px 25px !important; text-transform: uppercase; font-family: 'Oswald', sans-serif !important; letter-spacing: 1px; }
div.stButton > button:hover { border-color: VAR_RED !important; color: VAR_RED !important; }
div[data-testid="stPills"] button[aria-checked="true"] { border: 2px solid VAR_RED !important; background-color: VAR_BG !important; color: VAR_TEXT !important; }
div[data-testid="stPills"] button { background-color: VAR_BG !important; border: 1px solid VAR_BORDER !important; border-radius: 25px !important; color: VAR_GRAY !important; }
h1, h2, h3, h4 { color: VAR_RED !important; text-transform: uppercase; letter-spacing: 3px; }
[data-testid="stSidebar"] { background-color: VAR_PANEL; border-right: 1px solid VAR_BORDER; }
[data-testid="stMetricValue"] { color: VAR_TEXT !important; font-size: 2.2rem; font-weight: 200; }
[data-testid="stMetricLabel"] { color: VAR_RED !important; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 2px; }
.watermark { position: absolute; bottom: 80px; right: 40px; z-index: 1000; pointer-events: none; opacity: 0.4; }
.stat-header { color: VAR_RED; font-size: 0.95rem; font-weight: 400; margin-bottom: 5px; border-bottom: 1px solid VAR_BORDER; letter-spacing: 1px; padding-top: 15px; }
.stat-val { font-size: 1.3rem; color: VAR_TEXT; font-weight: 300; margin-top: 5px;}
.stat-label { font-size: 0.75rem; color: VAR_GRAY; text-transform: uppercase; margin-bottom: 8px; line-height: 1.2; }
.window-box { border-left: 2px solid VAR_RED; padding-left: 10px; margin-bottom: 15px; }
.welcome-text { font-size: 1.2rem; line-height: 1.6; color: VAR_TEXT; font-weight: 300; }
.welcome-highlight { color: VAR_ORANGE; font-weight: 400; }
</style>
"""
css = css.replace("VAR_BG", th_bg).replace("VAR_TEXT", th_text).replace("VAR_PANEL", th_panel).replace("VAR_BORDER", th_border).replace("VAR_RED", th_red).replace("VAR_GRAY", th_gray).replace("VAR_ORANGE", th_orange)
st.markdown(css, unsafe_allow_html=True)

def get_avg_date(dates_series):
    if dates_series.empty: 
        return "N/A"
    try:
        ds = pd.to_datetime(dates_series)
        return (datetime.datetime(2024, 1, 1) + datetime.timedelta(days=int(ds.dt.dayofyear.mean()) - 1)).strftime('%b %d')
    except: 
        return "N/A"

def update_freq_from_input():
    raw = st.session_state.freq_direct_entry
    if raw:
        val = str(raw).strip()
        if '.' not in val and len(val) >= 3:
            val = val[:-1] + '.' + val[-1]
        try:
            st.session_state.selected_mhz = round(float(val), 1)
            st.session_state.freq_map_key += 1
        except:
            pass
    st.session_state.freq_direct_entry = ""

def clean_station_slogan(text):
    if pd.isna(text) or str(text).strip() == '': 
        return 'Unknown'
    s = str(text)
    s = re.sub(r'(?<!\d)(8[7-9]|9\d|10[0-7])(\.\d)?(?!\d)', '{FREQ}', s)
    s = re.sub(r'\b[Kk][- ]?\{FREQ\}', 'K-{FREQ}', s)
    s = re.sub(r'\b[Yy][- ]?\{FREQ\}', 'Y-{FREQ}', s)
    s = re.sub(r'\b[Qq][- ]?\{FREQ\}', 'Q-{FREQ}', s)
    s = re.sub(r'\b[Zz][- ]?\{FREQ\}', 'Z-{FREQ}', s)
    s = re.sub(r'\b[Xx][- ]?\{FREQ\}', 'X-{FREQ}', s)
    s = re.sub(r'\b(Power|Rock|Magic|Mix|Kiss|Hits|Classic|Oldies|Nash|The Fox|The Bear|The Bull|The Eagle|Bob)[- ]?\{FREQ\}', r'\1 {FREQ}', s, flags=re.IGNORECASE)
    return s.strip()

# TELEPORT CALLBACK FUNCTION
def jump_to_county(fips_code):
    st.session_state.selected_wtfda_county_intel = fips_code
    st.session_state.jump_to_rds = True

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
        
        # --- GRACEFUL DEGRADATION: Try FIPS table first, fallback to original if not built ---
        try:
            df_coords = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_coords_fips`").to_dataframe()
        except:
            df_coords = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_coords`").to_dataframe()
        
        l_dx = next((c for c in df_logs.columns if 'Concatenated' in c and 'DX' in c), 'Concatenated_DXer_Location')
        l_st = next((c for c in df_logs.columns if 'Concatenated' in c and 'Station' in c), 'Concatenated_Station_Location')
        c_dx = next((c for c in df_coords.columns if 'Concatenated' in c and 'DX' in c), 'Concatenated_DXer_Location')
        c_st = next((c for c in df_coords.columns if 'Concatenated' in c and 'Station' in c), 'Concatenated_Station_Location')

        df_logs['join_dx'] = df_logs[l_dx].str.upper().str.strip()
        df_logs['join_st'] = df_logs[l_st].str.upper().str.strip()
        df_coords[c_dx] = df_coords[c_dx].str.upper().str.strip()
        df_coords[c_st] = df_coords[c_st].str.upper().str.strip()

        # FIPS extraction logic
        if 'DXer_County' in df_coords.columns and 'DXer_FIPS' in df_coords.columns:
            dx_base = df_coords[[c_dx, 'DXer_Latitude', 'DXer_Longitude', 'DXer_County', 'DXer_FIPS']].rename(columns={c_dx: 'Loc', 'DXer_Latitude': 'Lat', 'DXer_Longitude': 'Lon', 'DXer_County': 'County', 'DXer_FIPS': 'FIPS'})
        else:
            dx_base = df_coords[[c_dx, 'DXer_Latitude', 'DXer_Longitude']].rename(columns={c_dx: 'Loc', 'DXer_Latitude': 'Lat', 'DXer_Longitude': 'Lon'})
            dx_base['County'] = None
            dx_base['FIPS'] = None
            
        if 'Station_County' in df_coords.columns and 'Station_FIPS' in df_coords.columns:
            st_base = df_coords[[c_st, 'Station_Lat', 'Station_Long', 'Station_County', 'Station_FIPS']].rename(columns={c_st: 'Loc', 'Station_Lat': 'Lat', 'Station_Long': 'Lon', 'Station_County': 'County', 'Station_FIPS': 'FIPS'})
        else:
            st_base = df_coords[[c_st, 'Station_Lat', 'Station_Long']].rename(columns={c_st: 'Loc', 'Station_Lat': 'Lat', 'Station_Long': 'Lon'})
            st_base['County'] = None
            st_base['FIPS'] = None

        master_map = pd.concat([dx_base, st_base]).dropna(subset=['Lat', 'Lon']).drop_duplicates(subset=['Loc'])

        df = df_logs.merge(master_map, left_on='join_dx', right_on='Loc', how='left').rename(columns={'Lat': 'DX_Lat', 'Lon': 'DX_Lon', 'County': 'DXer_County', 'FIPS': 'FIPS_DXer'}).drop(columns=['Loc'])
        df = df.merge(master_map, left_on='join_st', right_on='Loc', how='left').rename(columns={'Lat': 'ST_Lat', 'Lon': 'ST_Lon', 'County': 'County', 'FIPS': 'FIPS'}).drop(columns=['Loc'])

        # Data Correction Shield: Force St. Tammany logs into LA if misattributed
        if 'County' in df.columns and 'State' in df.columns:
            df.loc[df['County'] == 'St. Tammany', 'State'] = 'LA'

        for c in ['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon', 'Mid_Lat', 'Mid_Long']:
            if c in df.columns: 
                df[c] = pd.to_numeric(df[c].astype(str).str.replace('°', '').str.strip(), errors='coerce').astype('float32')

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
        df['DateTime_Key'] = pd.to_datetime(df['Local_Date'].astype(str) + ' ' + df['Local_Time'].astype(str))
        
        dist_col = [c for c in df.columns if 'Distance' in c and 'mi' in c][0]
        dd_col = [c for c in df.columns if 'Distance' in c and 'Distribution' in c][0]
        h_col = next((c for c in df.columns if 'Local' in c and 'Hour' in c), 'Local_Hour')
        y_col = next((c for c in df.columns if 'Local' in c and 'Year' in c), 'Local_Year')
        dom_col = next((c for c in df.columns if 'Local' in c and 'Day' in c and 'Month' in c), 'Local_Day_of_Month')
        m_name_col = next((c for c in df.columns if 'Local' in c and 'Month' in c and 'Name' in c), 'Local_Month_Name')
        dx_st_col = next((c for c in df.columns if 'DXer' in c and ('State' in c or 'Prov' in c)), 'DXer_State_Prov')
        rds_c_field = next((c for c in df.columns if 'RDS' in c and 'Decode' in c), 'RDS_Decode')
        
        df['Station_Discovery_Year'] = df.groupby('Station')[y_col].transform('min')
        df['Freq_Num'] = pd.to_numeric(df['Frequency'], errors='coerce')
        
        df['RDS_Status'] = df[rds_c_field].apply(lambda x: 'No' if pd.isna(x) or str(x).strip().lower() in ['', 'nan', 'none', 'no', '0', 'false'] else 'Yes')

        return df, df['Date_Obj'].max(), dist_col, dd_col, 'DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon', l_dx, l_st, h_col, y_col, dom_col, m_name_col, dx_st_col, rds_c_field
    except Exception as e:
        st.error(f"Link Failure: {e}")
        return pd.DataFrame(), None, "Distance", "Distribution", None, None, None, None, "DX", "Station", "Hour", "Year", "Day", "Month", "DXer_State", "RDS"

df, last_date, d_col, dd_col, dx_lat_f, dx_lon_f, st_lat_f, st_lon_f, dx_loc_col, st_loc_col, h_col, y_col, dom_col, m_name_col, dx_st_col, rds_c = load_data()

if df.empty: 
    st.stop()

# 2b. DATA LOADING (WTFDA BIGQUERY ENGINE)
@st.cache_data(ttl=43200) # Syncs directly with BigQuery every 12 hours
def load_wtfda_data():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/bigquery", "https://www.googleapis.com/auth/drive.readonly"]
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = bigquery.Client(credentials=credentials, project=credentials.project_id)
        
        # Pulling from the new BigQuery Spatial Join table
        df_w = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.wtfda_fips`").to_dataframe()
        
        # --- BIGQUERY AUTO-FIX REVERTER ---
        col_mapping = {
            'S_P': 'S/P',
            'S_P_': 'S/P',
            'PI_Code': 'PI Code',
            'Call_Letters': 'Call Letters'
        }
        df_w = df_w.rename(columns=col_mapping)

        # Data Correction Shield: Force St. Tammany transmitters into LA
        if 'County' in df_w.columns and 'S/P' in df_w.columns:
            df_w.loc[df_w['County'] == 'St. Tammany', 'S/P'] = 'LA'

        df_w = df_w[df_w['Country'].isin(['USA', 'CAN', 'MEX', 'Canada', 'Mexico'])]
        df_w['Country'] = df_w['Country'].replace({'CAN': 'Canada', 'MEX': 'Mexico'})
        df_w['Frequency'] = pd.to_numeric(df_w['Frequency'], errors='coerce')
        
        if 'PI Code' in df_w.columns:
            df_w['Has_PI'] = df_w['PI Code'].apply(lambda x: 'Yes' if pd.notna(x) and str(x).strip() != '' else 'No')
        else:
            df_w['Has_PI'] = 'No'
            
        df_w['Band_Type'] = df_w['Frequency'].apply(lambda x: 'Non-Commercial (88.1-91.9)' if pd.notna(x) and x < 92.0 else 'Commercial (92.1-107.9)')
        df_w['Slogan_Clean'] = df_w['Slogan'].apply(clean_station_slogan)
        df_w['Format'] = df_w['Format'].fillna('Unknown')
        
        if 'Callsign' not in df_w.columns:
            if 'Call Letters' in df_w.columns: df_w['Callsign'] = df_w['Call Letters']
            elif 'Call' in df_w.columns: df_w['Callsign'] = df_w['Call']
            else: df_w['Callsign'] = 'Unknown'
            
        return df_w
    except Exception as e:
        st.error(f"WTFDA Load Error: {e}")
        return pd.DataFrame()

# 2c. DATA LOADING (SPACE WEATHER ENGINE)
@st.cache_data(ttl=43200)
def load_solar_data():
    try:
        # Attempt to pull directly from BigQuery first
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/bigquery", "https://www.googleapis.com/auth/drive.readonly"]
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = bigquery.Client(credentials=credentials, project=credentials.project_id)
        
        df_s = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.solar_data_master`").to_dataframe()
        df_s['Date_Obj'] = pd.to_datetime(df_s['Date_Str']).dt.date
        return df_s
    except Exception as e:
        # Fallback to local CSV if uploaded to the repo directly
        try:
            df_s = pd.read_csv("sedap_solar_clean.csv")
            df_s['Date_Obj'] = pd.to_datetime(df_s['Date_Str']).dt.date
            return df_s
        except:
            st.error(f"Space Weather Database Offline: Could not locate BigQuery table or local sedap_solar_clean.csv")
            return pd.DataFrame()

# 2d. DATA LOADING (WSPR ENGINE)
@st.cache_data(ttl=43200)
def load_wspr_data():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/bigquery", "https://www.googleapis.com/auth/drive.readonly"]
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = bigquery.Client(credentials=credentials, project=credentials.project_id)
        
        df_w = client.query("SELECT * FROM `sporadic-es-data-analysis.FMList_Data.wspr_clouds_master`").to_dataframe()
        df_w['Date_Obj'] = pd.to_datetime(df_w['Date']).dt.date
        df_w['Time_Str'] = df_w['Time_UTC'].astype(str).str[:5]
        return df_w
    except Exception as e:
        try:
            df_w = pd.read_csv("sedap_wspr_clouds.csv")
            df_w['Date_Obj'] = pd.to_datetime(df_w['Date']).dt.date
            df_w['Time_Str'] = df_w['Time_UTC'].astype(str).str[:5]
            return df_w
        except:
            return pd.DataFrame()

# 3. SIDEBAR NAVIGATION ENGINE
pages = ["WELCOME", "DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC ANALYSIS", "TEMPORAL TRENDS", "FREQUENCY & MUF", "DXER INTELLIGENCE", "STATION & RDS IQ", "ATMOSPHERIC CORRELATION", "6M WSPR INTELLIGENCE"]

if st.session_state.jump_to_rds:
    st.session_state.nav_idx = pages.index("STATION & RDS IQ")
    st.session_state.rds_view_default = "WTFDA County Intelligence"
    st.session_state.jump_to_rds = False

from streamlit_option_menu import option_menu
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    selected_page = option_menu(
        "DATA MODULES", 
        pages, 
        icons=["broadcast", "house-fill", "cloud-haze2", "geo-alt", "clock-history", "graph-up-arrow", "person-badge", "broadcast-pin", "sun", "radar"], 
        default_index=st.session_state.nav_idx,
        key=f"nav_menu_{st.session_state.reset_count}_{st.session_state.nav_idx}"
    )

if pages.index(selected_page) != st.session_state.nav_idx:
    st.session_state.nav_idx = pages.index(selected_page)
    st.rerun()

# 4. GLOBAL FILTERS (STATIC)
f_freq = "All"
f_dxer = "All"
f_stat = "All"
f_state = "All"
f_ctry = "All"
f_dxco = "All"
f_dxst = "All"
f_month = "All"
f_year = "All"
f_day = "All"
f_dist = "All"
f_reg = "All"
f_rds = "All"

if not st.session_state.full_screen and selected_page != "WELCOME":
    rk = f"v{st.session_state.reset_count}" 
    st.markdown("<h4 style='color: #D32F2F; margin-bottom: 0px;'>GLOBAL FILTERS</h4>", unsafe_allow_html=True)
    st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px; border-color: #333;'>", unsafe_allow_html=True)
    
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
    f_rds = r3[2].selectbox("RDS Decode?", ["All"] + (sorted(df[rds_c].dropna().unique().astype(str).tolist()) if rds_c in df.columns else []), key=f"f13_{rk}")
    
    if st.button("RESET ALL FILTERS"): 
        st.session_state.reset_count += 1
        st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)

filt_df = df.copy()
f_logic = {
    'Frequency': f_freq, 
    'DXer': f_dxer, 
    'Station': f_stat, 
    'State': f_state, 
    'Country': f_ctry, 
    'DXer_Country': f_dxco, 
    dx_st_col: f_dxst, 
    'Local_Month': f_month, 
    'Local_Year': f_year, 
    'Month_Day': f_day, 
    dd_col: f_dist, 
    'DXer_Region': f_reg, 
    rds_c: f_rds
}

for col, val in f_logic.items():
    if val != "All" and col in filt_df.columns: 
        filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# 5. MODULE 0: WELCOME
if selected_page == "WELCOME":
    st.markdown("""
    <div style="text-align: center; padding-bottom: 20px;">
        <img src="https://raw.githubusercontent.com/dxcentral/fm-dx-dashboard/main/SEDAP%20Banner.png" style="max-width: 600px; width: 100%;">
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #D32F2F; font-size: 3rem; margin-top: -10px;'>WELCOME TO SEDAP</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #FFA500; margin-top: -15px;'>Sporadic Es Data Analysis Project</h3>", unsafe_allow_html=True)
    st.markdown("---")
    
    col_text, col_info = st.columns([2.5, 1])
    
    with col_text:
        st.markdown("""
        <div class="welcome-text">
        For years, analysis of Sporadic Es receptions on the FM band has been largely a siloed effort.<br><br>
        
        Historically, this has meant DXers analyzing the data of receptions from their specific location, comparing season-over-season and gauging quality of seasons based on total logs or number of events. What if some locations are just more prone to Sporadic Es than others? What if some DXers just have better setups or have more time to DX?<br><br>
        
        <span class="welcome-highlight">Clearly, we need more data.</span><br><br>
        
        Further, we have seen over the past decade or two an explosion in the amount of resources available to DXers. Sites such as FMList.org and the Worldwide TV-FM DX Association (WTFDA)'s WLogger that provide real-time maps of receptions and sometimes email alerts for possible Sporadic Es propagation in a specific location. Sites such as Rabbitears and the RDS autologging maps that allow for unattended RDS decode logging of receptions through always-on receivers.<br><br>
        
        We haven't even mentioned the explosion of the use of Software-Defined Radio (SDR) technology that provides DXers with not only visual representations of their FM band, but the ability to record a portion or even the entire FM band for later review and logging of every single station received during an opening.<br><br>
        
        In recent years, we have seen a vast expansion of online FM DX receivers through sources such as FMDX.org that allow DXers to hear "first hand" the FM band in various locations all around the world and even spot openings using other locations as a beacon.<br><br>
        
        So, it is in that spirit that here at DX Central we decided it was time to collect all of that newly created data from the tens of thousands of FM Sporadic Es logs over the past decade or so.<br><br>
        
        We decided to start with North America, as that was the data that was most easily digestible and available to us from our partners at FMlist.org.<br><br>
        
        To our knowledge, this represents the first widespread and collective analysis of Sporadic Es logs from a large enough sample size to be able to spot trends and provide what we hope is a directionally accurate analysis.<br><br>
        
        We hope it helps provide insight for you not only into the historical performance of Sporadic Es seasons, but show you what is possible from your location, or in any given season. We can't predict Sporadic Es (yet!) but maybe we can at least shine some light on how a typical season behaves and unfolds.
        </div>
        """, unsafe_allow_html=True)
        
    with col_info:
        st.info("""
        ### 🧭 How To Use This Dashboard
        
        1. **Navigate Modules:** Click on the data modules on the sidebar at the left to view different categories of forensic data.
        2. **Sub-Sections:** On some pages, there are multiple sections, so look for section buttons (pills) to navigate to those specific views.
        3. **Interactive Intel:** Most of the data is interactive. Try clicking on charts, map locations, and bar graphs to see if a dedicated flyout of tactical intelligence is available!
        """)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="background-color: #111; padding: 20px; border-radius: 10px; border-left: 4px solid #D32F2F;">
        <h4 style="color: #D32F2F; margin-top: 0;">SPECIAL THANKS TO...</h4>
        <ul style="color: #DDD; font-weight: 300;">
            <li><b>Gunter Lorenz</b> at FMList.org for making their logging data available for analysis.</li>
            <li><b>The WTFDA</b> and their detailed station database that gives us actionable intelligence on stations.</li>
            <li><b>Mike Jeziorski</b> for his partnership in obtaining the data needed for this analysis.</li>
            <li>This dashboard is custom coded using Python into a Streamlit app. None of that is something I have ever had experience with, so I absolutely could not have accomplished this endeavor without the help of my trusted AI partner, Google Gemini <i>(Thanks, G!)</i></li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #888;">
    This is version 3.0 of our Es Data Dashboard. We are already planning the next data components we want to add, new data sources to add to our logging data, expanding beyond just the traditional FM season and more! Make sure to bookmark this site and check back often!<br><br>
    Thank you and best of DX!<br>
    <span style="color: #D32F2F; font-weight: bold;">Loyd Van Horn</span><br>
    DX Central<br>
    Mandeville, Louisiana
    </div>
    """, unsafe_allow_html=True)

# 6. MODULE 1: DASHBOARD OVERVIEW
elif selected_page == "DASHBOARD OVERVIEW":
    st.header("Operational Overview")
    m = st.columns(8)
    m[0].metric("Total Logs", f"{len(filt_df):,}")
    m[1].metric("Unique Stations", f"{filt_df['Station'].nunique():,}")
    m[2].metric("Unique DXers", f"{filt_df['DXer'].nunique():,}")
    m[3].metric("US States Heard", filt_df[filt_df['Country'] == 'USA']['State'].nunique())
    m[4].metric("Canadian Provinces", filt_df[filt_df['Country'] == 'Canada']['State'].nunique())
    m[5].metric("Mexican States", filt_df[filt_df['Country'] == 'Mexico']['State'].nunique())
    m[6].metric("Countries Heard", filt_df['Country'].nunique())
    m[7].metric("Furthest Reception", f"{filt_df[d_col].max() if not filt_df.empty else 0:,.0f} mi")
    
    st.dataframe(filt_df[['Local_Date', 'Local_Time', 'Frequency', 'Station', 'City', 'State', 'Country', 'DXer', d_col]].head(100), use_container_width=True, hide_index=True)

# 7. MODULE 2: ES-CLOUD TRACKER
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
        timeline = map_df.sort_values('DateTime_Key')
        time_steps = timeline[['Date_Str', 'Time_Str']].drop_duplicates().values.tolist()
        
        pb1, pb2, pb_txt = st.columns([1, 1, 3])
        if pb1.button("▶ PLAY"): 
            st.session_state.playing = True
            st.session_state.p_idx = 0
            st.rerun()
        if pb2.button("⏹ STOP"): 
            st.session_state.playing = False
            st.rerun()
        
        if st.session_state.playing:
            cur_step = time_steps[st.session_state.p_idx]
            cur_date, cur_time = cur_step[0], cur_step[1]
        else:
            times_only = sorted(map_df['Time_Str'].unique())
            cur_time = hc2.select_slider("Time Control", options=["SHOW ALL"] + times_only, value="SHOW ALL")
            cur_date = "N/A"

        if cur_time == "SHOW ALL":
            pb_txt.write("## 🕒 VIEWING: ALL SELECTED DATA")
        else:
            display_date = f"{cur_date} | " if cur_date != "N/A" else ""
            pb_txt.write(f"## 🕒 {display_date}{cur_time}")

        if cur_time == "SHOW ALL":
            render_df = map_df
        else:
            lookback_time_str = (datetime.datetime.strptime(cur_time, '%H:%M') - datetime.timedelta(minutes=30)).strftime('%H:%M')
            if st.session_state.playing:
                render_df = map_df[(map_df['Date_Str'] == cur_date) & (map_df['Time_Str'] <= cur_time) & (map_df['Time_Str'] >= lookback_time_str)]
            else:
                render_df = map_df[(map_df['Time_Str'] <= cur_time) & (map_df['Time_Str'] >= lookback_time_str)]
        
        # User requested exception: keep this Red = Low, White = High
        layers = [pdk.Layer(
            'HeatmapLayer' if vm == "Es Cloud Location Heatmap" else 'LineLayer', 
            data=render_df[['Final_Mid_Lat', 'Final_Mid_Lon']].dropna() if vm == "Es Cloud Location Heatmap" else render_df[[dx_lat_f, dx_lon_f, st_lat_f, st_lon_f]].dropna(), 
            get_position='[Final_Mid_Lon, Final_Mid_Lat]' if vm == "Es Cloud Location Heatmap" else None, 
            get_source_position=f'[{dx_lon_f}, {dx_lat_f}]' if vm != "Es Cloud Location Heatmap" else None, 
            get_target_position=f'[{st_lon_f}, {st_lat_f}]' if vm != "Es Cloud Location Heatmap" else None, 
            radius_pixels=65, intensity=2.0, threshold=0.03, 
            color_range=[[183, 28, 28, 60], [211, 47, 47, 150], [244, 67, 54, 200], [255, 235, 238, 230], [255, 255, 255, 255]] if vm == "Es Cloud Location Heatmap" else None, 
            get_width=1, get_color=map_line_color
        )]
                            
        st.pydeck_chart(pdk.Deck(map_style=map_style_url, initial_view_state=pdk.ViewState(latitude=32, longitude=-95, zoom=3.4), layers=layers))
        st.markdown("""<div class="watermark"><img src="https://raw.githubusercontent.com/dxcentral/fm-dx-dashboard/main/SEDAP%20Banner.png" style="width: 250px;"></div>""", unsafe_allow_html=True)
        
        if st.session_state.playing:
            conf = speed_sets[play_speed]
            if st.session_state.p_idx + conf['step'] < len(time_steps):
                st.session_state.p_idx += conf['step']
                time.sleep(conf['delay'])
                st.rerun()
            else:
                st.session_state.playing = False
                st.rerun()

# 8. MODULE 3: GEOGRAPHIC ANALYSIS
elif selected_page == "GEOGRAPHIC ANALYSIS":
    st.markdown("<h2 style='text-align: center; color: #D32F2F;'>GEOGRAPHIC ANALYSIS SUITE</h2>", unsafe_allow_html=True)
    gv = st.pills("MODULE", options=["International Stats", "Canadian Stats", "US States", "US Counties", "Distance Stats"], default="US States")
    st.markdown("---")
    geo_df = filt_df.copy()
    geo_df = geo_df[geo_df['State'] != 'AM']

    if gv == "Distance Stats":
        col_m, col_f = st.columns([3, 1]) if st.session_state.selected_tier else st.columns([1, 0.001])
        with col_m:
            st.markdown("### DISTANCE DISTRIBUTION HUB")
            st.caption("👈 Click on a Distance Distribution category for more details and statistics")
            d_counts = geo_df.groupby(dd_col).size().reset_index(name='Logs').dropna().sort_values('Logs', ascending=False)
            
            if not d_counts.empty:
                fig_hub = px.bar(d_counts, x='Logs', y=dd_col, orientation='h', color='Logs', color_continuous_scale=global_color_scale, template=plotly_tmpl)
                fig_hub.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=400, showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(showgrid=False))
                ev_hub = st.plotly_chart(fig_hub, use_container_width=True, on_select="rerun", key=f"dist_hub_{st.session_state.dist_map_key}")
                if ev_hub and "selection" in ev_hub and ev_hub["selection"]["points"]:
                    nt = ev_hub["selection"]["points"][0]["y"]
                    if st.session_state.selected_tier != nt: 
                        st.session_state.selected_tier = nt
                        st.rerun()
                        
            pulse_data = geo_df.groupby(['Local_Month', dd_col]).size().reset_index(name='Logs')
            fig_pulse = px.area(pulse_data, x='Local_Month', y='Logs', color=dd_col, groupnorm='percent', line_shape='spline', color_discrete_sequence=['#D32F2F', '#FFA500', '#FFFFFF', '#888888'], template=plotly_tmpl)
            st.plotly_chart(fig_pulse, use_container_width=True)
            
        if st.session_state.selected_tier:
            with col_f:
                tier = st.session_state.selected_tier
                st.markdown(f"### {tier.upper()} INTEL")
                if st.button("❌ CLEAR SELECTION", key="cl_dst", use_container_width=True): 
                    st.session_state.selected_tier = None
                    st.session_state.dist_map_key += 1
                    st.rerun()
                    
                s_of = geo_df[geo_df[dd_col] == tier]
                st.markdown('<div class="stat-header">TOTAL LOGS IN TIER</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{len(s_of):,}</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="stat-header">LIKELIHOOD SCORE</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{(s_of["DXer"].nunique() / geo_df["DXer"].nunique()) * 100:.1f}%</div><div class="stat-label">Of DXers have caught this</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="stat-header">TIER KINGS</div>', unsafe_allow_html=True)
                st.dataframe(s_of.groupby('DXer').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)
                
                st.markdown('<div class="stat-header">ORIGIN HOTSPOTS</div>', unsafe_allow_html=True)
                st.dataframe(s_of.groupby('State').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)
                
                st.markdown('<div class="stat-header">TOP 5 STATIONS</div>', unsafe_allow_html=True)
                t5 = s_of.groupby(['Frequency', 'Station']).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                t5['M'] = t5['L']
                st.dataframe(t5, column_config={"Frequency":"MHz", "L":st.column_config.NumberColumn("Logs", format="%d"), "M":st.column_config.ProgressColumn("", format="%d", min_value=0, max_value=int(t5['L'].max() if not t5.empty else 100))}, hide_index=True)
    
    elif gv == "US Counties":
        st.markdown("### 🗺️ US COUNTY LOG HEATMAP")
        if 'FIPS' not in geo_df.columns:
            st.warning("🚨 **County Intelligence Offline**")
            st.markdown("""
            The current FMList database in BigQuery has not yet been linked to the US Census geometry shapefiles. 
            
            **To unlock this feature:**
            Your FMList coordinate database requires a standard `FIPS` code column matching the spatial join we just built for WTFDA. We will establish this database link in the next phase! 
            """)
        else:
            col_m, col_f = st.columns([3, 1]) if st.session_state.selected_logged_county else st.columns([1, 0.001])
            with col_m:
                county_df = geo_df[geo_df['Country'] == 'USA'].dropna(subset=['FIPS', 'County']).copy()
                county_df['Type'] = np.where(county_df['State'] == 'LA', ' Parish, ', ' County, ')
                counts = county_df.groupby(['FIPS', 'County', 'State', 'Type']).size().reset_index(name='Logs')
                counts['Hover_Name'] = counts['County'] + counts['Type'] + counts['State']
                
                fig = px.choropleth(counts, geojson='https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json', locations='FIPS', color='Logs', scope='usa', color_continuous_scale=global_color_scale, hover_name='Hover_Name', template=plotly_tmpl)
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor=th_bg), margin={"r":0,"t":0,"l":0,"b":0}, height=750)
                ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=f"m_county_{st.session_state.logged_county_map_key}")
                
                if ev and ev.get("selection") and ev["selection"].get("points"):
                    sel_fips = ev["selection"]["points"][0]["location"]
                    if st.session_state.selected_logged_county != sel_fips:
                        st.session_state.selected_logged_county = sel_fips
                        st.rerun()
            
            if st.session_state.selected_logged_county:
                with col_f:
                    fips_target = st.session_state.selected_logged_county
                    c_data = county_df[county_df['FIPS'] == fips_target]
                    c_name = c_data['County'].iloc[0] if not c_data.empty else "Unknown"
                    c_state = c_data['State'].iloc[0] if not c_data.empty else "XX"
                    c_type = "PARISH" if c_state == 'LA' else "COUNTY"
                    
                    st.markdown(f"### {c_name.upper()} {c_type} INTEL")
                    if st.button("❌ CLEAR SELECTION", key="cl_c_map", use_container_width=True): 
                        st.session_state.selected_logged_county = None
                        st.session_state.logged_county_map_key += 1
                        st.rerun()
                        
                    # --- TARGET LOCK MINIMAP ---
                    st.markdown('<div class="stat-header">TARGET LOCK MINIMAP</div>', unsafe_allow_html=True)
                    state_map_df = county_df[county_df['State'] == c_state].dropna(subset=['FIPS']).groupby('FIPS').size().reset_index(name='Logs')
                    state_map_df['Highlight'] = np.where(state_map_df['FIPS'] == fips_target, 'Target', 'Other')
                    
                    fig_mini = px.choropleth(state_map_df, geojson='https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json', locations='FIPS', color='Highlight', color_discrete_map={'Target': th_red, 'Other': th_panel})
                    fig_mini.update_geos(fitbounds="locations", visible=False)
                    fig_mini.update_layout(showlegend=False, margin={"r":0,"t":10,"l":0,"b":10}, height=200, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_mini, use_container_width=True)

                    s_of = c_data
                    s_fr = geo_df[geo_df['FIPS_DXer'] == fips_target] if 'FIPS_DXer' in geo_df.columns else pd.DataFrame()
                        
                    st.markdown('<div class="stat-header">TOTAL LOGS IN DATASET</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{len(s_of):,}</div>', unsafe_allow_html=True)
                    
                    if not s_of.empty:
                        top_st = s_of.groupby(['Frequency', 'Station', 'City']).size().idxmax()
                        st.markdown('<div class="stat-header">MOST HEARD STATION</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-val">{top_st[1]}</div><div class="stat-label">{top_st[0]} MHz • {top_st[2]} • {s_of.groupby(["Frequency", "Station", "City"]).size().max()} Logs</div>', unsafe_allow_html=True)
                        
                        st.markdown('<div class="stat-header">PEAK SEASONALITY</div>', unsafe_allow_html=True)
                        m_c, y_c = s_of[m_name_col].value_counts(), s_of[y_col].value_counts()
                        st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Month</div><div class="stat-val" style="margin-top:0px;">{str(m_c.idxmax()).upper()} ({m_c.max()})</div></div>', unsafe_allow_html=True)
                        st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Year</div><div class="stat-val" style="margin-top:0px;">{y_c.idxmax()} ({y_c.max()})</div></div>', unsafe_allow_html=True)
                        
                        st.markdown('<div class="window-box">', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-label" style="color:{th_red}">Season Window - Stations From Region</div>', unsafe_allow_html=True)
                        od = pd.to_datetime(s_of['Local_Date'])
                        st.markdown(f'<div class="stat-label">Start: {get_avg_date(od.groupby(s_of[y_col]).min())} | Peak: {get_avg_date(od)} | End: {get_avg_date(od.groupby(s_of[y_col]).max())}</div>', unsafe_allow_html=True)
                        
                        if not s_fr.empty:
                            st.markdown(f'<div class="stat-label" style="color:{th_red}">Season Window - DXers In Region</div>', unsafe_allow_html=True)
                            fd = pd.to_datetime(s_fr['Local_Date'])
                            st.markdown(f'<div class="stat-label">Start: {get_avg_date(fd.groupby(s_fr[y_col]).min())} | Peak: {get_avg_date(fd)} | End: {get_avg_date(fd.groupby(s_fr[y_col]).max())}</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True)
                        f = s_of.sort_values(d_col, ascending=False).iloc[0]
                        st.markdown(f'<div class="stat-val">{f[d_col]:,.0f} MILES</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-label">{f["Frequency"]} - {f["Station"]} by {f["DXer"]}, {f[dx_loc_col]} on {f["Date_Str"]} at {f["Local_Time"]}</div>', unsafe_allow_html=True)
                    
                    if not s_fr.empty:
                        st.markdown('<div class="stat-header">LOCAL DXER ACTIVITY</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-val">{s_fr["DXer"].nunique()} UNIQUE DXERS</div>', unsafe_allow_html=True)
                        
                        st.markdown('<div class="stat-header">TOP RECEPTION PATHS</div>', unsafe_allow_html=True)
                        st.dataframe(s_fr.groupby('State').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)
                    
                    st.markdown('<div class="stat-header">TOP TRANSMISSION PATHS</div>', unsafe_allow_html=True)
                    st.dataframe(s_of.groupby(dx_st_col).size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)
                    
                    st.markdown('<div class="stat-header">TOP 5 STATIONS</div>', unsafe_allow_html=True)
                    t5 = s_of.groupby(['Frequency', 'Station']).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                    t5['M'] = t5['L']
                    st.dataframe(t5, column_config={"Frequency":"MHz", "L":st.column_config.NumberColumn("Logs", format="%d"), "M":st.column_config.ProgressColumn("", format="%d", min_value=0, max_value=int(t5['L'].max() if not t5.empty else 100))}, hide_index=True)

            # --- TARGET LIST FOR UNHEARD COUNTIES ---
            st.markdown("---")
            st.markdown(f"<h3 style='color: {th_red}; text-align: center; letter-spacing: 2px;'>🎯 UNHEARD COUNTY HIT LIST</h3>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align: center; color: {th_gray}; margin-bottom: 30px;'>Counties with active FM transmitters that have never been logged in the current dataset.<br>Click any target below to instantly teleport to its WTFDA Intelligence Report.</div>", unsafe_allow_html=True)
            
            wtfda_df_all = load_wtfda_data()
            if not wtfda_df_all.empty and 'FIPS' in wtfda_df_all.columns:
                if 'FIPS' in county_df.columns:
                    logged_fips = county_df['FIPS'].unique().tolist()
                else:
                    logged_fips = []
                    
                us_wtfda = wtfda_df_all[wtfda_df_all['Country'] == 'USA'].dropna(subset=['FIPS', 'County']).copy()
                
                # --- DATA SHIELD FOR DUPLICATE FIPS ---
                us_wtfda['County'] = us_wtfda['County'].astype(str).str.title().str.strip()
                avail_counties = us_wtfda.groupby(['FIPS', 'County', 'S/P']).size().reset_index(name='Stations')
                
                # Force strictly unique FIPS to prevent Streamlit DuplicateKey errors from WTFDA typos
                avail_counties = avail_counties.groupby('FIPS', as_index=False).agg({
                    'County': 'first',
                    'S/P': 'first',
                    'Stations': 'sum'
                })
                
                unheard = avail_counties[~avail_counties['FIPS'].isin(logged_fips)]
                
                if unheard.empty:
                    st.success("100% Penetration! Every county with a transmitter has been logged.")
                else:
                    unheard_by_state = unheard.groupby('S/P')
                    for state, state_data in sorted(unheard_by_state):
                        sorted_state_data = state_data.sort_values('County')
                        l_type = "PARISHES" if state == 'LA' else "COUNTIES"
                        
                        st.markdown(f'<div class="stat-header" style="border-bottom: 1px solid {th_red}; font-size: 1.1rem; margin-top: 25px; margin-bottom: 15px;">{state} <span style="color: {th_gray}; font-size: 0.9rem;">({len(sorted_state_data)} {l_type})</span></div>', unsafe_allow_html=True)
                        
                        n_cols = 4
                        cols = st.columns(n_cols)
                        
                        for idx, (_, row) in enumerate(sorted_state_data.iterrows()):
                            col_idx = idx % n_cols
                            btn_label = f"{row['County']} ({row['Stations']})"
                            cols[col_idx].button(btn_label, key=f"uh_btn_{row['FIPS']}_{idx}", on_click=jump_to_county, args=(row['FIPS'],), use_container_width=True)

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
                fig = px.choropleth(counts, locations='MapCountry', locationmode="country names", color='Logs', color_continuous_scale=global_color_scale, template=plotly_tmpl)
                fig.update_geos(projection_type="equirectangular", visible=True, lataxis_range=[-45, 75], lonaxis_range=[-130, 20])
            else:
                c_data = geo_df[geo_df['Country'] == target]
                cam = {'ON':'Ontario','QC':'Quebec','NS':'Nova Scotia','NB':'New Brunswick','MB':'Manitoba','BC':'British Columbia','PE':'Prince Edward Island','SK':'Saskatchewan','AB':'Alberta','NL':'Newfoundland and Labrador','NU':'Nunavut','NT':'Northwest Territories','YT':'Yukon'} if target == 'Canada' else {}
                c_data['MapLoc'] = c_data['State'].map(cam) if target == 'Canada' else c_data['State']
                counts = c_data.groupby('MapLoc').size().reset_index(name='Logs').dropna()
                fig = px.choropleth(counts, geojson=gj_url, locations='MapLoc', featureidkey=gj_key, locationmode=loc_mode, color='Logs', scope=scope, color_continuous_scale=global_color_scale, template=plotly_tmpl)
                if target != 'USA': fig.update_geos(fitbounds="locations", visible=True, showsubunits=True, subunitcolor=th_border)
                    
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor=th_bg), margin={"r":0,"t":0,"l":0,"b":0}, height=750)
            ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=f"m_{gv}_{st.session_state.map_key}")
            
            if ev and ev.get("selection") and ev["selection"].get("points"):
                raw = ev["selection"]["points"][0]["location"]
                new_sel = raw
                if target == 'Canada': 
                    inv = {v: k for k, v in cam.items()}
                    new_sel = inv.get(raw, raw)
                if st.session_state.selected_state != new_sel: 
                    st.session_state.selected_state = new_sel
                    st.rerun()
                    
        if st.session_state.selected_state:
            with col_f:
                sel = st.session_state.selected_state
                st.markdown(f"### {sel} INTEL")
                if st.button("❌ CLEAR SELECTION", key="cl_map", use_container_width=True): 
                    st.session_state.selected_state = None
                    st.session_state.map_key += 1
                    st.rerun()
                    
                if target == 'World': s_of, s_fr = geo_df[geo_df['MapCountry'] == sel], geo_df[geo_df['DXer_Country'] == sel]
                else: s_of, s_fr = geo_df[geo_df['Country'] == target][geo_df['State'] == sel], geo_df[geo_df[dx_st_col] == sel]
                    
                st.markdown('<div class="stat-header">TOTAL LOGS IN DATASET</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{len(s_of):,}</div>', unsafe_allow_html=True)
                
                if not s_of.empty:
                    top_st = s_of.groupby(['Frequency', 'Station', 'City']).size().idxmax()
                    st.markdown('<div class="stat-header">MOST HEARD STATION</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{top_st[1]}</div><div class="stat-label">{top_st[0]} MHz • {top_st[2]} • {s_of.groupby(["Frequency", "Station", "City"]).size().max()} Logs</div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="stat-header">PEAK SEASONALITY</div>', unsafe_allow_html=True)
                    m_c, y_c = s_of[m_name_col].value_counts(), s_of[y_col].value_counts()
                    st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Month</div><div class="stat-val" style="margin-top:0px;">{str(m_c.idxmax()).upper()} ({m_c.max()})</div></div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Year</div><div class="stat-val" style="margin-top:0px;">{y_c.idxmax()} ({y_c.max()})</div></div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="window-box">', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-label" style="color:{th_red}">Season Window - Stations From Region</div>', unsafe_allow_html=True)
                    od = pd.to_datetime(s_of['Local_Date'])
                    st.markdown(f'<div class="stat-label">Start: {get_avg_date(od.groupby(s_of[y_col]).min())} | Peak: {get_avg_date(od)} | End: {get_avg_date(od.groupby(s_of[y_col]).max())}</div>', unsafe_allow_html=True)
                    
                    st.markdown(f'<div class="stat-label" style="color:{th_red}">Season Window - DXers In Region</div>', unsafe_allow_html=True)
                    fd = pd.to_datetime(s_fr['Local_Date'])
                    st.markdown(f'<div class="stat-label">Start: {get_avg_date(fd.groupby(s_fr[y_col]).min())} | Peak: {get_avg_date(fd)} | End: {get_avg_date(fd.groupby(s_fr[y_col]).max())}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True)
                    f = s_of.sort_values(d_col, ascending=False).iloc[0]
                    st.markdown(f'<div class="stat-val">{f[d_col]:,.0f} MILES</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-label">{f["Frequency"]} - {f["Station"]} by {f["DXer"]}, {f[dx_loc_col]} on {f["Date_Str"]} at {f["Local_Time"]}</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="stat-header">LOCAL DXER ACTIVITY</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{s_fr["DXer"].nunique()} UNIQUE DXERS</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="stat-header">TOP RECEPTION PATHS</div>', unsafe_allow_html=True)
                st.dataframe(s_fr.groupby('State' if target != 'World' else 'Country').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)
                
                st.markdown('<div class="stat-header">TOP TRANSMISSION PATHS</div>', unsafe_allow_html=True)
                st.dataframe(s_of.groupby(dx_st_col if target != 'World' else 'DXer_Country').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)
                
                st.markdown('<div class="stat-header">TOP 5 STATIONS</div>', unsafe_allow_html=True)
                t5 = s_of.groupby(['Frequency', 'Station']).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                t5['M'] = t5['L']
                st.dataframe(t5, column_config={"Frequency":"MHz", "L":st.column_config.NumberColumn("Logs", format="%d"), "M":st.column_config.ProgressColumn("", format="%d", min_value=0, max_value=int(t5['L'].max() if not t5.empty else 100))}, hide_index=True)

# 9. MODULE 4: TEMPORAL TRENDS
elif selected_page == "TEMPORAL TRENDS":
    st.header("Temporal Intelligence Suite")
    tv = st.pills("MODULE", options=["Yearly Trends", "Monthly Almanac", "Hourly Analysis"], default="Hourly Analysis")
    st.info("⚠️ TIME SYNC NOTE: All temporal data is expressed in the Local Time of the DXer’s receiver location.")
    st.markdown("---")
    
    if tv == "Hourly Analysis":
        col_m, col_f = st.columns([3, 1]) if st.session_state.selected_hour is not None else st.columns([1, 0.001])
        with col_m:
            st.markdown("### DIURNAL VOLUME CURVE & HISTORY TIMELINE")
            st.caption("👈 CLICK ANY BAR OR POINT TO ANALYZE HOURLY INTELLIGENCE")
            h_data = filt_df.groupby(h_col).size().reset_index(name='Logs').sort_values(h_col)
            fig_h = go.Figure()
            fig_h.add_trace(go.Bar(x=h_data[h_col], y=h_data['Logs'], name='Log Volume', marker_color=th_red, opacity=0.3, hoverinfo='x+y'))
            fig_h.add_trace(go.Scatter(x=h_data[h_col], y=h_data['Logs'], mode='markers+lines', name='Hour Mark', marker=dict(size=12, color=th_red, line=dict(width=2, color='white')), line=dict(width=1, color=th_border)))
            fig_h.update_layout(template=plotly_tmpl, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=600, showlegend=False, xaxis=dict(title="Local Hour (0-23)", tickmode='array', tickvals=list(range(24)), range=[-0.5, 23.5], rangeslider=dict(visible=True), type='linear'), yaxis=dict(title="Total Log Volume", showgrid=False))
            ev_hour = st.plotly_chart(fig_h, use_container_width=True, on_select="rerun", key=f"h_chart_{st.session_state.hour_map_key}")
            
            if ev_hour and "selection" in ev_hour and ev_hour["selection"]["points"]:
                new_h = int(ev_hour["selection"]["points"][0]["x"])
                if st.session_state.selected_hour != new_h: 
                    st.session_state.selected_hour = new_h
                    st.rerun()
                    
        if st.session_state.selected_hour is not None:
            with col_f:
                h = st.session_state.selected_hour
                st.markdown(f"### HOUR {h:02d}:00 INTEL")
                if st.button("❌ CLEAR HOUR", key="cl_hr", use_container_width=True): 
                    st.session_state.selected_hour = None
                    st.session_state.hour_map_key += 1
                    st.rerun()
                    
                s_h = filt_df[filt_df[h_col].astype(int) == int(h)]
                st.markdown('<div class="stat-header">HOUR MISSION SUMMARY</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{len(s_h):,} LOGS</div><div class="stat-label">{(len(s_h)/len(filt_df))*100:.1f}% of Global Volume</div>', unsafe_allow_html=True)
                
                if not s_h.empty:
                    st.markdown('<div class="stat-header">PEAK SEASONALITY</div>', unsafe_allow_html=True)
                    m_h, y_h = s_h[m_name_col].value_counts(), s_h[y_col].value_counts()
                    st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Month</div><div class="stat-val" style="margin-top:0px;">{str(m_h.idxmax()).upper()} ({m_h.max()})</div></div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Year</div><div class="stat-val" style="margin-top:0px;">{y_h.idxmax()} ({y_h.max()})</div></div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="stat-header">LOCATION DOMINANCE</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{s_h[dx_loc_col].mode().iloc[0]}</div><div class="stat-label">Most Active DXer Location</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{s_h["State"].mode().iloc[0]}</div><div class="stat-label">Most Active Station State</div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="stat-header">TOP 5 PATHS (DXER ➔ STATION STATE/PROV)</div>', unsafe_allow_html=True)
                    paths = s_h.groupby([dx_st_col, 'State']).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                    paths['Path'] = paths[dx_st_col].astype(str) + " ➔ " + paths['State'].astype(str)
                    st.dataframe(paths[['Path', 'L']], column_config={"L": st.column_config.ProgressColumn("", format="%d")}, hide_index=True)
                    
                    st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True)
                    f = s_h.sort_values(d_col, ascending=False).iloc[0]
                    st.markdown(f'<div class="stat-val">{f[d_col]:,.0f} MILES</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-label">{f["Frequency"]} - {f["Station"]} by {f["DXer"]}, {f[dx_loc_col]} on {f["Date_Str"]} at {f["Local_Time"]}</div>', unsafe_allow_html=True)

    elif tv == "Monthly Almanac":
        st.markdown("### MONTHLY LOG ALMANAC")
        st.caption("Select a month to view seasonal density. Pick a date below to view tactical reports.")
        sel_m_name = st.pills("SELECT MONTH", ["May", "June", "July", "August"], default=st.session_state.almanac_month)
        st.session_state.almanac_month = sel_m_name
        avail_m_df = filt_df[filt_df[m_name_col] == sel_m_name]
        
        if not avail_m_df.empty:
            st.markdown("#### 📅 TACTICAL DATE FORENSICS")
            sel_date = st.date_input("SELECT DATE FOR INTEL REPORT", value=None, min_value=avail_m_df['Date_Obj'].min(), max_value=avail_m_df['Date_Obj'].max())
            cm, ci = st.columns([3, 1]) if sel_date else st.columns([1, 0.001])
            with cm:
                pivot = avail_m_df.pivot_table(index=dom_col, columns=y_col, values='Station', aggfunc='count').fillna(0).astype(int).reindex(range(1, 32), fill_value=0)
                pivot['TOTAL LOGS'] = pivot.sum(axis=1)
                pivot['ACTIVE YEARS'] = (pivot.drop(columns=['TOTAL LOGS']) > 0).sum(axis=1)
                pivot['AVG/YR'] = (pivot['TOTAL LOGS'] / pivot['ACTIVE YEARS']).replace([np.inf, -np.inf], 0).fillna(0).round(0).astype(int)
                
                f_rows = ['TOTAL LOGS', 'ACTIVE DAYS', 'AVG/DAY', 'DAYS >= 100', 'DAYS >= 500']
                footer = pd.DataFrame(index=f_rows, columns=pivot.columns).fillna(0)
                
                for col in pivot.columns:
                    d_slice = pivot.loc[1:31, col]
                    active_count = (d_slice > 0).sum()
                    footer.at['TOTAL LOGS', col] = int(d_slice.sum())
                    footer.at['ACTIVE DAYS', col] = int(active_count)
                    footer.at['AVG/DAY', col] = int(round(d_slice.sum() / active_count if active_count > 0 else 0))
                    footer.at['DAYS >= 100', col] = int((d_slice >= 100).sum())
                    footer.at['DAYS >= 500', col] = int((d_slice >= 500).sum())
                    
                final_pivot = pd.concat([pivot, footer]).reset_index().rename(columns={'index': 'DAY/METRIC'})
                
                def style_almanac(df):
                    styles = pd.DataFrame('', index=df.index, columns=df.columns)
                    core_y = [c for c in df.columns if str(c).isdigit()]
                    core_matrix = df.iloc[:31].get(core_y, pd.DataFrame())
                    max_v = core_matrix.max().max() if not core_matrix.empty else 100
                    
                    for r_idx in df.index:
                        label = df.at[r_idx, 'DAY/METRIC']
                        for c in df.columns:
                            val = df.at[r_idx, c]
                            if isinstance(label, int) and 1 <= label <= 31 and c in core_y:
                                if val > 0:
                                    rel = val / max_v
                                    bg = '#FFFF00' if rel > 0.8 else ('#FFA500' if rel > 0.5 else ('#D32F2F' if rel > 0.2 else '#640000'))
                                    fg = 'black' if rel > 0.5 else 'white'
                                    styles.at[r_idx, c] = f'background-color: {bg}; color: {fg};'
                            else: 
                                styles.at[r_idx, c] = f'background-color: {th_bg}; color: {th_text}; font-weight: bold;'
                    return styles
                    
                st.dataframe(final_pivot.style.apply(style_almanac, axis=None), use_container_width=True, height=1250, hide_index=True)
                
            if sel_date:
                with ci:
                    st.markdown(f"### 📡 TACTICAL REPORT: {sel_date.strftime('%b %d, %Y')}")
                    s_day = avail_m_df[avail_m_df['Date_Obj'] == sel_date]
                    if not s_day.empty:
                        st.metric("Total Logs", f"{len(s_day):,}")
                        st.metric("MUF Recorded", f"{s_day['Frequency'].max()} MHz")
                        st.metric("Unique DXers", s_day['DXer'].nunique())
                        
                        st.markdown('<div class="stat-header">LOCATION DOMINANCE</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-val">{s_day[dx_loc_col].mode().iloc[0]}</div><div class="stat-label">Most Active DXer Location</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-val">{s_day["State"].mode().iloc[0]}</div><div class="stat-label">Most Active Station State</div>', unsafe_allow_html=True)
                        
                        st.markdown('<div class="stat-header">TOP 5 PATHS (DXER ➔ STATION STATE/PROV)</div>', unsafe_allow_html=True)
                        m_paths = s_day.groupby([dx_st_col, 'State']).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                        m_paths['Path'] = m_paths[dx_st_col].astype(str) + " ➔ " + m_paths['State'].astype(str)
                        st.dataframe(m_paths[['Path', 'L']], hide_index=True)
                        
                        st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True)
                        f = s_day.sort_values(d_col, ascending=False).iloc[0]
                        st.markdown(f'<div class="stat-val">{f[d_col]:,.0f} MILES</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-label">{f["Frequency"]} - {f["Station"]} by {f["DXer"]}, {f[dx_loc_col]} on {f["Date_Str"]} at {f["Local_Time"]}</div>', unsafe_allow_html=True)
                        
                        intl = s_day[~s_day['Country'].isin(['USA', 'Canada'])]
                        if not intl.empty: 
                            st.markdown('<div class="stat-header">TOP INTERNATIONAL COUNTRIES</div>', unsafe_allow_html=True)
                            st.dataframe(intl.groupby('Country').size().reset_index(name='L').sort_values('L', ascending=False).head(3), hide_index=True)
                    else: 
                        st.warning("No signal intelligence for selected date.")
                        
        st.markdown("#### 📊 SEASONAL DENSITY MATRIX")
        st.caption("👈 Percentage of days in each month/year with at least one reported Es log. Red/Yellow intensity indicates high density.")
        m_days = {"May": 31, "June": 30, "July": 31, "August": 31}
        density_data = filt_df[filt_df[m_name_col].isin(list(m_days.keys()))]
        if not density_data.empty:
            years_v = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
            density_pivot = density_data.groupby([m_name_col, y_col])['Date_Obj'].nunique().unstack(fill_value=0).astype(float)
            density_pivot = density_pivot.reindex(columns=years_v, fill_value=0)
            
            for m in m_days:
                if m in density_pivot.index: 
                    density_pivot.loc[m] = (density_pivot.loc[m] / m_days[m]) * 100
                    
            density_pivot.loc['SEASON TOTAL'] = (density_data.groupby(y_col)['Date_Obj'].nunique() / 123) * 100
            density_pivot['AVERAGES'] = density_pivot.mean(axis=1)
            density_pivot.columns = [str(c) for c in density_pivot.columns]
            
            dens_text = density_pivot.map(lambda x: f"{x:.1f}%")
            fig_dens = px.imshow(density_pivot, text_auto=False, color_continuous_scale=global_color_scale, labels=dict(color="% Density"), template=plotly_tmpl)
            fig_dens.update_traces(text=dens_text.values, texttemplate="%{text}")
            fig_dens.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', coloraxis_showscale=False)
            st.plotly_chart(fig_dens, use_container_width=True)
            
        st.markdown("#### 🌎 INTERNATIONAL SEASONAL FLOW")
        st.caption("👈 Click anywhere on a country's horizontal bar for tactical intelligence.")
        intl_raw = filt_df[~filt_df['Country'].isin(['USA', 'Canada'])].copy()
        if not intl_raw.empty:
            intl_raw['Country'] = intl_raw['Country'].astype(str)
            intl_raw[m_name_col] = intl_raw[m_name_col].astype(str)
            intl_flow = intl_raw.groupby(['Country', m_name_col]).size().reset_index(name='Logs')
            intl_flow = intl_flow.sort_values('Country', ascending=False)
            
            col_intl_m, col_intl_f = st.columns([3, 1]) if st.session_state.selected_intl_country else st.columns([1, 0.001])
            with col_intl_m:
                fig_intl = px.bar(intl_flow, x='Logs', y='Country', color=m_name_col, orientation='h', template=plotly_tmpl, color_discrete_sequence=[th_dark_red, th_red, th_orange, th_yellow])
                fig_intl.update_layout(barnorm='percent', height=500, barmode='stack', clickmode='event+select', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_title="% Monthly Distribution")
                ev_intl = st.plotly_chart(fig_intl, use_container_width=True, on_select="rerun", key=f"intl_bar_{st.session_state.intl_map_key}")
                
                if ev_intl and ev_intl.get("selection") and ev_intl["selection"].get("points"):
                    new_intl = ev_intl["selection"]["points"][0]["y"]
                    if st.session_state.selected_intl_country != new_intl: 
                        st.session_state.selected_intl_country = new_intl
                        st.rerun()
                        
            if st.session_state.selected_intl_country:
                with col_intl_f:
                    c_sel = st.session_state.selected_intl_country
                    st.markdown(f"### {c_sel.upper()} INTEL")
                    if st.button("❌ CLEAR COUNTRY", use_container_width=True): 
                        st.session_state.selected_intl_country = None
                        st.session_state.intl_map_key += 1
                        st.rerun()
                        
                    c_df = intl_raw[intl_raw['Country'] == c_sel]
                    st.markdown('<div class="stat-header">MONTHLY DISTRIBUTION</div>', unsafe_allow_html=True)
                    c_grp = c_df.groupby(m_name_col).size().reset_index(name='Logs')
                    c_grp['% of Total'] = (c_grp['Logs'] / len(c_df)) * 100
                    c_grp['M'] = c_grp['% of Total']
                    st.dataframe(c_grp, column_config={m_name_col: "Month", "Logs": "Total Logs", "% of Total": st.column_config.NumberColumn("%", format="%.1f%%"), "M": st.column_config.ProgressColumn("", format="", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)
                    
                    st.markdown(f'<div class="stat-header">TOP 5 HUBS HEARING {c_sel.upper()}</div>', unsafe_allow_html=True)
                    intl_paths = c_df.groupby([dx_st_col]).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                    intl_paths['M'] = intl_paths['L']
                    st.dataframe(intl_paths, column_config={dx_st_col: "Origin State/Prov", "L": "Logs", "M": st.column_config.ProgressColumn("", format="", min_value=0, max_value=int(intl_paths['L'].max() if not intl_paths.empty else 10))}, hide_index=True, use_container_width=True)
                    
                    st.markdown('<div class="stat-header">PEAK SIGNAL INTEL</div>', unsafe_allow_html=True)
                    muf_row = c_df.sort_values('Frequency', ascending=False).iloc[0]
                    st.markdown(f'<div class="stat-val">{muf_row["Frequency"]} MHz</div><div class="stat-label">MAX MUF: {muf_row["Station"]} caught by {muf_row["DXer"]} ({muf_row[dx_loc_col]}) on {muf_row["Date_Str"]} at {muf_row["Local_Time"]} • {muf_row[d_col]:,.0f} MI</div>', unsafe_allow_html=True)
                    dist_row = c_df.sort_values(d_col, ascending=False).iloc[0]
                    st.markdown(f'<div class="stat-val">{dist_row[d_col]:,.0f} MILES</div><div class="stat-label">MAX DISTANCE: {dist_row["Frequency"]} MHz - {dist_row["Station"]} caught by {dist_row["DXer"]} ({dist_row[dx_loc_col]}) on {dist_row["Date_Str"]} at {dist_row["Local_Time"]}</div>', unsafe_allow_html=True)

    elif tv == "Yearly Trends":
        col_m, col_f = st.columns([3, 1]) if st.session_state.selected_year is not None else st.columns([1, 0.001])
        with col_m:
            st.markdown("### SEASONAL VOLUME TIMELINE")
            st.caption("👈 CLICK ANY BAR TO VIEW SEASON QUALITY & EFFICIENCY METRICS")
            y_data = filt_df.groupby(y_col).size().reset_index(name='Logs').sort_values(y_col)
            fig_y = go.Figure()
            fig_y.add_trace(go.Bar(x=y_data[y_col], y=y_data['Logs'], name='Log Volume', marker_color=th_red, opacity=0.3, hoverinfo='x+y'))
            fig_y.add_trace(go.Scatter(x=y_data[y_col], y=y_data['Logs'], mode='markers+lines', name='Year Mark', marker=dict(size=12, color=th_red, line=dict(width=2, color='white')), line=dict(width=1, color=th_border)))
            fig_y.update_layout(template=plotly_tmpl, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=600, showlegend=False, xaxis=dict(title="Local Year", rangeslider=dict(visible=True)), yaxis=dict(title="Total Log Volume", showgrid=False))
            
            ev_year = st.plotly_chart(fig_y, use_container_width=True, on_select="rerun", key=f"y_chart_{st.session_state.year_map_key}")
            if ev_year and "selection" in ev_year and ev_year["selection"]["points"]:
                ny = int(ev_year["selection"]["points"][0]["x"])
                if st.session_state.selected_year != ny: 
                    st.session_state.selected_year = ny
                    st.rerun()
        
        if st.session_state.selected_year is not None:
            with col_f:
                yr = st.session_state.selected_year
                st.markdown(f"### {yr} SEASON INTEL")
                if st.button("❌ CLEAR SELECTION", key="cl_yr", use_container_width=True): 
                    st.session_state.selected_year = None
                    st.session_state.year_map_key += 1
                    st.rerun()
                    
                s_y = filt_df[filt_df[y_col].astype(int) == int(yr)]
                st.markdown('<div class="stat-header">SEASON MISSION SUMMARY</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{len(s_y):,} LOGS</div>', unsafe_allow_html=True)
                
                u_dx = s_y['DXer'].nunique()
                eff = len(s_y) / u_dx if u_dx > 0 else 0
                st.markdown('<div class="stat-header">RECEIVER NETWORK</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{u_dx} UNIQUE DXERS</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="stat-header">SEASON EFFICIENCY INDEX</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{eff:.1f}</div><div class="stat-label">Logs per Active DXer</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="stat-header">STATION INTEL</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{s_y["Station"].nunique():,} UNIQUE STATIONS</div>', unsafe_allow_html=True)
                
                if not s_y.empty:
                    m_y = s_y[m_name_col].value_counts()
                    st.markdown('<div class="stat-header">PEAK SEASONALITY</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val" style="margin-top:0px;">{str(m_y.idxmax()).upper()} ({m_y.max()})</div><div class="stat-label">Highest Volume Month</div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="stat-header">GEOGRAPHIC SCOPE</div>', unsafe_allow_html=True)
                    gc = st.columns(2)
                    gc[0].metric("US States", s_y[s_y['Country'] == 'USA']['State'].nunique())
                    gc[0].metric("Can. Prov", s_y[s_y['Country'] == 'Canada']['State'].nunique())
                    gc[1].metric("Mex. States", s_y[s_y['Country'] == 'Mexico']['State'].nunique())
                    gc[1].metric("Countries", s_y['Country'].nunique())
                    
                    st.markdown('<div class="stat-header">TOP 5 CATCH PATHS (STATE ➔ STATE)</div>', unsafe_allow_html=True)
                    s_paths = s_y.groupby([dx_st_col, 'State']).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                    s_paths['Path'] = s_paths[dx_st_col].astype(str) + " ➔ " + s_paths['State'].astype(str)
                    st.dataframe(s_paths[['Path', 'L']], hide_index=True)
                    
                    st.markdown('<div class="stat-header">TOP 5 STATIONS</div>', unsafe_allow_html=True)
                    st.dataframe(s_y.groupby('Station').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)
                    
                    st.markdown('<div class="stat-header">TOP 5 MISSION DAYS</div>', unsafe_allow_html=True)
                    st.dataframe(s_y.groupby('Date_Str').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)
                    
                    f_y = s_y.sort_values(d_col, ascending=False).iloc[0]
                    st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{f_y[d_col]:,.0f} MILES</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-label">{f_y["Frequency"]} - {f_y["Station"]}, {f_y["City"]}, {f_y["State"]} by {f_y["DXer"]} ({f_y[dx_loc_col]}) on {f_y["Date_Str"]} at {f_y["Local_Time"]}</div>', unsafe_allow_html=True)
        
        # MACRO AUDITS SECTION
        st.markdown("---")
        st.markdown("### 📊 LONG-TERM SEASONAL PERFORMANCE AUDITS")
        r1, r2 = st.columns(2)
        with r1:
            st.markdown("#### Monthly Log Contribution (%)")
            m_cont = filt_df.groupby([y_col, m_name_col]).size().reset_index(name='L')
            fig_cont = px.bar(m_cont, x=y_col, y='L', color=m_name_col, template=plotly_tmpl, color_discrete_sequence=[th_dark_red, th_red, th_orange, th_yellow])
            fig_cont.update_layout(barnorm='percent', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_title="% Contribution", xaxis_title="Season")
            st.plotly_chart(fig_cont, use_container_width=True)
            
            st.markdown("#### Unique Stations per Month")
            u_stat = filt_df.groupby([y_col, m_name_col])['Station'].nunique().reset_index(name='U')
            fig_u = px.bar(u_stat, x=y_col, y='U', color=m_name_col, barmode='group', template=plotly_tmpl, color_discrete_sequence=[th_dark_red, th_red, th_orange, th_yellow])
            fig_u.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_title="Station Count", xaxis_title="Season")
            st.plotly_chart(fig_u, use_container_width=True)
        with r2:
            st.markdown("#### Station Discovery Yield (First-Ever Logs)")
            new_logs = filt_df[filt_df[y_col] == filt_df['Station_Discovery_Year']].groupby(y_col).size().reset_index(name='N')
            fig_new = px.line(new_logs, x=y_col, y='N', markers=True, template=plotly_tmpl, color_discrete_sequence=[th_yellow])
            fig_new.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_title="New Stations Found", xaxis_title="Season")
            st.plotly_chart(fig_new, use_container_width=True)
            
            st.markdown("#### Active Es Days per Month")
            act_days = filt_df.groupby([y_col, m_name_col])['Date_Obj'].nunique().reset_index(name='D')
            fig_act = px.bar(act_days, x=y_col, y='D', color=m_name_col, barmode='stack', template=plotly_tmpl, color_discrete_sequence=[th_dark_red, th_red, th_orange, th_yellow])
            fig_act.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_title="Active Day Count", xaxis_title="Season")
            st.plotly_chart(fig_act, use_container_width=True)
            
        st.markdown("#### Opening Strength: Logs per Active Day")
        str_data = filt_df.groupby([y_col, m_name_col]).agg({'Station': 'count', 'Date_Obj': 'nunique'}).reset_index()
        str_data['Intensity'] = str_data['Station'] / str_data['Date_Obj']
        fig_str = px.bar(str_data, x=y_col, y='Intensity', color=m_name_col, barmode='group', template=plotly_tmpl, color_discrete_sequence=[th_dark_red, th_red, th_orange, th_yellow])
        fig_str.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_title="Avg Logs / Opening Day", xaxis_title="Season")
        st.plotly_chart(fig_str, use_container_width=True)

# 10. MODULE 5: FREQUENCY & MUF
elif selected_page == "FREQUENCY & MUF":
    st.markdown(f"<h1 style='text-align: center; color: {th_red};'>FREQUENCY & MUF FORENSICS</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    current = st.session_state.selected_mhz
    col_m, col_f = st.columns([3, 1]) if current not in ["TUNE...", None] else st.columns([1, 0.001])
    
    with col_m:
        st.markdown("### 🎚️ SDR FREQUENCY TUNER")
        st.caption("Use the Coarse (1.0 MHz) or Fine (0.2 MHz) buttons to tune the dial, or enter a specific frequency directly.")
        
        base_freq = 87.7 if current in ["TUNE...", None] else current
        
        t1, t2, t3, t4, t5 = st.columns([1, 1, 3, 1, 1])
        with t1:
            if st.button("⏪ -1.0", use_container_width=True): 
                st.session_state.selected_mhz = round(base_freq - 1.0, 1)
                st.rerun()
        with t2:
            if st.button("◀ -0.2", use_container_width=True): 
                st.session_state.selected_mhz = round(base_freq - 0.2, 1)
                st.rerun()
        with t3:
            if current in ["TUNE...", None]:
                st.markdown('<div class="lcd-screen">TUNE...</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="lcd-screen">{current:.1f} <span class="lcd-unit">MHz</span></div>', unsafe_allow_html=True)
            st.text_input("DIRECT ENTRY (e.g. 921 for 92.1)", key="freq_direct_entry", on_change=update_freq_from_input)
        with t4:
            if st.button("+0.2 ▶", use_container_width=True): 
                st.session_state.selected_mhz = round(base_freq + 0.2, 1)
                st.rerun()
        with t5:
            if st.button("+1.0 ⏩", use_container_width=True): 
                st.session_state.selected_mhz = round(base_freq + 1.0, 1)
                st.rerun()

        st.markdown("---")
        
        # --- MUF DAILY CEILING ALMANAC ---
        st.markdown("### 🌡️ MUF DAILY CEILING ALMANAC")
        st.caption("Select a month to view the historical MUF (Highest Frequency) for each day/year combination.")
        
        sel_muf_m = st.pills("SELECT MUF MONTH", ["May", "June", "July", "August"], default=st.session_state.muf_almanac_month, key="muf_month_pill")
        st.session_state.muf_almanac_month = sel_muf_m
        
        muf_df = filt_df[filt_df[m_name_col] == sel_muf_m]
        
        if not muf_df.empty:
            muf_pivot = muf_df.pivot_table(index=dom_col, columns=y_col, values='Freq_Num', aggfunc='max').reindex(range(1, 32))
            
            def style_muf_grid(df):
                styles = pd.DataFrame('', index=df.index, columns=df.columns)
                for r in df.index:
                    for c in df.columns:
                        val = df.at[r, c]
                        if pd.notna(val) and val > 0:
                            if val >= 107.0: bg = '#D32F2F'; fg = 'white'
                            elif val >= 98.0: bg = '#FFA500'; fg = 'black'
                            elif val >= 92.0: bg = '#FFFF00'; fg = 'black'
                            else: bg = '#FFFFE0'; fg = 'black'
                            styles.at[r, c] = f'background-color: {bg}; color: {fg}; font-weight: bold;'
                        else:
                            styles.at[r, c] = f'background-color: {th_bg}; color: {th_gray};'
                return styles
            
            st.dataframe(muf_pivot.style.apply(style_muf_grid, axis=None).format("{:.1f}", na_rep="-"), use_container_width=True, height=1250)
            
            # FLYUP TACTICAL REPORT FOR MUF
            muf_date = st.date_input("SELECT DATE FOR TACTICAL MUF REPORT", value=st.session_state.muf_tactical_date, min_value=muf_df['Date_Obj'].min(), max_value=muf_df['Date_Obj'].max(), key="muf_date_input")
            if muf_date:
                st.session_state.muf_tactical_date = muf_date
                st.markdown("---")
                rt_1, rt_2 = st.columns([3, 1])
                rt_1.markdown(f"### 🚀 DAILY MUF INTEL: {muf_date.strftime('%b %d, %Y')}")
                if rt_2.button("❌ CLEAR MUF REPORT", use_container_width=True):
                    st.session_state.muf_tactical_date = None
                    st.rerun()
                    
                d_muf = muf_df[muf_df['Date_Obj'] == muf_date]
                if not d_muf.empty:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Total Logs", f"{len(d_muf):,}")
                    c2.metric("Absolute MUF", f"{d_muf['Freq_Num'].max():.1f} MHz")
                    c3.metric("Unique DXers", d_muf['DXer'].nunique())
                    c4.metric("Unique Stations", d_muf['Station'].nunique())
                    
                    r1, r2 = st.columns(2)
                    with r1:
                        st.markdown('<div class="stat-header">TOP 5 CATCH PATHS (STATE ➔ STATE)</div>', unsafe_allow_html=True)
                        p = d_muf.groupby([dx_st_col, 'State']).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                        p['Path'] = p[dx_st_col].astype(str) + " ➔ " + p['State'].astype(str)
                        st.dataframe(p[['Path', 'L']], hide_index=True, use_container_width=True)
                        
                        st.markdown('<div class="stat-header">LOCATION DOMINANCE</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-val">{d_muf[dx_loc_col].mode().iloc[0]}</div><div class="stat-label">Most Active DXer Location</div>', unsafe_allow_html=True)
                    with r2:
                        st.markdown('<div class="stat-header">TOP 5 STATIONS</div>', unsafe_allow_html=True)
                        st.dataframe(d_muf.groupby('Station').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True, use_container_width=True)
                        
                        f = d_muf.sort_values(d_col, ascending=False).iloc[0]
                        st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-val">{f[d_col]:,.0f} MILES</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-label">{f["Frequency"]} - {f["Station"]}, {f["City"]}, {f["State"]} by {f["DXer"]} ({f[dx_loc_col]}) on {f["Date_Str"]} at {f["Local_Time"]}</div>', unsafe_allow_html=True)
            else:
                st.warning("No signal intelligence recorded on this date.")
        
        st.markdown("---")
        r1, r2 = st.columns(2)
        with r1:
            st.markdown("#### 📊 GLOBAL BAND YIELD (LOGS PER FREQUENCY)")
            overall_freq = filt_df.groupby('Freq_Num').size().reset_index(name='Logs').sort_values('Freq_Num')
            fig_overall = px.bar(overall_freq, x='Freq_Num', y='Logs', template=plotly_tmpl, color_discrete_sequence=[th_red])
            fig_overall.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(title="Frequency (MHz)", range=[87.7, 107.9]), yaxis_title="Total Logs")
            st.plotly_chart(fig_overall, use_container_width=True)
            
        with r2:
            st.markdown("#### 📈 MUF PROBABILITY CURVE")
            daily_max = filt_df.groupby('Date_Obj')['Freq_Num'].max()
            muf_counts = daily_max.value_counts().reset_index().rename(columns={'count': 'Days', 'Freq_Num': 'Frequency'})
            total_active_days = len(daily_max)
            muf_counts['% Probability'] = (muf_counts['Days'] / total_active_days) * 100 if total_active_days > 0 else 0
            muf_counts = muf_counts.sort_values('Frequency')
            fig_muf_prob = px.area(muf_counts, x='Frequency', y='% Probability', template=plotly_tmpl, color_discrete_sequence=[th_orange])
            fig_muf_prob.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_title="Frequency (MHz)", yaxis_title="% of Active Days as MUF")
            st.plotly_chart(fig_muf_prob, use_container_width=True)

    if current not in ["TUNE...", None]:
        with col_f:
            st.markdown(f"### 📡 {current:.1f} MHz INTEL")
            if st.button("❌ CLEAR TUNER", use_container_width=True): 
                st.session_state.selected_mhz = "TUNE..."
                st.rerun()
            
            s_freq = filt_df[filt_df['Freq_Num'] == current]
            
            st.markdown('<div class="stat-header">TOTAL LOGS</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="stat-val">{len(s_freq):,}</div>', unsafe_allow_html=True)
            
            if not s_freq.empty and len(filt_df) > 0:
                pct_vol = (len(s_freq) / len(filt_df)) * 100
                st.markdown('<div class="stat-header">% OF GLOBAL VOLUME</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{pct_vol:.2f}%</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="stat-header">UNIQUE DXERS</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{s_freq["DXer"].nunique()}</div>', unsafe_allow_html=True)
                
                freq_active_days = s_freq['Date_Obj'].nunique()
                total_active_days = filt_df['Date_Obj'].nunique()
                pct_active = (freq_active_days / total_active_days * 100) if total_active_days > 0 else 0
                st.markdown('<div class="stat-header">% OF ACTIVE DAYS</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{pct_active:.1f}%</div><div class="stat-label">Days this frequency was open</div>', unsafe_allow_html=True)
                
                daily_max_series = filt_df.groupby('Date_Obj')['Freq_Num'].max()
                days_as_muf = (daily_max_series == current).sum()
                pct_muf = (days_as_muf / total_active_days * 100) if total_active_days > 0 else 0
                st.markdown('<div class="stat-header">MUF CEILING FREQUENCY</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{pct_muf:.1f}%</div><div class="stat-label">Of total days, this was the absolute MUF</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="stat-header">TOP MONTHS</div>', unsafe_allow_html=True)
                st.dataframe(s_freq[m_name_col].value_counts().head(5).reset_index(name='Logs').rename(columns={'index': 'Month'}), hide_index=True)
                
                st.markdown('<div class="stat-header">TOP YEARS</div>', unsafe_allow_html=True)
                st.dataframe(s_freq[y_col].value_counts().head(5).reset_index(name='Logs').rename(columns={'index': 'Year'}), hide_index=True)
                
                st.markdown('<div class="stat-header">TOP HOURS (LOCAL)</div>', unsafe_allow_html=True)
                st.dataframe(s_freq[h_col].value_counts().head(5).reset_index(name='Logs').rename(columns={'index': 'Hour'}), hide_index=True)

                st.markdown('<div class="stat-header">TOP 5 CATCH PATHS</div>', unsafe_allow_html=True)
                f_paths = s_freq.groupby([dx_st_col, 'State']).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                f_paths['Path'] = f_paths[dx_st_col].astype(str) + " ➔ " + f_paths['State'].astype(str)
                st.dataframe(f_paths[['Path', 'L']], hide_index=True)

                st.markdown('<div class="stat-header">LOCATION DOMINANCE</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{s_freq[dx_loc_col].mode().iloc[0]}</div><div class="stat-label">Most Active DXer Location</div>', unsafe_allow_html=True)

                intl_freq = s_freq[~s_freq['Country'].isin(['USA', 'Canada'])]
                if not intl_freq.empty:
                    st.markdown('<div class="stat-header">TOP INTERNATIONAL</div>', unsafe_allow_html=True)
                    st.dataframe(intl_freq.groupby('Country').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(3), hide_index=True)

                f_rec = s_freq.sort_values(d_col, ascending=False).iloc[0]
                st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{f_rec[d_col]:,.0f} MILES</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-label">{f_rec["Frequency"]} - {f_rec["Station"]}, {f_rec["City"]}, {f_rec["State"]} by {f_rec["DXer"]} ({f_rec[dx_loc_col]}) on {f_rec["Date_Str"]} at {f_rec["Local_Time"]}</div>', unsafe_allow_html=True)
            else:
                st.warning("No signal intelligence recorded on this frequency.")

# 11. MODULE 6: DXER INTELLIGENCE
elif selected_page == "DXER INTELLIGENCE": 
    st.markdown(f"<h1 style='text-align: center; color: {th_red};'>DXER NETWORK INTELLIGENCE</h1>", unsafe_allow_html=True)
    st.markdown("---")

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("### 📈 NETWORK GROWTH (YOY)")
        st.caption("Tracking the influx of monitoring stations and unique operators over time.")
        dx_y_stats = filt_df.groupby(y_col).agg(Logs=('Station', 'count'), Unique_DXers=('DXer', 'nunique')).reset_index()
        fig_growth = px.bar(dx_y_stats, x=y_col, y='Unique_DXers', template=plotly_tmpl, color_discrete_sequence=[th_red])
        fig_growth.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_title="Active DXers", xaxis_title="Season")
        st.plotly_chart(fig_growth, use_container_width=True)

    with col_g2:
        st.markdown("### 🏆 SEASON QUALITY INDEX (SQI)")
        st.caption("Logs per DXer: Normalizing the data to separate 'Observer Bias' from true atmospheric openings.")
        dx_y_stats['SQI'] = dx_y_stats['Logs'] / dx_y_stats['Unique_DXers']
        fig_sqi = px.line(dx_y_stats, x=y_col, y='SQI', markers=True, template=plotly_tmpl, color_discrete_sequence=[th_yellow])
        fig_sqi.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_title="SQI (Logs per DXer)", xaxis_title="Season")
        st.plotly_chart(fig_sqi, use_container_width=True)

    st.markdown("---")
    
    col_map, col_fly = st.columns([3, 1]) if st.session_state.selected_dx_loc else st.columns([1, 0.001])
    
    with col_map:
        st.markdown("### 📡 RECEIVER NETWORK MAP")
        st.caption("Scroll to zoom in/out and drag to pan. Click any location cluster to interrogate specific DXer intelligence.")
        
        # Build the cluster map data
        dx_map_data = filt_df.groupby([dx_loc_col, 'DX_Lat', 'DX_Lon']).agg(
            Logs=('Station', 'count'),
            DXer_Count=('DXer', 'nunique'),
            DXers=('DXer', lambda x: '<br>'.join(x.unique()))
        ).reset_index()
        
        # Create an interactive Plotly Mapbox for clustering and click events
        fig_dx = px.scatter_mapbox(
            dx_map_data, lat='DX_Lat', lon='DX_Lon', size='Logs', color='Logs',
            hover_name=dx_loc_col, 
            hover_data={'DX_Lat':False, 'DX_Lon':False, 'DXers':True, 'DXer_Count':True},
            color_continuous_scale=global_color_scale, zoom=4.2, center=dict(lat=38, lon=-95),
            size_max=45
        )
        fig_dx.update_layout(mapbox_style=map_style_px, height=800, paper_bgcolor='rgba(0,0,0,0)', margin={"r":0,"t":0,"l":0,"b":0})
        
        ev_dx = st.plotly_chart(fig_dx, use_container_width=True, on_select="rerun", key=f"dx_map_{st.session_state.dx_map_key}", config={'scrollZoom': True})
        
        if ev_dx and ev_dx.get("selection") and ev_dx["selection"].get("points"):
            pt = ev_dx["selection"]["points"][0]
            if "hovertext" in pt:
                new_loc = pt["hovertext"]
                if st.session_state.selected_dx_loc != new_loc:
                    st.session_state.selected_dx_loc = new_loc
                    st.rerun()

    if st.session_state.selected_dx_loc:
        with col_fly:
            loc = st.session_state.selected_dx_loc
            st.markdown(f"### 📍 {loc}")
            
            if st.button("❌ CLEAR LOCATION", key="cl_dx_map", use_container_width=True): 
                st.session_state.selected_dx_loc = None
                st.session_state.dx_map_key += 1
                st.rerun()
                
            loc_df = filt_df[filt_df[dx_loc_col] == loc]
            unique_dxers = sorted(loc_df['DXer'].unique().tolist())
            
            if len(unique_dxers) > 1:
                st.info(f"{len(unique_dxers)} Operators found at this location.")
                target_dxer = st.selectbox("Select Target Operator", options=unique_dxers)
            else:
                target_dxer = unique_dxers[0]
                st.markdown(f"**Operator:** {target_dxer}")
                
            d_df = loc_df[loc_df['DXer'] == target_dxer]
            
            st.markdown('<div class="stat-header">TOTAL LOGS</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="stat-val">{len(d_df):,}</div>', unsafe_allow_html=True)
            
            pct_global = (len(d_df) / len(filt_df)) * 100 if len(filt_df) > 0 else 0
            st.markdown('<div class="stat-header">% OF GLOBAL VOLUME</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="stat-val">{pct_global:.2f}%</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="stat-header">UNIQUE STATIONS</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="stat-val">{d_df["Station"].nunique():,}</div>', unsafe_allow_html=True)
            
            active_seasons = d_df[y_col].nunique()
            st.markdown('<div class="stat-header">ACTIVE SEASONS</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="stat-val">{active_seasons}</div>', unsafe_allow_html=True)
            
            logs_per_season = len(d_df) / active_seasons if active_seasons > 0 else 0
            st.markdown('<div class="stat-header">LOGS PER SEASON</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="stat-val">{logs_per_season:.1f}</div>', unsafe_allow_html=True)
            
            m_c, y_c = d_df[m_name_col].value_counts(), d_df[y_col].value_counts()
            st.markdown('<div class="stat-header">PEAK SEASONALITY</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Month</div><div class="stat-val" style="margin-top:0px;">{str(m_c.idxmax()).upper() if not m_c.empty else "N/A"}</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Year</div><div class="stat-val" style="margin-top:0px;">{y_c.idxmax() if not y_c.empty else "N/A"}</div></div>', unsafe_allow_html=True)
            
            st.markdown('<div class="window-box">', unsafe_allow_html=True)
            st.markdown(f'<div class="stat-label" style="color:{th_red}">Season Window</div>', unsafe_allow_html=True)
            od = pd.to_datetime(d_df['Local_Date'])
            st.markdown(f'<div class="stat-label">Start: {get_avg_date(od.groupby(d_df[y_col]).min())} | Peak: {get_avg_date(od)} | End: {get_avg_date(od.groupby(d_df[y_col]).max())}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="stat-header">LOGS BY SEASON</div>', unsafe_allow_html=True)
            dx_yr_counts = d_df.groupby(y_col).size().reset_index(name='Logs').sort_values(y_col)
            fig_dx_yr = px.bar(dx_yr_counts, x=y_col, y='Logs', template=plotly_tmpl, color_discrete_sequence=[th_red])
            fig_dx_yr.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=250, margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(title=None, type='category'), yaxis_title=None)
            st.plotly_chart(fig_dx_yr, use_container_width=True)

            st.markdown('<div class="stat-header">DISTANCE DISTRIBUTION</div>', unsafe_allow_html=True)
            dist_breakdown = d_df.groupby(dd_col).size().reset_index(name='Logs').sort_values('Logs', ascending=False)
            dist_breakdown['%'] = (dist_breakdown['Logs'] / len(d_df)) * 100
            st.dataframe(dist_breakdown, column_config={
                dd_col: "Category",
                "Logs": "Total Logs",
                "%": st.column_config.NumberColumn("% of Total", format="%.1f%%")
            }, hide_index=True, use_container_width=True)
            
            st.markdown('<div class="stat-header">TOP 5 STATES/PROV</div>', unsafe_allow_html=True)
            st.dataframe(d_df.groupby('State').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)
            
            intl_d = d_df[~d_df['Country'].isin(['USA', 'Canada'])]
            if not intl_d.empty:
                st.markdown('<div class="stat-header">TOP 3 INTERNATIONAL</div>', unsafe_allow_html=True)
                st.dataframe(intl_d.groupby('Country').size().reset_index(name='L').sort_values('L', ascending=False).head(3), hide_index=True)
                
            f_r = d_df.sort_values(d_col, ascending=False).iloc[0] if not d_df.empty else None
            if f_r is not None:
                st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{f_r[d_col]:,.0f} MILES</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-label">{f_r["Frequency"]} - {f_r["Station"]}, {f_r["City"]}, {f_r["State"]} on {f_r["Date_Str"]} at {f_r["Local_Time"]}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🥇 DXER LEADERBOARDS")
    col_l1, col_l2 = st.columns(2)
    
    with col_l1:
        st.markdown("#### 🌎 GLOBAL VOLUME LEADERS")
        top_dxers = filt_df.groupby('DXer').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(50)
        top_dxers['M'] = top_dxers['Logs']
        st.dataframe(
            top_dxers,
            column_config={
                "DXer": "Operator",
                "Logs": st.column_config.NumberColumn("Total Logs", format="%d"),
                "M": st.column_config.ProgressColumn("Volume Meter", format="%d", min_value=0, max_value=int(top_dxers['Logs'].max() if not top_dxers.empty else 100))
            },
            hide_index=True,
            use_container_width=True
        )

    with col_l2:
        st.markdown("#### 📍 REGIONAL LEADERS")
        reg_list = [r for r in filt_df['DXer_Region'].dropna().unique().tolist() if r != "All"]
        if reg_list:
            sel_reg = st.selectbox("Select Region", options=sorted(reg_list))
            reg_df = filt_df[filt_df['DXer_Region'] == sel_reg]
            top_reg = reg_df.groupby('DXer').size().reset_index(name='Logs').sort_values('Logs', ascending=False).head(50)
            top_reg['M'] = top_reg['Logs']
            st.dataframe(
                top_reg,
                column_config={
                    "DXer": "Operator",
                    "Logs": st.column_config.NumberColumn("Total Logs", format="%d"),
                    "M": st.column_config.ProgressColumn("Volume Meter", format="%d", min_value=0, max_value=int(top_reg['Logs'].max() if not top_reg.empty else 100))
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No regional data available for the current filter selection.")

# 12. MODULE 7: STATION & RDS IQ
elif selected_page == "STATION & RDS IQ": 
    st.markdown(f"<h1 style='text-align: center; color: {th_red};'>STATION & RDS INTELLIGENCE HUB</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("## 📡 TRANSMITTER NETWORK MAP")
    st.caption("Scroll to zoom in/out and drag to pan across the transmitter network. Click any transmitter location cluster to interrogate specific Station intelligence.")
    
    st_col_map, st_col_fly = st.columns([3, 1]) if st.session_state.selected_st_loc else st.columns([1, 0.001])
    
    with st_col_map:
        st_map_data = filt_df.groupby([st_loc_col, 'ST_Lat', 'ST_Lon']).agg(
            Logs=('Station', 'count'),
            Station_Count=('Station', 'nunique'),
            Stations=('Station', lambda x: '<br>'.join(x.unique()[:10]) + ('<br>...' if len(x.unique()) > 10 else ''))
        ).reset_index()
        
        fig_st_map = px.scatter_mapbox(
            st_map_data, lat='ST_Lat', lon='ST_Lon', size='Logs', color='Logs',
            hover_name=st_loc_col, 
            hover_data={'ST_Lat':False, 'ST_Lon':False, 'Stations':True, 'Station_Count':True},
            color_continuous_scale=global_color_scale, zoom=4.0, center=dict(lat=38, lon=-95),
            size_max=45
        )
        fig_st_map.update_layout(mapbox_style=map_style_px, height=800, paper_bgcolor='rgba(0,0,0,0)', margin={"r":0,"t":0,"l":0,"b":0})
        
        ev_st = st.plotly_chart(fig_st_map, use_container_width=True, on_select="rerun", key=f"st_map_{st.session_state.st_map_key}", config={'scrollZoom': True})
        
        if ev_st and ev_st.get("selection") and ev_st["selection"].get("points"):
            pt = ev_st["selection"]["points"][0]
            if "hovertext" in pt:
                new_loc = pt["hovertext"]
                if st.session_state.selected_st_loc != new_loc:
                    st.session_state.selected_st_loc = new_loc
                    st.rerun()

    if st.session_state.selected_st_loc:
        with st_col_fly:
            loc = st.session_state.selected_st_loc
            st.markdown(f"### 📍 {loc}")
            
            if st.button("❌ CLEAR LOCATION", key="cl_st_map", use_container_width=True): 
                st.session_state.selected_st_loc = None
                st.session_state.st_map_key += 1
                st.rerun()
                
            loc_df = filt_df[filt_df[st_loc_col] == loc].copy()
            loc_df['Station_Display'] = loc_df['Station'].astype(str) + " (" + loc_df['Freq_Num'].astype(str) + " MHz)"
            unique_stations = sorted(loc_df['Station_Display'].dropna().unique().tolist())
            
            if len(unique_stations) > 1:
                st.info(f"{loc_df['Station'].nunique()} Stations found at this location.")
                target_st_display = st.selectbox("Select Target Station", options=unique_stations)
            else:
                target_st_display = unique_stations[0]
                
            s_df = loc_df[loc_df['Station_Display'] == target_st_display]
            
            if not s_df.empty:
                hero_freq = s_df['Frequency'].iloc[0]
                hero_call = s_df['Station'].iloc[0]
                st.markdown(f"<h2 style='color:{th_yellow}; margin-bottom:0px;'>{hero_freq} {hero_call}</h2>", unsafe_allow_html=True)
                
                st.markdown('<div class="stat-header">TOTAL LOGS</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{len(s_df):,}</div>', unsafe_allow_html=True)
                
                pct_global = (len(s_df) / len(filt_df)) * 100 if len(filt_df) > 0 else 0
                st.markdown('<div class="stat-header">% OF GLOBAL VOLUME</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{pct_global:.2f}%</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="stat-header">UNIQUE DXERS</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{s_df["DXer"].nunique():,}</div>', unsafe_allow_html=True)
                
                m_c, y_c = s_df[m_name_col].value_counts(), s_df[y_col].value_counts()
                st.markdown('<div class="stat-header">PEAK SEASONALITY</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Month</div><div class="stat-val" style="margin-top:0px;">{str(m_c.idxmax()).upper() if not m_c.empty else "N/A"}</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="margin-bottom: 10px;"><div class="stat-label">Peak Year</div><div class="stat-val" style="margin-top:0px;">{y_c.idxmax()} ({y_c.max()})</div></div>', unsafe_allow_html=True)
                
                st.markdown('<div class="window-box">', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-label" style="color:{th_red}">Season Window</div>', unsafe_allow_html=True)
                od = pd.to_datetime(s_df['Local_Date'])
                st.markdown(f'<div class="stat-label">Start: {get_avg_date(od.groupby(s_df[y_col]).min())} | Peak: {get_avg_date(od)} | End: {get_avg_date(od.groupby(s_df[y_col]).max())}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown('<div class="stat-header">LOGS BY MONTH</div>', unsafe_allow_html=True)
                s_mo_counts = s_df.groupby(m_name_col).size().reset_index(name='Logs')
                fig_s_mo = px.bar(s_mo_counts, x=m_name_col, y='Logs', template=plotly_tmpl, color_discrete_sequence=[th_orange])
                fig_s_mo.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=200, margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(title=None, type='category'), yaxis_title=None)
                st.plotly_chart(fig_s_mo, use_container_width=True)

                st.markdown('<div class="stat-header">LOGS BY YEAR</div>', unsafe_allow_html=True)
                s_yr_counts = s_df.groupby(y_col).size().reset_index(name='Logs').sort_values(y_col)
                fig_s_yr = px.bar(s_yr_counts, x=y_col, y='Logs', template=plotly_tmpl, color_discrete_sequence=[th_red])
                fig_s_yr.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=200, margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(title=None, type='category'), yaxis_title=None)
                st.plotly_chart(fig_s_yr, use_container_width=True)
                
                st.markdown('<div class="stat-header">TOP 5 RECEPTION PATHS</div>', unsafe_allow_html=True)
                p_paths = s_df.groupby(dx_st_col).size().reset_index(name='L').sort_values('L', ascending=False).head(5)
                st.dataframe(p_paths, column_config={dx_st_col:"DXer State/Prov", "L":"Logs"}, hide_index=True, use_container_width=True)
                
                f_r = s_df.sort_values(d_col, ascending=False).iloc[0] if not s_df.empty else None
                if f_r is not None:
                    st.markdown('<div class="stat-header">FURTHEST RECEPTION</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{f_r[d_col]:,.0f} MILES</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-label">Caught by {f_r["DXer"]} ({f_r[dx_loc_col]}) on {f_r["Date_Str"]} at {f_r["Local_Time"]}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("## 📻 INTELLIGENCE DATA HUB")
    
    # We update the default view locally if a manual click overrides our programmatic teleport
    if 'rds_view_default' not in st.session_state:
        st.session_state.rds_view_default = "WTFDA US State Intelligence"
        
    rds_view = st.pills("INTELLIGENCE DATA SOURCE", ["Logged RDS Data", "WTFDA RDS Intelligence", "WTFDA Station Intelligence", "WTFDA US State Intelligence", "WTFDA County Intelligence"], default=st.session_state.rds_view_default)
    
    if rds_view != st.session_state.rds_view_default:
        st.session_state.rds_view_default = rds_view
    
    if rds_view == "Logged RDS Data":
        total_logs = len(filt_df)
        rds_logs = len(filt_df[filt_df['RDS_Status'] == 'Yes'])
        rds_pct = (rds_logs / total_logs * 100) if total_logs > 0 else 0
        
        col_r1, col_r2 = st.columns([1, 3])
        with col_r1:
            st.markdown("### OVERALL RDS YIELD")
            st.metric("Total RDS Decodes", f"{rds_logs:,}")
            st.markdown(f'<div class="stat-val" style="font-size: 3rem; color: {th_yellow};">{rds_pct:.1f}%</div><div class="stat-label">Of currently filtered logs contain RDS data</div>', unsafe_allow_html=True)
            
        with col_r2:
            st.markdown("### 📈 YOY RDS TREND ANALYSIS")
            rds_yr = filt_df.groupby([y_col, 'RDS_Status']).size().reset_index(name='Logs')
            rds_yr['Total'] = rds_yr.groupby(y_col)['Logs'].transform('sum')
            rds_yr['Pct'] = (rds_yr['Logs'] / rds_yr['Total'] * 100).round(1)
            rds_yr['Label'] = rds_yr['Pct'].astype(str) + '%'
            
            fig_rds_trend = px.bar(rds_yr, x=y_col, y='Logs', color='RDS_Status', text='Label', template=plotly_tmpl, color_discrete_map={'Yes': th_blue, 'No': th_gray})
            fig_rds_trend.update_traces(textposition='inside', textfont_size=14)
            fig_rds_trend.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(type='category'), barmode='stack', yaxis_title="Total Logs", xaxis_title="Season")
            st.plotly_chart(fig_rds_trend, use_container_width=True)

        r_c1, r_c2, r_c3 = st.columns(3)
        
        with r_c1:
            st.markdown("#### RDS YIELD BY FREQUENCY")
            odd_freq_df = filt_df[filt_df['Freq_Num'].notna()].copy()
            odd_freq_df = odd_freq_df[odd_freq_df['Freq_Num'].apply(lambda x: int(round(x * 10)) % 2 != 0)]
            
            freq_rds = odd_freq_df.groupby('Freq_Num')['RDS_Status'].value_counts(normalize=True).unstack().fillna(0)
            freq_rds['RDS_%'] = freq_rds.get('Yes', 0) * 100
            freq_rds = freq_rds.reset_index()
            fig_f_rds = px.line(freq_rds, x='Freq_Num', y='RDS_%', template=plotly_tmpl, color_discrete_sequence=[th_blue])
            fig_f_rds.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(title="Frequency (MHz)", range=[87.7, 107.9]), yaxis_title="% with RDS")
            st.plotly_chart(fig_f_rds, use_container_width=True)
            
        with r_c2:
            st.markdown("#### TOP STATES/PROV BY RDS YIELD")
            state_rds = filt_df.groupby('State')['RDS_Status'].value_counts().unstack().fillna(0)
            state_rds['Total'] = state_rds.sum(axis=1)
            state_rds = state_rds[state_rds['Total'] >= 50]
            state_rds['RDS_%'] = (state_rds.get('Yes', 0) / state_rds['Total']) * 100
            state_rds = state_rds.reset_index().sort_values('RDS_%', ascending=False).head(10)
            st.dataframe(state_rds[['State', 'Total', 'RDS_%']], column_config={"RDS_%": st.column_config.NumberColumn("% Decoded", format="%.1f%%")}, hide_index=True, use_container_width=True)

        with r_c3:
            st.markdown("#### TOP COUNTRIES BY RDS YIELD")
            ctry_rds = filt_df.groupby('Country')['RDS_Status'].value_counts().unstack().fillna(0)
            ctry_rds['Total'] = ctry_rds.sum(axis=1)
            ctry_rds['RDS_%'] = (ctry_rds.get('Yes', 0) / ctry_rds['Total']) * 100
            ctry_rds = ctry_rds.reset_index().sort_values('RDS_%', ascending=False).head(10)
            st.dataframe(ctry_rds[['Country', 'Total', 'RDS_%']], column_config={"RDS_%": st.column_config.NumberColumn("% Decoded", format="%.1f%%")}, hide_index=True, use_container_width=True)
            
    elif rds_view == "WTFDA RDS Intelligence":
        st.markdown("### 📡 WTFDA STATION DATABASE FORENSICS")
        st.caption("The data presented below is sourced from the Worldwide TV-FM DX Association station database at [db.wtfda.org](https://db.wtfda.org/).")
        
        wtfda_df = load_wtfda_data()
        if not wtfda_df.empty:
            total_st = len(wtfda_df)
            pi_st = len(wtfda_df[wtfda_df['Has_PI'] == 'Yes'])
            pi_pct = (pi_st / total_st) * 100 if total_st > 0 else 0
            
            c_w1, c_w2, c_w3 = st.columns(3)
            c_w1.metric("Total Stations (US/CA/MX)", f"{total_st:,}")
            c_w2.metric("Stations Transmitting PI Code", f"{pi_st:,}")
            c_w3.markdown(f'<div class="stat-header">OVERALL PI ADOPTION</div><div class="stat-val" style="color:{th_yellow}; font-size: 2.2rem;">{pi_pct:.1f}%</div>', unsafe_allow_html=True)
            
            st.markdown("---")
            r_w1, r_w2 = st.columns(2)
            
            with r_w1:
                st.markdown("#### COMMERCIAL VS NON-COMMERCIAL PI YIELD")
                band_grp = wtfda_df.groupby(['Band_Type', 'Has_PI']).size().reset_index(name='Count')
                band_grp['Total'] = band_grp.groupby('Band_Type')['Count'].transform('sum')
                band_grp['Pct'] = (band_grp['Count'] / band_grp['Total'] * 100).round(1)
                band_grp['Label'] = band_grp['Pct'].astype(str) + '%'
                
                fig_band = px.bar(band_grp, x='Band_Type', y='Count', color='Has_PI', text='Label', template=plotly_tmpl, color_discrete_map={'Yes': th_blue, 'No': th_gray}, barmode='stack')
                fig_band.update_traces(textposition='inside', textfont_size=14)
                fig_band.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, yaxis_title="Station Count")
                st.plotly_chart(fig_band, use_container_width=True)
                
            with r_w2:
                st.markdown("#### PI CODE ADOPTION BY FREQUENCY")
                freq_grp = wtfda_df[wtfda_df['Frequency'].apply(lambda x: int(round(x * 10)) % 2 != 0)]
                f_pi = freq_grp.groupby('Frequency')['Has_PI'].value_counts(normalize=True).unstack().fillna(0)
                f_pi['PI_%'] = f_pi.get('Yes', 0) * 100
                f_pi = f_pi.reset_index()
                fig_f_pi = px.line(f_pi, x='Frequency', y='PI_%', template=plotly_tmpl, color_discrete_sequence=[th_blue])
                fig_f_pi.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(title="Frequency (MHz)", range=[87.7, 107.9]), yaxis_title="% with PI Code")
                st.plotly_chart(fig_f_pi, use_container_width=True)

            st.markdown("---")
            
            col_w_m, col_w_f = st.columns([3, 1]) if st.session_state.selected_wtfda_state else st.columns([1, 0.001])
            
            with col_w_m:
                st.markdown("#### US STATE PI CODE ADOPTION MAP")
                st.caption("Click any state to view its specific PI Code adoption breakdown.")
                us_w = wtfda_df[wtfda_df['Country'] == 'USA']
                st_pi = us_w.groupby('S/P')['Has_PI'].value_counts(normalize=True).unstack().fillna(0)
                st_pi['PI_%'] = st_pi.get('Yes', 0) * 100
                st_pi = st_pi.reset_index()
                
                fig_us_pi = px.choropleth(st_pi, locations='S/P', locationmode='USA-states', color='PI_%', scope='usa', color_continuous_scale=global_color_scale, template=plotly_tmpl)
                fig_us_pi.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor=th_bg), margin={"r":0,"t":0,"l":0,"b":0}, height=500)
                ev_us_pi = st.plotly_chart(fig_us_pi, use_container_width=True, on_select="rerun", key=f"wtfda_us_{st.session_state.wtfda_map_key}")
                
                if ev_us_pi and ev_us_pi.get("selection") and ev_us_pi["selection"].get("points"):
                    new_state = ev_us_pi["selection"]["points"][0]["location"]
                    if st.session_state.selected_wtfda_state != new_state:
                        st.session_state.selected_wtfda_state = new_state
                        st.rerun()

            if st.session_state.selected_wtfda_state:
                with col_w_f:
                    ws_sel = st.session_state.selected_wtfda_state
                    st.markdown(f"### {ws_sel} INTEL")
                    if st.button("❌ CLEAR SELECTION", key="cl_w_map", use_container_width=True): 
                        st.session_state.selected_wtfda_state = None
                        st.session_state.wtfda_map_key += 1
                        st.rerun()
                        
                    s_df_w = wtfda_df[(wtfda_df['Country'] == 'USA') & (wtfda_df['S/P'] == ws_sel)]
                    st.markdown('<div class="stat-header">TOTAL STATIONS IN STATE</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{len(s_df_w):,}</div>', unsafe_allow_html=True)
                    
                    if not s_df_w.empty:
                        pi_ct = len(s_df_w[s_df_w['Has_PI'] == 'Yes'])
                        pi_pt = (pi_ct / len(s_df_w)) * 100
                        st.markdown('<div class="stat-header">PI CODE ADOPTION</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-val" style="color:{th_yellow};">{pi_pt:.1f}%</div><div class="stat-label">({pi_ct} Stations Transmitting)</div>', unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("#### NATIONAL PI YIELDS")
            ctry_grp = wtfda_df.groupby('Country')['Has_PI'].value_counts().unstack().fillna(0)
            ctry_grp['Total'] = ctry_grp.sum(axis=1)
            ctry_grp['PI_%'] = (ctry_grp.get('Yes', 0) / ctry_grp['Total']) * 100
            ctry_grp = ctry_grp.reset_index().sort_values('PI_%', ascending=False)
            st.dataframe(ctry_grp[['Country', 'Total', 'PI_%']], column_config={"PI_%": st.column_config.NumberColumn("% with PI", format="%.1f%%"), "Total": "Total Stations"}, hide_index=True, use_container_width=True)
            
    elif rds_view == "WTFDA Station Intelligence":
        st.markdown("### 📡 WTFDA STATION DATABASE FORENSICS")
        st.caption("Deep demographic analysis of formats and slogans from the worldwide database.")
        
        wtfda_df = load_wtfda_data()
        if not wtfda_df.empty:
            
            st.markdown("### 🎶 FORMAT INTELLIGENCE")
            col_fm, col_ff = st.columns([3, 1]) if st.session_state.selected_format else st.columns([1, 0.001])
            with col_fm:
                top_formats = wtfda_df['Format'].value_counts().reset_index()
                top_formats.columns = ['Format', 'Stations']
                top_formats = top_formats[top_formats['Format'] != 'Unknown'].head(25)
                fig_fmt = px.bar(top_formats, x='Format', y='Stations', template=plotly_tmpl, color_discrete_sequence=[th_red])
                fig_fmt.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, yaxis_title="Total Stations")
                ev_fmt = st.plotly_chart(fig_fmt, use_container_width=True, on_select="rerun", key=f"fmt_{st.session_state.format_map_key}")
                
                if ev_fmt and ev_fmt.get("selection") and ev_fmt["selection"].get("points"):
                    new_fmt = ev_fmt["selection"]["points"][0]["x"]
                    if st.session_state.selected_format != new_fmt:
                        st.session_state.selected_format = new_fmt
                        st.rerun()
            
            if st.session_state.selected_format:
                with col_ff:
                    fmt_sel = st.session_state.selected_format
                    st.markdown(f"### FORMAT: {fmt_sel}")
                    if st.button("❌ CLEAR SELECTION", key="cl_fmt", use_container_width=True): 
                        st.session_state.selected_format = None
                        st.session_state.format_map_key += 1
                        st.rerun()
                        
                    f_df = wtfda_df[wtfda_df['Format'] == fmt_sel]
                    st.markdown('<div class="stat-header">TOTAL STATIONS</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{len(f_df):,}</div>', unsafe_allow_html=True)
                    
                    pct_fmt = (len(f_df) / len(wtfda_df)) * 100
                    st.markdown('<div class="stat-header">% OF OVERALL DATABASE</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{pct_fmt:.2f}%</div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="stat-header">TOP 5 STATES/PROV</div>', unsafe_allow_html=True)
                    st.dataframe(f_df.groupby('S/P').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True, use_container_width=True)
                    
                    st.markdown('<div class="stat-header">TOP 5 FREQUENCIES</div>', unsafe_allow_html=True)
                    st.dataframe(f_df.groupby('Frequency').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True, use_container_width=True)

            st.markdown("---")
            
            st.markdown("### 🗣️ SLOGAN INTELLIGENCE")
            st.caption("Normalized to aggregate frequencies (e.g., 'K-95', 'Y-102.5' map to '{FREQ}')")
            col_sm, col_sf = st.columns([3, 1]) if st.session_state.selected_slogan else st.columns([1, 0.001])
            with col_sm:
                top_slogans = wtfda_df['Slogan_Clean'].value_counts().reset_index()
                top_slogans.columns = ['Slogan', 'Stations']
                top_slogans = top_slogans[top_slogans['Slogan'] != 'Unknown'].head(25)
                fig_slog = px.bar(top_slogans, x='Slogan', y='Stations', template=plotly_tmpl, color_discrete_sequence=[th_orange])
                fig_slog.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, yaxis_title="Total Stations")
                ev_slog = st.plotly_chart(fig_slog, use_container_width=True, on_select="rerun", key=f"slog_{st.session_state.slogan_map_key}")
                
                if ev_slog and ev_slog.get("selection") and ev_slog["selection"].get("points"):
                    new_slog = ev_slog["selection"]["points"][0]["x"]
                    if st.session_state.selected_slogan != new_slog:
                        st.session_state.selected_slogan = new_slog
                        st.rerun()
                        
            if st.session_state.selected_slogan:
                with col_sf:
                    slog_sel = st.session_state.selected_slogan
                    st.markdown(f"### SLOGAN: {slog_sel}")
                    if st.button("❌ CLEAR SELECTION", key="cl_slog", use_container_width=True): 
                        st.session_state.selected_slogan = None
                        st.session_state.slogan_map_key += 1
                        st.rerun()
                        
                    sl_df = wtfda_df[wtfda_df['Slogan_Clean'] == slog_sel]
                    st.markdown('<div class="stat-header">TOTAL STATIONS</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{len(sl_df):,}</div>', unsafe_allow_html=True)
                    
                    pct_slog = (len(sl_df) / len(wtfda_df)) * 100
                    st.markdown('<div class="stat-header">% OF OVERALL DATABASE</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{pct_slog:.2f}%</div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="stat-header">TOP 5 STATES/PROV</div>', unsafe_allow_html=True)
                    st.dataframe(sl_df.groupby('S/P').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True, use_container_width=True)
                    
                    st.markdown('<div class="stat-header">TOP 5 FORMATS</div>', unsafe_allow_html=True)
                    st.dataframe(sl_df[sl_df['Format'] != 'Unknown'].groupby('Format').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True, use_container_width=True)

            st.markdown("---")
            st.markdown("### 🔗 SLOGAN & FORMAT CORRELATION MATRIX")
            st.caption("Heatmap showing the intersection density between the Top 15 Slogans and their most frequent Formats.")
            
            top_slogans_list = wtfda_df[wtfda_df['Slogan_Clean'] != 'Unknown']['Slogan_Clean'].value_counts().head(15).index.tolist()
            
            # Extract top formats specifically for these top slogans to avoid empty rows
            slogans_df = wtfda_df[wtfda_df['Slogan_Clean'].isin(top_slogans_list)]
            top_formats_list = slogans_df[slogans_df['Format'] != 'Unknown']['Format'].value_counts().head(15).index.tolist()
            
            corr_df = slogans_df[slogans_df['Format'].isin(top_formats_list)]
            corr_pivot = corr_df.pivot_table(index='Format', columns='Slogan_Clean', aggfunc='size', fill_value=0)
            
            # Reorder to match the top lists and drop any lingering zero-sum rows
            corr_pivot = corr_pivot.reindex(index=top_formats_list, columns=top_slogans_list).fillna(0)
            corr_pivot = corr_pivot.loc[(corr_pivot.sum(axis=1) > 0)]
            
            # Custom Scale: 0 is Black, low hits are Pale Yellow, high hits are Dark Red
            gs_heat = [
                [0.0, th_bg], 
                [0.01, '#FFFFE0'], 
                [0.25, th_yellow], 
                [0.5, th_orange], 
                [0.75, th_red], 
                [1.0, th_dark_red]
            ]
            fig_corr = px.imshow(corr_pivot, template=plotly_tmpl, color_continuous_scale=gs_heat, text_auto=True, aspect="auto")
            fig_corr.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_title="Standardized Slogan", yaxis_title="Programming Format", coloraxis_showscale=False)
            st.plotly_chart(fig_corr, use_container_width=True)
            
    elif rds_view == "WTFDA US State Intelligence":
        st.markdown("### 📡 WTFDA STATE-LEVEL FORENSICS")
        st.caption("Click any state to interrogate available transmitters vs. historically logged stations.")
        
        wtfda_df = load_wtfda_data()
        if not wtfda_df.empty:
            us_w = wtfda_df[wtfda_df['Country'] == 'USA']
            state_counts = us_w.groupby('S/P').size().reset_index(name='Stations')
            
            col_w_m, col_w_f = st.columns([3, 1]) if st.session_state.selected_wtfda_state_intel else st.columns([1, 0.001])
            
            with col_w_m:
                fig_st_state = px.choropleth(state_counts, locations='S/P', locationmode='USA-states', color='Stations', scope='usa', color_continuous_scale=global_color_scale, template=plotly_tmpl)
                fig_st_state.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor=th_bg), margin={"r":0,"t":0,"l":0,"b":0}, height=600)
                ev_st_state = st.plotly_chart(fig_st_state, use_container_width=True, on_select="rerun", key=f"wtfda_state_intel_{st.session_state.wtfda_state_intel_map_key}")
                
                if ev_st_state and ev_st_state.get("selection") and ev_st_state["selection"].get("points"):
                    sel_state = ev_st_state["selection"]["points"][0]["location"]
                    if st.session_state.selected_wtfda_state_intel != sel_state:
                        st.session_state.selected_wtfda_state_intel = sel_state
                        st.rerun()

            if st.session_state.selected_wtfda_state_intel:
                with col_w_f:
                    sel = st.session_state.selected_wtfda_state_intel
                    st.markdown(f"### {sel} TARGET INTEL")
                    if st.button("❌ CLEAR SELECTION", key="cl_wst_map", use_container_width=True): 
                        st.session_state.selected_wtfda_state_intel = None
                        st.session_state.wtfda_state_intel_map_key += 1
                        st.rerun()
                        
                    s_intel_df = us_w[us_w['S/P'] == sel].copy()
                    total_avail = len(s_intel_df)
                    
                    st.markdown('<div class="stat-header">TOTAL STATIONS IN STATE</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{total_avail:,}</div>', unsafe_allow_html=True)
                    
                    # LOGGED VS AVAILABLE MATH
                    logged_in_state = filt_df[filt_df['State'] == sel]
                    logged_stations = logged_in_state['Station'].dropna().str.upper().str.strip().unique()
                    
                    # Fuzzy match cross reference
                    s_intel_df['Match_Call'] = s_intel_df['Callsign'].str.upper().str.strip()
                    logged_count = s_intel_df[s_intel_df['Match_Call'].isin(logged_stations)].shape[0]
                    pct_logged = (logged_count / total_avail) * 100 if total_avail > 0 else 0
                    
                    st.markdown('<div class="stat-header">NETWORK PENETRATION</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val" style="color:{th_yellow};">{pct_logged:.1f}%</div><div class="stat-label">{logged_count} of {total_avail} stations historically logged</div>', unsafe_allow_html=True)

                    pi_ct = len(s_intel_df[s_intel_df['Has_PI'] == 'Yes'])
                    pi_pt = (pi_ct / total_avail) * 100 if total_avail > 0 else 0
                    st.markdown('<div class="stat-header">RDS PI ADOPTION</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{pi_pt:.1f}%</div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="stat-header">TOP 3 CITIES</div>', unsafe_allow_html=True)
                    city_counts = s_intel_df['City'].value_counts().reset_index(name='Stations').head(3)
                    city_counts['%'] = (city_counts['Stations'] / total_avail) * 100
                    city_counts['M'] = city_counts['%']
                    st.dataframe(city_counts, column_config={"%": st.column_config.NumberColumn("%", format="%.1f%%"), "M": st.column_config.ProgressColumn("", format="", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)
                    
                    st.markdown('<div class="stat-header">TOP 5 FREQUENCIES</div>', unsafe_allow_html=True)
                    freq_counts = s_intel_df['Frequency'].value_counts().reset_index(name='Stations').head(5)
                    freq_counts['%'] = (freq_counts['Stations'] / total_avail) * 100
                    freq_counts['M'] = freq_counts['%']
                    st.dataframe(freq_counts, column_config={"%": st.column_config.NumberColumn("%", format="%.1f%%"), "M": st.column_config.ProgressColumn("", format="", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)
                    
                    st.markdown('<div class="stat-header">TOP 5 FORMATS</div>', unsafe_allow_html=True)
                    fmt_counts = s_intel_df[s_intel_df['Format'] != 'Unknown']['Format'].value_counts().reset_index(name='Stations').head(5)
                    fmt_counts['%'] = (fmt_counts['Stations'] / total_avail) * 100
                    fmt_counts['M'] = fmt_counts['%']
                    st.dataframe(fmt_counts, column_config={"%": st.column_config.NumberColumn("%", format="%.1f%%"), "M": st.column_config.ProgressColumn("", format="", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)

                    # THE GAMIFICATION LIST
                    st.markdown('<div class="stat-header">🎯 UNHEARD STATION TARGETS</div>', unsafe_allow_html=True)
                    st.caption(f"The following {total_avail - logged_count} stations have never been logged in the FMList dataset. Happy hunting!")
                    
                    unheard_df = s_intel_df[~s_intel_df['Match_Call'].isin(logged_stations)].sort_values(['Frequency', 'Callsign'])
                    if not unheard_df.empty:
                        unheard_df['Target'] = unheard_df['Frequency'].astype(str) + " - " + unheard_df['Callsign'] + " - " + unheard_df['City']
                        st.dataframe(unheard_df[['Target']], height=300, hide_index=True, use_container_width=True)
                    else:
                        st.success("100% Penetration! Every station in this state has been logged.")

    elif rds_view == "WTFDA County Intelligence":
        st.markdown("### 🗺️ WTFDA COUNTY-LEVEL FORENSICS")
        st.caption("Click any county to interrogate available transmitters vs. historically logged stations in that specific area.")
        wtfda_df = load_wtfda_data()
        
        if 'FIPS' not in wtfda_df.columns:
            st.warning("🚨 **County Intelligence Offline**")
            st.markdown("""
            The current WTFDA database in BigQuery has not yet been linked to the US Census geometry shapefiles. 
            
            **To unlock this feature:**
            Your database requires a standard `FIPS` code column. Once the Spatial Join SQL query is executed on your BigQuery warehouse, this map will automatically render. 
            """)
        else:
            col_wc_m, col_wc_f = st.columns([3, 1]) if st.session_state.selected_wtfda_county_intel else st.columns([1, 0.001])
            
            with col_wc_m:
                county_counts = wtfda_df.dropna(subset=['FIPS', 'County']).groupby(['FIPS', 'County', 'S/P']).size().reset_index(name='Stations')
                county_counts['Type'] = np.where(county_counts['S/P'] == 'LA', ' Parish, ', ' County, ')
                county_counts['Hover_Name'] = county_counts['County'] + county_counts['Type'] + county_counts['S/P']
                
                fig_w_county = px.choropleth(county_counts, geojson='https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json', locations='FIPS', color='Stations', scope='usa', color_continuous_scale=global_color_scale, hover_name='Hover_Name', template=plotly_tmpl)
                fig_w_county.update_layout(paper_bgcolor='rgba(0,0,0,0)', geo=dict(bgcolor='rgba(0,0,0,0)', lakecolor=th_bg), margin={"r":0,"t":0,"l":0,"b":0}, height=750)
                ev_w_county = st.plotly_chart(fig_w_county, use_container_width=True, on_select="rerun", key=f"wtfda_county_intel_{st.session_state.wtfda_county_intel_map_key}")
                
                if ev_w_county and ev_w_county.get("selection") and ev_w_county["selection"].get("points"):
                    sel_fips = ev_w_county["selection"]["points"][0]["location"]
                    if st.session_state.selected_wtfda_county_intel != sel_fips:
                        st.session_state.selected_wtfda_county_intel = sel_fips
                        st.rerun()

            if st.session_state.selected_wtfda_county_intel:
                with col_wc_f:
                    sel_fips = st.session_state.selected_wtfda_county_intel
                    s_intel_df = wtfda_df[wtfda_df['FIPS'] == sel_fips].copy()
                    c_name = s_intel_df['County'].iloc[0] if not s_intel_df.empty else "Unknown"
                    c_state = s_intel_df['S/P'].iloc[0] if not s_intel_df.empty else "XX"
                    c_type = "PARISH" if c_state == 'LA' else "COUNTY"
                    
                    st.markdown(f"### {c_name.upper()} {c_type} TARGET INTEL")
                    if st.button("❌ CLEAR SELECTION", key="cl_wc_map", use_container_width=True): 
                        st.session_state.selected_wtfda_county_intel = None
                        st.session_state.wtfda_county_intel_map_key += 1
                        st.rerun()
                        
                    # --- TARGET LOCK MINIMAP ---
                    st.markdown('<div class="stat-header">TARGET LOCK MINIMAP</div>', unsafe_allow_html=True)
                    state_map_df = wtfda_df[wtfda_df['S/P'] == c_state].dropna(subset=['FIPS']).groupby('FIPS').size().reset_index(name='Stations')
                    state_map_df['Highlight'] = np.where(state_map_df['FIPS'] == sel_fips, 'Target', 'Other')
                    
                    fig_mini = px.choropleth(state_map_df, geojson='https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json', locations='FIPS', color='Highlight', color_discrete_map={'Target': th_red, 'Other': th_panel})
                    fig_mini.update_geos(fitbounds="locations", visible=False)
                    fig_mini.update_layout(showlegend=False, margin={"r":0,"t":10,"l":0,"b":10}, height=200, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_mini, use_container_width=True)

                    total_avail = len(s_intel_df)
                    st.markdown(f'<div class="stat-header">TOTAL STATIONS IN {c_type}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{total_avail:,}</div>', unsafe_allow_html=True)
                    
                    # LOGGED VS AVAILABLE MATH
                    if 'FIPS' in filt_df.columns:
                        logged_in_county = filt_df[filt_df['FIPS'] == sel_fips]
                        logged_stations = logged_in_county['Station'].dropna().str.upper().str.strip().unique()
                    else:
                        logged_stations = []
                        
                    s_intel_df['Match_Call'] = s_intel_df['Callsign'].str.upper().str.strip()
                    logged_count = s_intel_df[s_intel_df['Match_Call'].isin(logged_stations)].shape[0]
                    pct_logged = (logged_count / total_avail) * 100 if total_avail > 0 else 0
                    
                    st.markdown('<div class="stat-header">NETWORK PENETRATION</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val" style="color:{th_yellow};">{pct_logged:.1f}%</div><div class="stat-label">{logged_count} of {total_avail} stations historically logged</div>', unsafe_allow_html=True)

                    pi_ct = len(s_intel_df[s_intel_df['Has_PI'] == 'Yes'])
                    pi_pt = (pi_ct / total_avail) * 100 if total_avail > 0 else 0
                    st.markdown('<div class="stat-header">RDS PI ADOPTION</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="stat-val">{pi_pt:.1f}%</div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="stat-header">TOP 3 CITIES</div>', unsafe_allow_html=True)
                    city_counts = s_intel_df['City'].value_counts().reset_index(name='Stations').head(3)
                    city_counts['%'] = (city_counts['Stations'] / total_avail) * 100
                    city_counts['M'] = city_counts['%']
                    st.dataframe(city_counts, column_config={"%": st.column_config.NumberColumn("%", format="%.1f%%"), "M": st.column_config.ProgressColumn("", format="", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)
                    
                    st.markdown('<div class="stat-header">TOP 5 FREQUENCIES</div>', unsafe_allow_html=True)
                    freq_counts = s_intel_df['Frequency'].value_counts().reset_index(name='Stations').head(5)
                    freq_counts['%'] = (freq_counts['Stations'] / total_avail) * 100
                    freq_counts['M'] = freq_counts['%']
                    st.dataframe(freq_counts, column_config={"%": st.column_config.NumberColumn("%", format="%.1f%%"), "M": st.column_config.ProgressColumn("", format="", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)
                    
                    st.markdown('<div class="stat-header">TOP 5 FORMATS</div>', unsafe_allow_html=True)
                    fmt_counts = s_intel_df[s_intel_df['Format'] != 'Unknown']['Format'].value_counts().reset_index(name='Stations').head(5)
                    fmt_counts['%'] = (fmt_counts['Stations'] / total_avail) * 100
                    fmt_counts['M'] = fmt_counts['%']
                    st.dataframe(fmt_counts, column_config={"%": st.column_config.NumberColumn("%", format="%.1f%%"), "M": st.column_config.ProgressColumn("", format="", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)

                    st.markdown('<div class="stat-header">🎯 UNHEARD STATION TARGETS</div>', unsafe_allow_html=True)
                    st.caption(f"The following {total_avail - logged_count} stations have never been logged in the FMList dataset. Happy hunting!")
                    
                    unheard_df = s_intel_df[~s_intel_df['Match_Call'].isin(logged_stations)].sort_values(['Frequency', 'Callsign'])
                    if not unheard_df.empty:
                        unheard_df['Target'] = unheard_df['Frequency'].astype(str) + " - " + unheard_df['Callsign'] + " - " + unheard_df['City']
                        st.dataframe(unheard_df[['Target']], height=300, hide_index=True, use_container_width=True)
                    else:
                        st.success(f"100% Penetration! Every station in this {c_type.lower()} has been logged.")

# 13. MODULE 8: ATMOSPHERIC CORRELATION
elif selected_page == "ATMOSPHERIC CORRELATION":
    st.markdown(f"<h1 style='text-align: center; color: {th_red};'>ATMOSPHERIC CORRELATION</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    solar_df = load_solar_data()
    if solar_df.empty:
        st.warning("🚨 **Space Weather Database Offline**")
        st.markdown("We could not locate the `solar_data_master` table in BigQuery or the local `sedap_solar_clean.csv` fallback file. Please ensure the data is uploaded correctly.")
    else:
        # Prepare Data Merge
        daily_logs = filt_df.groupby('Date_Obj').size().reset_index(name='Logs')
        
        # Perform the Inner Join matching FM logs to Space Weather by Date
        merged_df = pd.merge(daily_logs, solar_df, on='Date_Obj', how='inner').sort_values('Date_Obj')
        
        if merged_df.empty:
            st.warning("No overlapping dates found between the active filters and the Space Weather database.")
        else:
            # -------------------------------------------------------------
            # DUAL-AXIS TEMPORAL OVERLAY
            # -------------------------------------------------------------
            st.markdown("### 🔭 DUAL-AXIS TEMPORAL OVERLAY")
            st.caption("Compare your filtered log volume directly against space weather indices over time.")
            
            overlay_metric = st.radio("Select Overlay Metric:", ["SFI (10.7cm Radio Flux)", "Kp-Index (Geomagnetic Storming)"], horizontal=True)
            
            fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
            fig_dual.add_trace(
                go.Bar(x=merged_df['Date_Obj'], y=merged_df['Logs'], name="Total Logs", marker_color=th_red, opacity=0.95),
                secondary_y=False
            )
            
            if overlay_metric == "SFI (10.7cm Radio Flux)":
                fig_dual.add_trace(
                    go.Scatter(x=merged_df['Date_Obj'], y=merged_df['F107_Obs'], name="Solar Flux (SFI)", mode='lines', line=dict(color=th_yellow, width=2)),
                    secondary_y=True
                )
                fig_dual.update_yaxes(title_text="Solar Flux Index (SFI)", secondary_y=True, showgrid=False)
            else:
                fig_dual.add_trace(
                    go.Scatter(x=merged_df['Date_Obj'], y=merged_df['Kp_Max'], name="Max Kp-Index", mode='lines', line=dict(color=th_blue, width=2)),
                    secondary_y=True
                )
                fig_dual.update_yaxes(title_text="Maximum Kp-Index", secondary_y=True, showgrid=False, range=[0, 9])
                
                # Earmark Storm Zones (Kp >= 5)
                storm_days = merged_df[merged_df['Kp_Max'] >= 5]['Date_Obj']
                for storm_day in storm_days:
                    fig_dual.add_vrect(
                        x0=storm_day - datetime.timedelta(hours=12), 
                        x1=storm_day + datetime.timedelta(hours=12), 
                        fillcolor="red", opacity=0.2, layer="below", line_width=0
                    )
                    
            fig_dual.update_layout(template=plotly_tmpl, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=750, hovermode="x unified")
            fig_dual.update_yaxes(title_text="Total Logs", secondary_y=False)
            
            # --- DYNAMIC TIME-WARPING (Remove Off-Season Gaps) ---
            d_min = pd.to_datetime(merged_df['Date_Obj'].min())
            d_max = pd.to_datetime(merged_df['Date_Obj'].max())
            all_d = pd.date_range(d_min, d_max)
            # Filter for off-season months (Sept through April)
            off_season = all_d[~all_d.month.isin([5, 6, 7, 8])]
            
            if not off_season.empty:
                fig_dual.update_xaxes(rangebreaks=[dict(values=off_season.strftime("%Y-%m-%d").tolist())])
                
            st.plotly_chart(fig_dual, use_container_width=True)

            st.markdown("---")
            
            # -------------------------------------------------------------
            # CORRELATION SCATTER MATRIX
            # -------------------------------------------------------------
            c1, c2 = st.columns(2)
            
            with c1:
                st.markdown("### ⚛️ PHYSICS SCATTER MATRIX")
                st.caption("Does Sporadic Es prefer a quiet or active sun? Each dot represents a single day.")
                
                fig_scatter = px.scatter(
                    merged_df.dropna(subset=['F107_Obs', 'Kp_Max']), 
                    x='F107_Obs', y='Logs', color='Kp_Max', 
                    hover_data=['Date_Obj'],
                    color_continuous_scale='Turbo', 
                    template=plotly_tmpl,
                    labels={"F107_Obs": "Solar Flux Index (SFI)", "Logs": "Logs per Day", "Kp_Max": "Max Kp"}
                )
                fig_scatter.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=450)
                st.plotly_chart(fig_scatter, use_container_width=True)
                
            # -------------------------------------------------------------
            # SWEET SPOT RADAR
            # -------------------------------------------------------------
            with c2:
                st.markdown("### 🎯 THE SWEET SPOT RADAR")
                st.caption("Probability mapping of log occurrence across the A-Index vs. SFI grid.")
                
                # Clean dropna for math
                hm_df = merged_df.dropna(subset=['F107_Obs', 'Ap']).copy()
                
                # Create Bins
                hm_df['SFI_Bin'] = pd.cut(hm_df['F107_Obs'], bins=[0, 75, 100, 150, 200, 999], labels=['<75', '75-100', '100-150', '150-200', '200+'])
                hm_df['Ap_Bin'] = pd.cut(hm_df['Ap'], bins=[-1, 5, 10, 20, 40, 999], labels=['0-5 (Quiet)', '6-10 (Unsettled)', '11-20 (Active)', '21-40 (Minor Storm)', '40+ (Major Storm)'])
                
                # Calculate average logs per day for that specific weather grid combo
                heat_pivot = hm_df.pivot_table(index='Ap_Bin', columns='SFI_Bin', values='Logs', aggfunc='mean').fillna(0)
                
                # Reorder index to put quiet weather at the bottom
                heat_pivot = heat_pivot.reindex(['40+ (Major Storm)', '21-40 (Minor Storm)', '11-20 (Active)', '6-10 (Unsettled)', '0-5 (Quiet)'])
                
                # Format to integers for readability
                heat_text = heat_pivot.round(0).astype(int).astype(str)
                heat_text[heat_pivot == 0] = ""
                
                fig_heat = px.imshow(
                    heat_pivot, 
                    text_auto=False, 
                    color_continuous_scale=global_color_scale, 
                    template=plotly_tmpl, 
                    aspect="auto",
                    labels=dict(x="Solar Flux Index (SFI)", y="Planetary A-Index (Ap)", color="Avg Logs/Day")
                )
                fig_heat.update_traces(text=heat_text.values, texttemplate="%{text}")
                fig_heat.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=450, coloraxis_showscale=False)
                st.plotly_chart(fig_heat, use_container_width=True)

# 14. MODULE 9: 6M WSPR INTELLIGENCE (NEW)
elif selected_page == "6M WSPR INTELLIGENCE":
    st.markdown(f"<h1 style='text-align: center; color: {th_red};'>6M WSPR CLOUD TRACKER (50 MHz)</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    wspr_df = load_wspr_data()
    
    if wspr_df.empty:
        st.warning("🚨 **WSPR Database Offline**")
        st.markdown("We could not locate the `wspr_clouds_master` table in BigQuery or the local `sedap_wspr_clouds.csv` fallback file. Please ensure the exact file is uploaded and available.")
    else:
        w1, w2, w3, w4 = st.columns(4)
        w1.metric("Total 50 MHz Clouds Mapped", f"{len(wspr_df):,}")
        w2.metric("Active 6m Days", f"{wspr_df['Date_Obj'].nunique():,}")
        w3.metric("Furthest WSPR Path", f"{wspr_df['Distance_mi'].max():,.0f} mi")
        w4.metric("Avg Hop Distance", f"{wspr_df['Distance_mi'].mean():,.0f} mi")
        
        st.markdown("### 📡 50 MHz IONOSPHERIC RADAR")
        st.caption("Select a date to track the exact geographic formation of 50 MHz Sporadic E clouds. Data is natively displayed in UTC.")
        
        avail_wspr_days = sorted(wspr_df['Date_Obj'].unique())
        # Try to default to the mega-day we found earlier, otherwise just use the last available day
        target_default = datetime.date(2022, 6, 19)
        default_day = target_default if target_default in avail_wspr_days else avail_wspr_days[-1]
        
        col_map, col_ctrl = st.columns([3, 1])
        
        with col_ctrl:
            wspr_date = st.date_input("Select Event Date", value=default_day, min_value=avail_wspr_days[0], max_value=avail_wspr_days[-1])
            day_wspr = wspr_df[wspr_df['Date_Obj'] == wspr_date].copy()
            
            if day_wspr.empty:
                st.warning("No WSPR clouds mapped on this date.")
            else:
                day_wspr = day_wspr.sort_values('Time_Str')
                times_only = sorted(day_wspr['Time_Str'].dropna().unique())
                w_time = st.select_slider("Time Control (UTC)", options=["SHOW ALL"] + times_only, value="SHOW ALL")
                
                st.markdown('<div class="stat-header">HOP CLASSIFICATION</div>', unsafe_allow_html=True)
                if 'Hop_Type' in day_wspr.columns:
                    hop_counts = day_wspr['Hop_Type'].value_counts().reset_index(name='Clouds').rename(columns={'Hop_Type': 'Type'})
                    st.dataframe(hop_counts, hide_index=True, use_container_width=True)
                    
                st.markdown('<div class="stat-header">CLOUDS TRACKED THIS DAY</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="stat-val">{len(day_wspr):,}</div>', unsafe_allow_html=True)

        with col_map:
            if not day_wspr.empty:
                if w_time == "SHOW ALL":
                    render_w = day_wspr
                    st.markdown(f"**Viewing All Clouds on {wspr_date.strftime('%b %d, %Y')}**")
                else:
                    # Show clouds within a 1-hour rolling window of the selected time
                    lookback_time_w = (datetime.datetime.strptime(w_time, '%H:%M') - datetime.timedelta(minutes=60)).strftime('%H:%M')
                    render_w = day_wspr[(day_wspr['Time_Str'] <= w_time) & (day_wspr['Time_Str'] >= lookback_time_w)]
                    st.markdown(f"**Viewing Clouds from {lookback_time_w} to {w_time} UTC**")
                    
                if 'Cloud_Lat' in render_w.columns and 'Cloud_Lon' in render_w.columns:
                    layer_w = pdk.Layer(
                        'HeatmapLayer',
                        data=render_w[['Cloud_Lon', 'Cloud_Lat']].dropna(),
                        get_position='[Cloud_Lon, Cloud_Lat]',
                        radius_pixels=50, intensity=2.0, threshold=0.03,
                        color_range=[[183, 28, 28, 60], [211, 47, 47, 150], [244, 67, 54, 200], [255, 235, 238, 230], [255, 255, 255, 255]]
                    )
                    st.pydeck_chart(pdk.Deck(map_style=map_style_url, initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=3.4), layers=[layer_w]))
                else:
                    st.error("Missing Cloud_Lat or Cloud_Lon columns in the WSPR dataset.")

        st.markdown("---")
        st.markdown("### 🧬 THE OVERLAP: 50 MHz vs 100+ MHz")
        st.caption("Which days had both a massive 50 MHz WSPR cloud formation AND explosive 100+ MHz broadcast logs? This scatter plot automatically cross-references your FM filters against the WSPR database.")
        
        # Overlap Logic built directly into pandas
        fm_daily = filt_df.groupby('Date_Obj').size().reset_index(name='FM_Logs')
        wspr_daily = wspr_df.groupby('Date_Obj').size().reset_index(name='WSPR_Clouds')
        
        overlap_df = pd.merge(fm_daily, wspr_daily, on='Date_Obj', how='inner')
        overlap_df['Intensity_Score'] = overlap_df['FM_Logs'] * overlap_df['WSPR_Clouds']
        overlap_df = overlap_df.sort_values('Intensity_Score', ascending=False)
        
        if not overlap_df.empty:
            fig_over = px.scatter(
                overlap_df, x='WSPR_Clouds', y='FM_Logs', size='Intensity_Score', color='Intensity_Score',
                hover_name='Date_Obj', text='Date_Obj', template=plotly_tmpl, color_continuous_scale='Turbo'
            )
            fig_over.update_traces(textposition='top center')
            fig_over.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_title="Total 6m WSPR Clouds", yaxis_title="Filtered FM Broadcast Logs", height=500)
            st.plotly_chart(fig_over, use_container_width=True)
        else:
            st.info("No overlapping dates found between the WSPR dataset and the current FM Log filters.")
