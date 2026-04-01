import streamlit as st
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

# 1. THEME & STYLING
st.set_page_config(layout="wide", page_title="Sporadic Es Data Analysis")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@300;400;700&display=swap');
    
    html, body, [class*="st-"] {
        font-family: 'Oswald', sans-serif;
        background-color: #000000;
        color: #FFFFFF;
    }
    
    h1, h2, h3, h4 { color: #D32F2F !important; font-weight: 700; text-transform: uppercase; }
    [data-testid="stMetricValue"] { color: #FFFFFF !important; font-size: 2.2rem; }
    [data-testid="stMetricLabel"] { color: #D32F2F !important; font-size: 1.1rem; text-transform: uppercase; }

    /* RESET BUTTON: Pure Red, White Text, Perfectly Centered */
    div.stButton > button {
        background-color: #D32F2F !important;
        color: white !important;
        border-radius: 25px !important;
        border: none !important;
        padding: 10px 40px !important;
        font-family: 'Oswald', sans-serif !important;
        background-image: none !important;
        width: 100%; /* Spans its column for centering */
    }
    div.stButton > button p, div.stButton > button div, div.stButton > button span {
        background-color: transparent !important;
        background: transparent !important;
    }
    div.stButton > button:hover {
        background-color: #b22828 !important;
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING
@st.cache_data(ttl=3600)
def load_data():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/bigquery", "https://www.googleapis.com/auth/drive.readonly"]
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = bigquery.Client(credentials=credentials, project=credentials.project_id, location="US")
        query = "SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_data_raw`"
        return client.query(query).to_dataframe()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame()

df = load_data()
if df.empty: st.stop()

# 3. LOGO
st.image("SEDAP Banner.png", width=800)

# 4. RESET LOGIC
def reset_all():
    for key in st.session_state.keys():
        if key.startswith("filt_"):
            st.session_state[key] = "All"

# 5. FILTERS GRID (Cleaned up label)
with st.expander("GLOBAL FILTERS", expanded=True):
    r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
    f_freq = r1c1.selectbox("Frequency", ["All"] + sorted(df['Frequency'].dropna().unique().astype(str).tolist()), key="filt_freq")
    f_dxer = r1c2.selectbox("DXer Name", ["All"] + sorted(df['DXer'].dropna().unique().tolist()), key="filt_dxer")
    f_station = r1c3.selectbox("Station", ["All"] + sorted(df['Station'].dropna().unique().tolist()), key="filt_station")
    f_state = r1c4.selectbox("State", ["All"] + sorted(df['State'].dropna().unique().tolist()), key="filt_state")
    f_country = r1c5.selectbox("Country", ["All"] + sorted(df['Country'].dropna().unique().tolist()), key="filt_country")

    r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)
    f_dxer_co = r2c1.selectbox("DXer Country", ["All"] + sorted(df['DXer_Country'].dropna().unique().tolist()), key="filt_dx_co")
    f_dxer_st = r2c2.selectbox("DXer State", ["All"] + sorted(df['DXer_State_Prov'].dropna().unique().tolist()), key="filt_dx_st")
    f_month = r2c3.selectbox("Local Month", ["All"] + sorted(df['Local_Month'].dropna().unique().astype(str).tolist()), key="filt_month")
    f_year = r2c4.selectbox("Local Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key="filt_year")
    f_day = r2c5.selectbox("Month Day", ["All"] + sorted(df['Month_Day'].dropna().unique().astype(str).tolist()), key="filt_day")

    r3c1, r3c2, r3c3 = st.columns(3)
    f_dist = r3c1.selectbox("Distance Distribution", ["All"] + sorted(df['Distance_Distribution'].dropna().unique().tolist()), key="filt_dist")
    f_reg = r3c2.selectbox("DXer Region", ["All"] + sorted(df['DXer_Region'].dropna().unique().tolist()), key="filt_reg")
    rds_col = 'RDS_Decode_' if 'RDS_Decode_' in df.columns else 'RDS_Decode'
    f_rds = r3c3.selectbox("RDS Decode?", ["All"] + sorted(df[rds_col].dropna().unique().tolist()), key="filt_rds")

    # Perfectly Centered Reset Button
    bt_left, bt_mid, bt_right = st.columns([2, 1, 2])
    bt_mid.button("RESET ALL FILTERS", on_click=reset_all)

# 6. FILTERING LOGIC
filt_df = df.copy()
filter_map = {
    'Frequency': f_freq, 'DXer': f_dxer, 'Station': f_station, 'State': f_state,
    'Country': f_country, 'DXer_Country': f_dxer_co, 'DXer_State_Prov': f_dxer_st,
    'Local_Month': f_month, 'Local_Year': f_year, 'Month_Day': f_day,
    'Distance_Distribution': f_dist, 'DXer_Region': f_reg, rds_col: f_rds
}
for col, val in filter_map.items():
    if val != "All":
        filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# 7. CONTENT: GENERAL STATS
st.header("General Stats")

m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
m1.metric("Total Stations Logged", f"{len(filt_df):,}")
m2.metric("Unique Stations Heard", f"{filt_df['Station'].nunique():,}")
m3.metric("US States (Incl DC)", filt_df[filt_df['Country'] == 'USA']['State'].nunique())
m4.metric("Canadian Provinces", filt_df[filt_df['Country'] == 'Canada']['State'].nunique())
m5.metric("Mexican States", filt_df[filt_df['Country'] == 'Mexico']['State'].nunique())
m6.metric("Total Countries", filt_df['Country'].nunique())

dist_col = 'Distance__mi_' if 'Distance__mi_' in df.columns else 'Distance'
max_d = filt_df[dist_col].max() if not filt_df.empty else 0
m7.metric("Furthest Reception", f"{max_d:,.0f} mi")

# 8. SUBMITTED LOGS TABLE
st.subheader("Submitted Logs")

# Fake Pagination: Row Count Selector
row_count = st.slider("Number of rows to display", 10, 500, 100)

table_cols = [
    'Local_Date', 'Local_Time', 'Frequency', 'Station', 'City', 'State', 
    'Country', 'Local_Month', 'DXer', 'DXer_Concatenated_Location', dist_col
]
display_cols = [c for c in table_cols if c in filt_df.columns]

st.dataframe(
    filt_df[display_cols].head(row_count), 
    use_container_width=True, 
    hide_index=True,
    column_config={
        "DXer_Concatenated_Location": st.column_config.TextColumn(width="large"),
        "Station": st.column_config.TextColumn(width="medium"),
        "Frequency": st.column_config.NumberColumn(format="%.1f"),
    }
)

csv = filt_df.to_csv(index=False).encode('utf-8')
st.download_button("EXPORT TABLE TO CSV", data=csv, file_name="submitted_logs.csv", mime="text/csv")
