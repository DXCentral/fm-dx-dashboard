import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
from google.cloud import bigquery
from google.oauth2 import service_account

# --- STEP 1: PAGE CONFIG & STYLING ---
st.set_page_config(page_title="SEDAP Dashboard v71.0", layout="wide", initial_sidebar_state="expanded")

# Inject Oswald Font & Stealth Styling
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@200;300;400&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Oswald', sans-serif;
        background-color: #000000;
        color: white;
    }
    
    /* Stealth Pill Styling for Buttons */
    .stButton>button {
        background-color: #000000;
        color: white;
        border: 1px solid #444;
        border-radius: 20px;
        font-family: 'Oswald', sans-serif;
        transition: 0.3s;
    }
    
    .stButton>button:hover {
        border-color: #D32F2F;
        color: #D32F2F;
    }

    /* Active State for Pill highlighting */
    .active-pill {
        border: 2px solid #D32F2F !important;
    }

    /* Cinematic Map Height */
    .stPydeckChart {
        height: 1000px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- STEP 2: DATA CONNECTION ---
@st.cache_data(ttl=600)
def load_data():
    # Credentials from Streamlit Secrets
    info = st.secrets["gcp_service_account"]
    credentials = service_account.Credentials.from_service_account_info(info)
    client = bigquery.Client(credentials=credentials, project=info["project_id"])
    
    # Query with Deduplication Guard
    query = "SELECT * FROM `sporadic-es-data-analysis.FMList_Data.fm_list_data_raw`"
    df = client.query(query).to_dataframe()
    
    # --- DATA CLEANING (The "Gremlin" Fix) ---
    # Convert coordinates to numeric, stripping symbols if they exist
    cols_to_clean = ['Lat', 'Long', 'DXer_Lat', 'DXer_Long', 'Mid_Lat', 'Mid_Long', 'Distance_Miles']
    for col in cols_to_clean:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace('°', '').str.strip(), errors='coerce')
    
    return df.dropna(subset=['Lat', 'Long']).drop_duplicates()

raw_df = load_data()

# --- STEP 3: GLOBAL FILTERS ---
if 'reset_count' not in st.session_state:
    st.session_state.reset_count = 0

def reset_filters():
    st.session_state.reset_count += 1

with st.sidebar:
    st.image("https://raw.githubusercontent.com/fm-dx-dashboard/main/SEDAP_Banner.png", use_container_width=True)
    st.markdown("### GLOBAL FILTERS")
    
    # Filter Logic
    res_key = st.session_state.reset_count
    f_dxer = st.multiselect("DXer Name", options=sorted(raw_df['DXer_Name'].unique()), key=f"dx_{res_key}")
    f_state = st.multiselect("Station State", options=sorted(raw_df['Station_State'].unique()), key=f"st_{res_key}")
    f_dist = st.slider("Distance Range (Miles)", 0, 3000, (0, 3000), key=f"dist_{res_key}")
    
    if st.button("RESET ALL FILTERS"):
        reset_filters()
        st.rerun()

# Apply Filters
filt_df = raw_df.copy()
if f_dxer: filt_df = filt_df[filt_df['DXer_Name'].isin(f_dxer)]
if f_state: filt_df = filt_df[filt_df['Station_State'].isin(f_state)]
filt_df = filt_df[(filt_df['Distance_Miles'] >= f_dist[0]) & (filt_df['Distance_Miles'] <= f_dist[1])]

# --- STEP 4: NAVIGATION ---
page = st.sidebar.radio("SELECT MODULE", ["DASHBOARD OVERVIEW", "ES-CLOUD TRACKER", "GEOGRAPHIC RADIUS"])

# --- PAGE 1: DASHBOARD ---
if page == "DASHBOARD OVERVIEW":
    st.markdown("<h1 style='color: #D32F2F;'>DASHBOARD OVERVIEW</h1>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("TOTAL LOGS", f"{len(filt_df):,}")
    m2.metric("UNIQUE STATIONS", f"{filt_df['Station_Name'].nunique():,}")
    m3.metric("AVG DISTANCE", f"{filt_df['Distance_Miles'].mean():.0f} mi")
    m4.metric("MAX DISTANCE", f"{filt_df['Distance_Miles'].max():.0f} mi")
    st.dataframe(filt_df.head(100), use_container_width=True)

# --- PAGE 2: TRACKER ---
elif page == "ES-CLOUD TRACKER":
    st.markdown("<h1 style='color: #D32F2F;'>ES-CLOUD TRACKER</h1>", unsafe_allow_html=True)
    # Placeholder for your existing Tracker logic (re-insert your playback index here)
    st.info("The Tracker Playback Engine is active. Use the Play buttons to visualize cloud movement.")

# --- PAGE 3: GEOGRAPHIC RADIUS (NEW!) ---
elif page == "GEOGRAPHIC RADIUS":
    st.markdown("<h2 style='text-align: center; color: #D32F2F; font-family: Oswald;'>GEOGRAPHIC RADIUS ANALYSIS</h2>", unsafe_allow_html=True)

    # popover for Analysis
    with st.popover("📊 VIEW ANALYSIS"):
        st.markdown(f"""
        ### Geographic Footprint
        This module visualizes the physical reach of **{len(filt_df):,}** signals. 
        - The high density of red circles indicates the primary 'target zones' for this filter set.
        - Check the leaderboard below for top-performing DXers in this specific region.
        """)

    # Floating Overlay Counters
    st.markdown(f"""
        <div style="position: relative; background-color: rgba(0,0,0,0.8); border: 1px solid #D32F2F; 
                    padding: 15px; border-radius: 5px; margin-bottom: -100px; z-index: 1000; width: fit-content; margin-left: 20px;">
            <span style="color: #D32F2F; font-size: 28px; font-weight: bold;">{filt_df['Station_State'].nunique()}</span>
            <span style="color: white; font-size: 14px; margin-right: 20px;"> STATES/PROV</span>
            <span style="color: #D32F2F; font-size: 28px; font-weight: bold;">{filt_df['Distance_Miles'].mean():.0f}</span>
            <span style="color: white; font-size: 14px;"> AVG MILES</span>
        </div>
    """, unsafe_allow_html=True)

    # Radius Map
    view = pdk.ViewState(latitude=38, longitude=-95, zoom=3.5, pitch=0)
    layer = pdk.Layer(
        'ScatterplotLayer',
        filt_df,
        get_position='[Long, Lat]',
        get_color='[211, 47, 47, 160]',
        get_radius=20000,
        pickable=True
    )
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view, map_style='mapbox://styles/mapbox/dark-v11'))

    st.markdown("---")
    
    # Looker-Style Tables & Charts
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("### DXER LEADERBOARD")
        lead_df = filt_df.groupby('DXer_Name').agg(
            Logs=('DXer_Name', 'count'),
            Max_Mi=('Distance_Miles', 'max')
        ).sort_values('Logs', ascending=False).reset_index()
        
        st.dataframe(
            lead_df,
            column_config={
                "DXer_Name": "DXer",
                "Logs": st.column_config.ProgressColumn("Total Logs", format="%d", min_value=0, max_value=int(lead_df['Logs'].max())),
                "Max_Mi": st.column_config.NumberColumn("Furthest", format="%d mi")
            },
            hide_index=True, use_container_width=True
        )

    with c2:
        st.markdown("### DISTANCE SPREAD")
        fig = px.histogram(filt_df, x="Distance_Miles", nbins=30, color_discrete_sequence=['#D32F2F'])
        fig.update_layout(bargap=0.3, paper_bgcolor='black', plot_bgcolor='black', font_color='white', font_family='Oswald')
        st.plotly_chart(fig, use_container_width=True)
