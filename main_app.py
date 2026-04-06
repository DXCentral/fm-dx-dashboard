import streamlit as st
import pandas as pd
import pydeck as pdk
import time
import datetime

# ... (Theme & Loading Code from V34 stays the same) ...

# 4. ES-CLOUD TRACKER PAGE
if selected_page == "ES-CLOUD TRACKER":
    st.header("Ionospheric Propagation Analysis")
    
    view_mode = st.radio("SELECT MAP LAYER", ["Midpoint Heatmap (Es-Cloud)", "Path Line Analysis (Signal Grid)"], horizontal=True)
    
    hc1, hc2 = st.columns([1, 2])
    avail_dates = sorted(filt_df['Date_Obj'].unique())
    date_range = hc1.date_input("Event Date Range", value=(avail_dates[0], avail_dates[-1]))
    
    # Date Filtering
    if isinstance(date_range, tuple) and len(date_range) == 2:
        map_df = filt_df[(filt_df['Date_Obj'] >= date_range[0]) & (filt_df['Date_Obj'] <= date_range[1])]
    else:
        map_df = filt_df[filt_df['Date_Obj'] == date_range]

    if not map_df.empty:
        times = sorted(map_df['Time_Str'].dropna().unique().tolist())
        
        # KEY FIX: Better state management for the loop
        if 'anim_idx' not in st.session_state: st.session_state.anim_idx = 0
        if 'is_playing' not in st.session_state: st.session_state.is_playing = False

        # Slider follows the animation index
        selected_time = hc2.select_slider(
            "Timing Control", 
            options=["SHOW ALL"] + times, 
            value=times[st.session_state.anim_idx] if st.session_state.is_playing else "SHOW ALL"
        )
        
        # Playback Controls
        btn1, btn2, btn3 = st.columns([1, 1, 1])
        
        if btn1.button("▶ PLAY TIMELAPSE"):
            st.session_state.is_playing = True
            # We start from the current position and go to the end
            for i in range(st.session_state.anim_idx, len(times)):
                st.session_state.anim_idx = i
                # Slight delay to allow the "Heat" to render on screen
                time.sleep(0.15) 
                st.rerun()
            st.session_state.is_playing = False # Stop when reaching the end

        if btn2.button("⏹ STOP / RESET"):
            st.session_state.is_playing = False
            st.session_state.anim_idx = 0
            st.rerun()

        # 4c. THE MAP RENDERER (Wrapped in a placeholder for stability)
        map_placeholder = st.empty()
        
        # Decide which data to show
        current_view_time = times[st.session_state.anim_idx] if st.session_state.is_playing else selected_time
        
        if current_view_time != "SHOW ALL":
            # 60-minute trailing window for the "Heatmap" persistence
            sel_dt = datetime.datetime.strptime(current_view_time, '%H:%M')
            win_start = (sel_dt - datetime.timedelta(minutes=60)).strftime('%H:%M')
            render_df = map_df[(map_df['Time_Str'] <= current_view_time) & (map_df['Time_Str'] >= win_start)]
        else:
            render_df = map_df

        # Layer Logic
        layers = []
        if view_mode == "Midpoint Heatmap (Es-Cloud)":
            map_ready = render_df[['Mid_Lat', 'Mid_Lon']].dropna()
            layers.append(pdk.Layer(
                'HeatmapLayer', data=map_ready, get_position='[Mid_Lon, Mid_Lat]',
                radius_pixels=80, intensity=3, threshold=0.01,
                color_range=[[211, 47, 47, 50], [211, 47, 47, 180], [255, 255, 255, 255]]
            ))
        else:
            map_ready = render_df[['DX_Lat', 'DX_Lon', 'ST_Lat', 'ST_Lon']].dropna()
            layers.append(pdk.Layer(
                'LineLayer', data=map_ready,
                get_source_position='[DX_Lon, DX_Lat]', get_target_position='[ST_Lon, ST_Lat]',
                get_width=1, get_color=[211, 47, 47, 40]
            ))

        # Render into the placeholder
        with map_placeholder:
            st.pydeck_chart(pdk.Deck(
                map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
                initial_view_state=pdk.ViewState(latitude=38, longitude=-95, zoom=3.8, pitch=0),
                layers=layers
            ))
            # If we are playing, show the current timestamp on the map
            if st.session_state.is_playing:
                st.markdown(f"### 🕒 CURRENT TIME: {current_view_time}")
