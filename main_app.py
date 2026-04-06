import streamlit as st
import pandas as pd
import pydeck as pdk
import time
import datetime
from google.cloud import bigquery
from google.oauth2 import service_account 

# 1. THEME & UI STYLING
st.set_page_config(layout="wide", page_title="SEDAP Control Center")

# NEW: Toggle for Broadcast Mode (Hides Streamlit UI)
if 'broadcast_mode' not in st.session_state: st.session_state.broadcast_mode = False

if st.session_state.broadcast_mode:
    # This CSS hides the sidebar, top header, and menu buttons for a clean recording
    st.markdown("""
        <style>
        [data-testid="stSidebar"], [data-testid="stHeader"], .st-emotion-cache-zq5m06 { display: none !important; }
        .stMain { padding: 0 !important; }
        .watermark { bottom: 100px !important; } /* Move logo up so controls don't overlap */
        </style>
        """, unsafe_allow_html=True)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@200;300;400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Oswald', sans-serif !important; background-color: #000000; color: #FFFFFF; font-weight: 300; }
    h1, h2, h3, h4 { color: #D32F2F !important; font-family: 'Oswald', sans-serif !important; text-transform: uppercase; letter-spacing: 3px; }
    [data-testid="stSidebar"] { background-color: #0A0A0A; border-right: 1px solid #1A1A1A; min-width: 320px !important; }
    div.stButton > button { background-color: #D32F2F !important; color: white !important; border-radius: 4px !important; border: none !important; padding: 8px 25px !important; text-transform: uppercase; width: 100%; }
    
    .watermark {
        position: absolute;
        bottom: 60px;
        right: 40px;
        opacity: 0.4;
        z-index: 1000;
        pointer-events: none;
    }
    
    /* Floating Playback Controls for Full Screen */
    .floating-controls {
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(0,0,0,0.8);
        padding: 10px 20px;
        border-radius: 50px;
        border: 1px solid #D32F2F;
        z-index: 2000;
    }
    </style>
    """, unsafe_allow_html=True)

# ... (Data Loading logic remains identical to v57) ...

# 6. ES-CLOUD TRACKER
if selected_page == "ES-CLOUD TRACKER":
    if not st.session_state.broadcast_mode:
        st.header("Ionospheric Propagation Analysis")
        view_mode = st.radio("SELECT MAP LAYER", ["Midpoint Heatmap (Es-Cloud)", "Path Line Analysis (Signal Grid)"], horizontal=True)
    else:
        # In broadcast mode, we default to the currently selected view mode
        view_mode = st.session_state.get('last_view_mode', "Midpoint Heatmap (Es-Cloud)")
    
    hc1, hc2 = st.columns([1, 2])
    
    # Selection Controls (Only show if NOT in broadcast mode)
    if not st.session_state.broadcast_mode:
        with hc1:
            date_sel = st.date_input("Select Event Date", value=sorted(df['Date_Obj'].unique())[-1])
            map_df = df[df['Date_Obj'] == date_sel]
            speed_settings = {"1x": {"delay": 0.2, "step": 1}, "2x": {"delay": 0.1, "step": 2}, "4x": {"delay": 0.01, "step": 4}}
            play_speed = st.selectbox("Playback Speed", options=list(speed_settings.keys()), index=1)
            st.session_state.last_speed = play_speed
            st.session_state.last_view_mode = view_mode
            
            if st.button("📺 ENTER BROADCAST MODE"):
                st.session_state.broadcast_mode = True
                st.rerun()
    else:
        # Carry over the data from session state
        map_df = df[df['Date_Obj'] == st.session_state.get('filt_date', sorted(df['Date_Obj'].unique())[-1])]
        play_speed = st.session_state.get('last_speed', "2x")
        speed_settings = {"1x": {"delay": 0.2, "step": 1}, "2x": {"delay": 0.1, "step": 2}, "4x": {"delay": 0.01, "step": 4}}

    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        
        # 6b. PLAYBACK LOGIC
        if 'p_idx' not in st.session_state: st.session_state.p_idx = 0
        if 'playing' not in st.session_state: st.session_state.playing = False

        # Draw the Map (Takes up full screen in Broadcast Mode)
        current_time = times[min(st.session_state.p_idx, len(times)-1)]
        
        t_obj = datetime.datetime.strptime(current_time, '%H:%M')
        t_start = (t_obj - datetime.timedelta(minutes=60)).strftime('%H:%M')
        render_df = map_df[(map_df['Time_Str'] <= current_time) & (map_df['Time_Str'] >= t_start)]

        layers = []
        if view_mode == "Midpoint Heatmap (Es-Cloud)":
            layers.append(pdk.Layer('HeatmapLayer', data=render_df[['Mid_Lat', 'Mid_Lon']].dropna(), get_position='[Mid_Lon, Mid_Lat]', radius_pixels=65, intensity=2.0, threshold=0.03,
                                   color_range=[[183, 28, 28, 60], [211, 47, 47, 150], [244, 67, 54, 200], [255, 235, 238, 230], [255, 255, 255, 255]]))
        else:
            layers.append(pdk.Layer('LineLayer', data=render_df[['DXer_Latitude', 'DXer_Longitude', 'Station_Lat', 'Station_Long']].dropna(), get_source_position='[DXer_Longitude, DXer_Latitude]', get_target_position='[Station_Long, Station_Lat]', get_width=1, get_color=[211, 47, 47, 45]))

        st.pydeck_chart(pdk.Deck(
            map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
            initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=4.5 if st.session_state.broadcast_mode else 4),
            layers=layers
        ))

        # 🏷️ BROADCAST CONTROLS (Bottom of Screen)
        bc1, bc2, bc3, bc4 = st.columns([1, 1, 1, 1])
        if st.session_state.broadcast_mode:
            with st.container():
                # We show minimal controls here for the recorder to capture
                if bc1.button("▶ START"):
                    st.session_state.playing = True
                    st.rerun()
                if bc2.button("⏹ STOP"):
                    st.session_state.playing = False
                    st.rerun()
                bc3.write(f"## 🕒 {current_time}")
                if bc4.button("❌ EXIT"):
                    st.session_state.broadcast_mode = False
                    st.session_state.playing = False
                    st.rerun()

        # 🏷️ WATERMARK
        st.markdown(f"""
            <div class="watermark">
                <img src="https://raw.githubusercontent.com/dxcentral/fm-dx-dashboard/main/SEDAP%20Banner.png" width="220">
            </div>
            """, unsafe_allow_html=True)
        
        # AUTO-ADVANCE
        if st.session_state.playing:
            conf = speed_settings[play_speed]
            if st.session_state.p_idx + conf['step'] < len(times):
                st.session_state.p_idx += conf['step']
                time.sleep(conf['delay'])
                st.rerun()
            else:
                st.session_state.playing = False
                st.rerun()
