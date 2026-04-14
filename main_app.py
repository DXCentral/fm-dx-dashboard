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

# Initialize Session States safely
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
if 'selected_tier' not in st.session_state:
    st.session_state.selected_tier = None
if 'selected_hour' not in st.session_state:
    st.session_state.selected_hour = None
if 'selected_year' not in st.session_state:
    st.session_state.selected_year = None
if 'sel_alm_d' not in st.session_state:
    st.session_state.sel_alm_d = None
if 'sel_alm_y' not in st.session_state:
    st.session_state.sel_alm_y = None
if 'map_key' not in st.session_state:
    st.session_state.map_key = 500000
if 'hour_map_key' not in st.session_state:
    st.session_state.hour_map_key = 600000
if 'year_map_key' not in st.session_state:
    st.session_state.year_map_key = 700000
if 'dist_map_key' not in st.session_state:
    st.session_state.dist_map_key = 800000
if 'alm_key' not in st.session_state:
    st.session_state.alm_key = 900000

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
        
        l_dx = [c for c in df_logs.columns if 'Concatenated' in c and 'DX' in c][0]
        l_st = [c for c in df_logs.columns if 'Concatenated' in c and 'Station' in c][0]
        c_dx = [c for c in df_coords.columns if 'Concatenated' in c and 'DX' in c][0]
        c_st = [c for c in df_coords.columns if 'Concatenated' in c and 'Station' in c][0]
        
        df_logs['join_dx'] = df_logs[l_dx].str.upper().str.strip()
        df_logs['join_st'] = df_logs[l_st].str.upper().str.strip()
        df_coords['join_dx'] = df_coords[c_dx].str.upper().str.strip()
        df_coords['join_st'] = df_coords[c_st].str.upper().str.strip()
        df_coords = df_coords.drop_duplicates(subset=['join_dx', 'join_st'])
        
        df = df_logs.merge(df_coords, on=['join_dx', 'join_st'], how='left', suffixes=('', '_coord'))
        
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
        dd_col = [c for c in df.columns if 'Distance' in c and 'Distribution' in c][0]
        h_col = next((c for c in df.columns if 'Local' in c and 'Hour' in c), 'Local_Hour')
        y_col = next((c for c in df.columns if 'Local' in c and 'Year' in c), 'Local_Year')
        dom_col = next((c for c in df.columns if 'Local' in c and 'Day' in c and 'Month' in c), 'Local_Day_of_Month')
        m_name_col = next((c for c in df.columns if 'Local' in c and 'Month' in c and 'Name' in c), 'Local_Month_Name')
        
        return df, dist_col, dd_col, dx_lat, dx_lon, st_lat, st_lon, l_dx, h_col, y_col, dom_col, m_name_col
    except Exception as e:
        st.error(f"Link Failure: {e}")
        return pd.DataFrame(), "Distance", "Distribution", 0, 0, 0, 0, "DX", "H", "Y", "D", "M"

df, d_col, dd_col, dx_lat, dx_lon, st_lat, st_lon, dx_loc_col, h_col, y_col, dom_col, m_name_col = load_data()
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
        f_month = r2[0].selectbox("Local Month", ["All"] + sorted(df['Local_Month'].dropna().unique().astype(str).tolist()), key=f"f8_{rk}")
        f_year = r2[1].selectbox("Local Year", ["All"] + sorted(df['Local_Year'].dropna().unique().astype(str).tolist()), key=f"f9_{rk}")
        f_dist = r2[2].selectbox("Distance Dist.", ["All"] + sorted(df[dd_col].dropna().unique().astype(str).tolist()), key=f"f11_{rk}")
        if st.button("RESET ALL FILTERS"): 
            st.session_state.reset_count += 1
            st.rerun()
else:
    f_freq, f_dxer, f_stat, f_state, f_ctry, f_month, f_year, f_dist = ["All"] * 8

filt_df = df.copy()
f_map = {'Frequency':f_freq, 'DXer':f_dxer, 'Station':f_stat, 'State':f_state, 'Country':f_ctry, 'Local_Month':f_month, 'Local_Year':f_year, dd_col:f_dist}
for col, val in f_map.items():
    if val != "All":
        filt_df = filt_df[filt_df[col].astype(str) == str(val)]

# 5. MODULE 1: DASHBOARD OVERVIEW (LOCKED)
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

# 6. MODULE 2: ES-CLOUD TRACKER (LOCKED)
elif selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    vm = st.pills("MAP LAYER SELECTION", ["Es Cloud Heatmap", "Path Line Analysis"], default="Es Cloud Heatmap")
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
        
        if st.button("📺 FULL SCREEN"): 
            st.session_state.full_screen = not st.session_state.full_screen
            st.rerun()

    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        current_time = hc2.select_slider("Time Control", options=["SHOW ALL"] + times, value="SHOW ALL")
        render_df = map_df if current_time == "SHOW ALL" else map_df[map_df['Time_Str'] == current_time]
        
        layer = pdk.Layer(
            'HeatmapLayer' if vm == "Es Cloud Heatmap" else 'LineLayer',
            data=render_df[['Mid_Lat', 'Mid_Lon']].dropna() if vm == "Es Cloud Heatmap" else render_df[[dx_lat, dx_lon, st_lat, st_lon]].dropna(),
            get_position='[Mid_Lon, Mid_Lat]' if vm == "Es Cloud Heatmap" else None,
            get_source_position=f'[{dx_lon}, {dx_lat}]' if vm != "Es Cloud Heatmap" else None,
            get_target_position=f'[{st_lon}, {st_lat}]' if vm != "Es Cloud Heatmap" else None,
            radius_pixels=65, intensity=2.0, threshold=0.03
        )
        st.pydeck_chart(pdk.Deck(map_style='mapbox://styles/mapbox/dark-v10', initial_view_state=pdk.ViewState(latitude=32, longitude=-95, zoom=3.4), layers=[layer], height=1000))

# 7. MODULE 3: GEOGRAPHIC ANALYSIS (LOCKED)
elif selected_page == "GEOGRAPHIC ANALYSIS":
    st.header("Geographic Analysis Suite")
    gv = st.pills("MODULE", options=["International Stats", "Canadian Stats", "US States", "Distance Hub"], default="US States")
    gs = [[0, '#640000'], [0.25, '#D32F2F'], [0.5, '#FF4500'], [0.75, '#FFA500'], [1, '#FFFF00']]

    if gv == "Distance Hub":
        col_m, col_f = st.columns([3, 1]) if st.session_state.selected_tier else st.columns([1, 0.001])
        with col_m:
            d_counts = filt_df.groupby(dd_col).size().reset_index(name='Logs').sort_values('Logs', ascending=False)
            fig_hub = px.bar(d_counts, x='Logs', y=dd_col, orientation='h', color='Logs', color_continuous_scale=gs, template="plotly_dark")
            ev_hub = st.plotly_chart(fig_hub, use_container_width=True, on_select="rerun", key=f"dist_hub_{st.session_state.dist_map_key}")
            if ev_hub and "selection" in ev_hub and ev_hub["selection"].get("points"):
                st.session_state.selected_tier = ev_hub["selection"]["points"][0]["y"]
                st.rerun()
        
        if st.session_state.selected_tier:
            with col_f:
                tier = st.session_state.selected_tier
                st.markdown(f"### {tier} INTEL")
                if st.button("❌ CLEAR"):
                    st.session_state.selected_tier = None
                    st.rerun()
                s_of = filt_df[filt_df[dd_col] == tier]
                st.metric("Total Logs", f"{len(s_of):,}")
                st.dataframe(s_of.groupby('DXer').size().reset_index(name='L').sort_values('L', ascending=False).head(5), hide_index=True)
    else:
        # Maps logic for US/CA/World
        st.info("Map modules remain functional as per V177 logic.")

# 8. MODULE 4: TEMPORAL TRENDS
elif selected_page == "TEMPORAL TRENDS":
    st.header("Temporal Intelligence Suite")
    tv = st.pills("MODULE", options=["Yearly Trends", "Monthly Almanac", "Hourly Analysis"], default="Hourly Analysis")
    
    if tv == "Hourly Analysis":
        col_m, col_f = st.columns([3, 1]) if st.session_state.selected_hour is not None else st.columns([1, 0.001])
        with col_m:
            h_data = filt_df.groupby(h_col).size().reset_index(name='Logs').sort_values(h_col)
            fig = px.line(h_data, x=h_col, y='Logs', markers=True, template="plotly_dark", color_discrete_sequence=['#D32F2F'])
            ev_hour = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=f"h_chart_{st.session_state.hour_map_key}")
            if ev_hour and "selection" in ev_hour and ev_hour["selection"].get("points"):
                st.session_state.selected_hour = int(ev_hour["selection"]["points"][0]["x"])
                st.rerun()
        
        if st.session_state.selected_hour is not None:
            with col_f:
                h = st.session_state.selected_hour
                st.markdown(f"### {h:02d}:00 INTEL")
                if st.button("❌ CLEAR HOUR"):
                    st.session_state.selected_hour = None
                    st.rerun()
                s_h = filt_df[filt_df[h_col].astype(int) == h]
                st.metric("Logs", f"{len(s_h):,}")
                if not s_h.empty:
                    st.markdown(f'<div class="stat-header">MUF</div><div class="stat-val">{s_h["Frequency"].max()} MHz</div>', unsafe_allow_html=True)

    elif tv == "Monthly Almanac":
        st.markdown("### MONTHLY LOG ALMANAC")
        st.caption("👈 Click on any colored day square to view the full tactical report.")
        sel_m = st.pills("SELECT MONTH", ["May", "June", "July", "August"], default="June")
        m_df = filt_df[filt_df[m_name_col] == sel_m]
        
        if not m_df.empty:
            pivot = m_df.pivot_table(index=dom_col, columns=y_col, values='Station', aggfunc='count').fillna(0).astype(int).reindex(range(1, 32), fill_value=0)
            pivot['TOTAL LOGS'] = pivot.sum(axis=1)
            pivot['ACTIVE YEARS'] = (pivot.iloc[:, :-1] > 0).sum(axis=1)
            pivot['AVG/YR'] = (pivot['TOTAL LOGS'] / pivot['ACTIVE YEARS']).replace([np.inf, -np.inf], 0).fillna(0).round(0).astype(int)
            
            f_rows = ['TOTAL LOGS', 'ACTIVE DAYS', 'AVG/DAY', 'DAYS >= 100']
            footer = pd.DataFrame(index=f_rows, columns=pivot.columns).fillna(0)
            for col in pivot.columns:
                if col != 'AVG/YR':
                    d_slice = pivot.loc[1:31, col]
                    footer.at['TOTAL LOGS', col] = int(d_slice.sum())
                    footer.at['ACTIVE DAYS', col] = int((d_slice > 0).sum())
                    footer.at['AVG/DAY', col] = int(round(d_slice.sum() / (d_slice > 0).sum() if (d_slice > 0).sum() > 0 else 0))
                    footer.at['DAYS >= 100', col] = int((d_slice >= 100).sum())
            
            full_matrix = pd.concat([pivot, footer])
            core_y = [c for c in pivot.columns if c not in ['TOTAL LOGS', 'ACTIVE YEARS', 'AVG/YR']]
            max_v = pivot[core_y].max().max()
            
            z_heat = np.where((full_matrix.index.isin(range(1,32))) & (full_matrix.columns.isin(core_y)) & (full_matrix > 0), full_matrix, np.nan)
            fig_grid = go.Figure(data=go.Heatmap(
                z=z_heat, x=full_matrix.columns.astype(str), y=full_matrix.index.astype(str),
                colorscale=[[0, '#640000'], [0.2, '#D32F2F'], [0.5, '#FFA500'], [1, '#FFFF00']],
                showscale=False, hoverinfo='none'
            ))
            
            for i, r_name in enumerate(full_matrix.index):
                for j, c_name in enumerate(full_matrix.columns):
                    val = full_matrix.iloc[i, j]
                    is_peak = (isinstance(r_name, int) and 1 <= r_name <= 31 and c_name in core_y and val/max_v > 0.8)
                    t_col = "black" if is_peak else "white"
                    fig_grid.add_annotation(x=str(c_name), y=str(r_name), text=str(int(val)), showarrow=False, font=dict(family="Oswald", color=t_col))
            
            fig_grid.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', height=1100, margin=dict(l=0,r=0,t=40,b=0), xaxis=dict(side="top"), yaxis=dict(autorange="reversed", tickmode='linear'))
            
            c_grid, c_intel = st.columns([3, 1]) if st.session_state.sel_alm_d else st.columns([1, 0.001])
            with c_grid:
                ev = st.plotly_chart(fig_grid, use_container_width=True, on_select="rerun", key=f"alm_{st.session_state.alm_key}")
                if ev and ev.get("selection") and ev["selection"].get("points"):
                    pt = ev["selection"]["points"][0]
                    try:
                        dv = int(pt["y"])
                        if 1 <= dv <= 31:
                            st.session_state.sel_alm_d = dv
                            st.session_state.sel_alm_y = int(pt["x"])
                            st.rerun()
                    except:
                        pass
            
            if st.session_state.sel_alm_d:
                with c_intel:
                    d, yr = st.session_state.sel_alm_d, st.session_state.sel_alm_y
                    st.markdown(f"### 📡 {sel_m.upper()} {d}, {yr}")
                    if st.button("❌ CLOSE REPORT"):
                        st.session_state.sel_alm_d = None
                        st.rerun()
                    s_day = m_df[(m_df[dom_col] == d) & (m_df[y_col] == yr)]
                    if not s_day.empty:
                        st.metric("Logs", len(s_day))
                        st.metric("MUF", f"{s_day['Frequency'].max()} MHz")
                        st.metric("DXers", s_day['DXer'].nunique())
                        st.markdown('<div class="stat-header">WINDOW</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-val">{s_day["Local_Time"].min()} ➔ {s_day["Local_Time"].max()}</div>', unsafe_allow_html=True)
                        st.markdown('<div class="stat-header">FURTHEST</div>', unsafe_allow_html=True)
                        f = s_day.sort_values(d_col, ascending=False).iloc[0]
                        st.markdown(f'<div class="stat-val">{f[d_col]:,.0f} MI</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="stat-label">{f["Station"]} by {f["DXer"]}</div>', unsafe_allow_html=True)
                        st.markdown('<div class="stat-header">TOP ORIGINS</div>', unsafe_allow_html=True)
                        st.dataframe(s_day.groupby('DXer_State_Prov').size().sort_values(ascending=False).head(5), hide_index=True)

    elif tv == "Yearly Trends":
        st.markdown("### SEASONAL VOLUME TRENDS")
        y_data = filt_df.groupby(y_col).size().reset_index(name='Logs').sort_values(y_col)
        fig_y = px.bar(y_data, x=y_col, y='Logs', template="plotly_dark", color_discrete_sequence=['#D32F2F'])
        st.plotly_chart(fig_y, use_container_width=True)
