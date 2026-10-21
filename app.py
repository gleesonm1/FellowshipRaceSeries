import streamlit as st
import pandas as pd
import numpy as np
import os
import html
import base64
from datetime import datetime, timezone

# Import your event configs and UI helper
from event_configs import EVENT_CONFIG, render_event_info

# --- 0. SETUP & CACHING ---
st.set_page_config(page_title="Fellowship Race Series", layout="wide")

# --- 0b. MOUNTAIN BANNER ---
# Ridgelines drawn back-to-front; each is filled black so nearer ridges hide the ones behind
ridges = [
    ("0,120 60,95 110,110 170,70 230,100 290,55 340,85 400,40 460,90 520,65 580,100 640,50 700,80 760,35 820,75 880,60 940,95 1000,45 1060,80 1120,60 1200,90", 0.5),
    ("0,150 80,120 140,135 210,95 270,130 330,105 390,140 450,100 510,125 570,85 630,130 700,110 760,140 830,95 890,120 950,100 1010,135 1080,105 1140,125 1200,110", 0.75),
    ("0,185 90,165 160,175 240,145 310,170 380,155 460,180 540,150 620,172 700,140 780,168 860,150 940,178 1020,155 1100,172 1200,160", 1.0),
]
ridge_paths = "".join(
    f'<path d="M{pts.replace(" ", " L")} L1200,200 L0,200 Z" fill="#000" '
    f'stroke="rgba(255,255,255,{op})" stroke-width="2" vector-effect="non-scaling-stroke"/>'
    for pts, op in ridges
)
# st.html strips inline <svg>, so embed it as a base64 background image instead
ridge_svg = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 200" preserveAspectRatio="none">'
    f'{ridge_paths}</svg>'
)
ridge_b64 = base64.b64encode(ridge_svg.encode()).decode()
st.html(f"""
<div style="position: relative; width: 100%; height: 170px; overflow: hidden; border-bottom: 1px solid #333;
            background: #000 url('data:image/svg+xml;base64,{ridge_b64}') no-repeat; background-size: 100% 100%;">
    <div style="position: absolute; left: 24px; top: 18px; color: #FFF; font-size: 2em; font-weight: 700; letter-spacing: 0.04em;">
        Fellowship Race Series
    </div>
</div>
""")

# --- 1. EXTERNAL LINKS ---
link_col1, link_col2, link_col3, _ = st.columns([2, 1, 1, 4])

# with link_col1:
#     logo_path = "icons/Fellowship.png"
#     if os.path.exists(logo_path):
#         st.image(logo_path, width=100)

# with link_col2:
#     st.link_button("Fellowship website", "")

st.markdown("<hr style='margin-top: 5px; margin-bottom: 5px;'>", unsafe_allow_html=True)

@st.cache_data

# --- 2. useful key functions ---
def load_excel_data(file_path, last_modified):
    """
    By adding last_modified as an argument, Streamlit will 
    automatically re-run this function whenever the file changes.
    """
    if os.path.exists(file_path):
        return pd.read_excel(file_path, sheet_name=None)
    return None

def clean_data(df):
    """Standardized cleaning for all sheets."""
    if 'name' in df.columns:
        df['name'] = df['name'].apply(lambda x: html.unescape(str(x)))
    if 'team_name' in df.columns:
        df['team_name'] = df['team_name'].apply(lambda x: html.unescape(str(x)) if pd.notnull(x) else "")
    return df.replace(['None', 'none', 'NaN'], '')

def format_egap(td):
    if pd.isna(td):
        return ""
    
    total_seconds = td.total_seconds()
    if total_seconds == 0:
        return "00.000 s"
        
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
    elif minutes > 0:
        return f"{minutes:02d}:{seconds:06.3f}"
    else:
        return f"{seconds:06.3f}"

def render_podium(df):
    """Renders a responsive 3-step podium for the top 3 riders in the filtered dataframe."""
    if df.empty or 'name' not in df.columns:
        return

    # Helper to safely extract rider info for index i
    def get_rider(idx):
        if idx < len(df):
            name = html.escape(str(df.iloc[idx].get('name', '-')))
            team = html.escape(str(df.iloc[idx].get('team_name', '')))
            if team.lower() in ['none', 'nan', '']:
                team = ""
            return name, team
        return "-", ""

    # Extract top 3 (Index 0 = 1st, 1 = 2nd, 2 = 3rd)
    p1_name, p1_team = get_rider(0)
    p2_name, p2_team = get_rider(1)
    p3_name, p3_team = get_rider(2)

    # textwrap.dedent removes leading whitespace/indentation so Streamlit doesn't render it as a code block
    podium_html = f"""
    <div style="display: flex; align-items: flex-end; justify-content: center; gap: 16px; margin: 20px 0 30px 0;">
        
        <!-- 2nd Place (Silver) -->
        <div style="flex: 1; max-width: 220px; text-align: center;">
            <div style="font-weight: 600; font-size: 0.95em; color: #E0E0E0; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{p2_name}">
                {p2_name}
            </div>
            <div style="font-size: 0.8em; color: #888; margin-bottom: 8px; height: 1.2em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{p2_team}">
                {p2_team}
            </div>
            <div style="background: linear-gradient(180deg, #C0C0C0 0%, #7F8C8D 100%); height: 80px; border-radius: 8px 8px 0 0; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 1.4em; box-shadow: 0 4px 10px rgba(0,0,0,0.3);">
                2nd
            </div>
        </div>

        <!-- 1st Place (Gold) -->
        <div style="flex: 1; max-width: 240px; text-align: center;">
            <div style="font-size: 1.1em; font-weight: 700; color: #FFD700; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{p1_name}">
                {p1_name}
            </div>
            <div style="font-size: 0.8em; color: #AAA; margin-bottom: 8px; height: 1.2em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{p1_team}">
                {p1_team}
            </div>
            <div style="background: linear-gradient(180deg, #FFD700 0%, #D4AF37 100%); height: 115px; border-radius: 8px 8px 0 0; display: flex; align-items: center; justify-content: center; color: #111; font-weight: bold; font-size: 1.6em; box-shadow: 0 6px 14px rgba(212,175,55,0.4);">
                1st
            </div>
        </div>

        <!-- 3rd Place (Bronze) -->
        <div style="flex: 1; max-width: 220px; text-align: center;">
            <div style="font-weight: 600; font-size: 0.95em; color: #E0E0E0; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{p3_name}">
                {p3_name}
            </div>
            <div style="font-size: 0.8em; color: #888; margin-bottom: 8px; height: 1.2em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{p3_team}">
                {p3_team}
            </div>
            <div style="background: linear-gradient(180deg, #CD7F32 0%, #8B4513 100%); height: 60px; border-radius: 8px 8px 0 0; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 1.3em; box-shadow: 0 4px 10px rgba(0,0,0,0.3);">
                3rd
            </div>
        </div>

    </div>
    """

    st.html(podium_html)

# --- 3. URL & NAVIGATION ---
event_list = list(EVENT_CONFIG.keys())
url_event = st.query_params.get("event", event_list[0])
event_idx = event_list.index(url_event) if url_event in event_list else 0

selected_event = st.radio("**Select Event**", options=event_list, index=event_idx, horizontal=True)
st.query_params["event"] = selected_event

# Load Data
config = EVENT_CONFIG[selected_event]
file_path = config["file"]

if os.path.exists(file_path):
    mtime = os.path.getmtime(file_path)
else:
    mtime = 0

# --- LAST UPDATED BOX ---
if mtime > 0:
    last_updated = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")
    with link_col3:
        st.markdown(
            f"""
            <div style="background-color:#1E1E1E; border:1px solid #333; border-radius:8px;
                        padding:6px 14px; margin-bottom:12px; display:inline-block;">
                <span style="color:#AAA; font-size:0.85em;">🕒 Last updated:</span>
                <span style="color:#FFD700; font-weight:600; font-size:0.85em; margin-left:4px;">{last_updated}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

all_sheets = load_excel_data(file_path, mtime)

if all_sheets is None:
    st.error(f"File not found: {config['file']}")
    st.stop()

# --- POSTER LAYOUT ---
# Poster sits beside the rules/results on wide screens; Streamlit stacks columns on narrow screens
poster = config.get("poster")
if poster and os.path.exists(poster):
    poster_col, main_col = st.columns([2, 3], gap="large")
    with poster_col:
        st.image(poster, width="stretch")
else:
    main_col = st.container()

with main_col:
    # --- RENDER EVENT RULES ---
    render_event_info(selected_event)


    # -----------------------------------

    # Handle Sheet selection via URL
    sheet_names = list(all_sheets.keys())
    url_sheet = st.query_params.get("sheet", config["default_sheet"])
    sheet_idx = sheet_names.index(url_sheet) if url_sheet in sheet_names else 0

    selected_sheet = st.selectbox("Select Leaderboard View", options=sheet_names, index=sheet_idx)
    st.query_params["sheet"] = selected_sheet

    # --- 4. DATA PROCESSING ---
    df = all_sheets[selected_sheet]
    if selected_sheet != "Team GC":
        df = clean_data(df)

    # 1. Create a temporary numeric time column for accurate sorting
    if selected_sheet != "e_gap":
        if 'total_time' in df.columns:
            # If a time is only "MM:SS.ms" (1 colon), prepend "00:" so pandas reads it as "HH:MM:SS.ms"
            time_str = df['total_time'].astype(str).apply(
                    lambda x: '00:' + x if x.count(':') == 1 
                    else ('00:00:' + x if x.count(':') == 0 
                    else x)
                )
            df['temp_sort_time'] = pd.to_timedelta(time_str, errors='coerce')
    elif selected_sheet == "e_gap":
        if 'e_gap' in df.columns:
            # Check if already float/int (seconds) or string time
            if pd.api.types.is_numeric_dtype(df['e_gap']):
                df['e_gap'] = pd.to_timedelta(df['e_gap'], unit='s')
            else:
                time_str = df['e_gap'].astype(str).apply(
                    lambda x: '00:' + x if x.count(':') == 1 
                    else ('00:00:' + x if x.count(':') == 0 
                    else x)
                )
                df['e_gap'] = pd.to_timedelta(time_str, errors='coerce')

    if "Round" in selected_sheet:
        # If a time is only "MM:SS.ms" (1 colon), prepend "00:" so pandas reads it as "HH:MM:SS.ms"
        time_str = df['time'+selected_sheet[-1]].astype(str).apply(
                lambda x: '00:' + x if x.count(':') == 1 
                else ('00:00:' + x if x.count(':') == 0 
                else x)
            )
        df['temp_sort_time'] = pd.to_timedelta(time_str, errors='coerce')

    # Apply Sorting from Config
    sort_cols, sort_orders = config["sorting"](selected_sheet)

    # 2. If 'total_time' is in the sorting logic, swap it for our temporary time column
    if 'total_time' in sort_cols and 'temp_sort_time' in df.columns:
        sort_cols = ['temp_sort_time' if c == 'total_time' else c for c in sort_cols]
    elif 'Round' in selected_sheet and 'temp_sort_time' in df.columns:
        sort_cols = ['temp_sort_time' if 'time' in c else c for c in sort_cols]

    # 3. Sort and reset index
    df = df.sort_values(by=sort_cols, ascending=sort_orders).reset_index(drop=True)

    # --- 5. UI & FILTERING ---
    st.title(f"🏆 {selected_event}: {selected_sheet}")
    m1, m2, m3, m4 = st.columns(4)
    st.divider()

    # Check which columns exist to build our filters
    has_pen = 'pen' in df.columns
    has_category = 'category' in df.columns
    has_age = 'age' in df.columns
    has_velo = 'velocategory' in df.columns

    if has_pen or has_category or has_age or has_velo:
        # Create two side-by-side columns for the filters
        if not has_velo:
            filter_col1, filter_col2, filter_col3 = st.columns(3)
        else:
            filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
    
        # Initialize defaults
        selected_pen = 'All'
        selected_cat = 'All'
        selected_age = 'All'
        selected_velo = 'All'
    
        if has_pen:
            with filter_col1:
                pen_options = ['All'] + sorted(df['pen'].dropna().unique().tolist())
                selected_pen = st.selectbox("Filter by pen", options=pen_options, index=0)

        if selected_sheet == "GC":       
            if has_category:
                if selected_sheet != "KQOM" and selected_sheet != "Sprints":
                    with filter_col2:
                        cat_options = ['All'] + sorted(df['category'].dropna().unique().tolist())
                        selected_cat = st.selectbox("Filter by category", options=cat_options, index=0)
        
            if has_age:
                if selected_sheet != "KQOM" and selected_sheet != "Sprints":
                    with filter_col3:
                        age_options = ['All'] + sorted(df['age'].dropna().unique().tolist())
                        selected_age = st.selectbox("Filter by age group", options=age_options, index=0)

            if has_velo:
                if selected_sheet != "KQOM" and selected_sheet != "Sprints":
                    with filter_col3:
                        velo_options = ['All'] + sorted(df['velocategory'].dropna().unique().tolist())
                        selected_velo = st.selectbox("Filter by vELO category", options=velo_options, index=0)

        # Apply the filters to a copy of the dataframe
        filtered_df = df.copy()
    
        if selected_pen != 'All':
            filtered_df = filtered_df[filtered_df['pen'] == selected_pen]
        
        if selected_cat != 'All':
            filtered_df = filtered_df[filtered_df['category'] == selected_cat]
    
        if selected_age != 'All':
            filtered_df = filtered_df[filtered_df['age'] == selected_age]

        if selected_velo != 'All':
            filtered_df = filtered_df[filtered_df['velocategory'] == selected_velo]
        
        # Re-sort strictly by time if 'All' is selected for either filter
        # if selected_pen == 'All' or selected_cat == 'All':
        if 'temp_sort_time' in filtered_df.columns:
            if selected_sheet == "GC":
                filtered_df = filtered_df.sort_values(by=['races','temp_sort_time'], ascending=[False,True])
            if selected_sheet == "Team GC":
                filtered_df = filtered_df.sort_values(by=['racers','temp_sort_time'], ascending=[False,True])
            if 'Round' in selected_sheet:
                filtered_df = filtered_df.sort_values(by=['temp_sort_time'], ascending=[True])
        elif 'total_time' in filtered_df.columns:
            if selected_sheet == "GC":
                filtered_df = filtered_df.sort_values(by=['races','total_time'], ascending=[False,True])
            elif selected_sheet == "Team GC":
                filtered_df = filtered_df.sort_values(by=['racers','total_time'], ascending=[False,True])
        elif 'e_gap' in filtered_df.columns:
            filtered_df = filtered_df.sort_values(by=['e_gap', 'total_time'], ascending=[True,True])
            
        filtered_df = filtered_df.reset_index(drop=True)
    else:
        filtered_df = df.copy()

    if 'temp_sort_time' in filtered_df.columns and not filtered_df.empty:
        # Find the max races and create a mask for those riders
        if "Round" not in selected_sheet:
            if 'races' in filtered_df.columns:
                max_races = filtered_df['races'].max()
                mask = filtered_df['races'] == max_races
            elif 'racers' in filtered_df.columns:
                max_races = filtered_df['racers'].max()
                mask = filtered_df['racers'] == max_races
        
            # Calculate the raw gap using the Timedelta column 
            # (Index 0 is guaranteed to be the fastest since we just sorted it)
            fastest_time = filtered_df.loc[0, 'temp_sort_time']
            raw_gaps = filtered_df.loc[mask, 'temp_sort_time'] - fastest_time
        
            # Helper function to convert Timedelta back to "+HH:MM:SS.ms" or "+MM:SS.ms"
            def format_gap(td):
                if pd.isna(td) or td.total_seconds() == 0:
                    return "00.000" # Leader / No gap
            
                total_sec = td.total_seconds()
                h = int(total_sec // 3600)
                m = int((total_sec % 3600) // 60)
                s = total_sec % 60
            
                if h > 0:
                    return f"+{h:02d}:{m:02d}:{s:06.3f}"
                else:
                    return f"+{m:02d}:{s:06.3f}"
                
            # Apply the formatted string back to your gap column
            filtered_df["time_offset"] = ""
            filtered_df.loc[mask, 'time_offset'] = raw_gaps.apply(format_gap)

    # 4. Clean up by dropping the temporary column so it doesn't show in the UI
    if 'temp_sort_time' in df.columns:
        df = df.drop(columns=['temp_sort_time'])
    if 'temp_sort_time' in filtered_df.columns:
        filtered_df = filtered_df.drop(columns=['temp_sort_time'])

    # Metric Logic
    if not filtered_df.empty:
        m1.metric("Total Participants", len(df))
        if 'pen' in filtered_df.columns:
            m2.metric("Filtered Count", len(filtered_df))
        if selected_event == "Spring Classics" or selected_event == "Total Non-Stop Power (iTT)":
            if 'avg_power' in filtered_df.columns:
                m3.metric("Highest Power", str(
                          np.round(filtered_df['avg_power'].loc[filtered_df['avg_power'] == filtered_df['avg_power'].max()].iloc[0])) + "W",
                          filtered_df['name'].loc[filtered_df['avg_power'] == filtered_df['avg_power'].max()].iloc[0])
            if 'avg_wkg' in filtered_df.columns:
                m4.metric("Highest W/kg", str(
                          np.round(filtered_df['avg_wkg'].loc[filtered_df['avg_wkg'] == filtered_df['avg_wkg'].max()].iloc[0],3)) + "W/kg",
                          filtered_df['name'].loc[filtered_df['avg_wkg'] == filtered_df['avg_wkg'].max()].iloc[0])
        else:
            if 'name' in filtered_df.columns:
                m3.metric("Current Leader", filtered_df['name'].iloc[0])
            if 'total_points' in filtered_df.columns:
                m4.metric("Top Points", f"{filtered_df['total_points'].max()} pts")
            elif 'final_points' in filtered_df.columns:
                m4.metric("Top Points", f"{filtered_df['final_points'].max()} pts")
            elif 'W/kg' in filtered_df.columns:
                m4.metric("Highest W/kg", str(
                          np.round(filtered_df['W/kg'].loc[filtered_df['W/kg'] == filtered_df['W/kg'].max()].iloc[0],3)) + " W/kg",
                          filtered_df['name'].loc[filtered_df['W/kg'] == filtered_df['W/kg'].max()].iloc[0])

    render_podium(filtered_df)

    # --- 6. STYLING & DISPLAY ---
    def highlight_podium(row):
        colors = {1: 'background-color: #D4AF37; color: black; font-weight: bold', 
                  2: 'background-color: #C0C0C0; color: black', 
                  3: 'background-color: #CD7F32; color: black'}
        return [colors.get(row.name, '')] * len(row)

    # Standardize column configs for the dataframe
    column_main_config = {
        "name": "Rider",
        "team_name": "Team",
        "total_points": st.column_config.NumberColumn("Points", format="%d ⭐"),
        "final_points": st.column_config.NumberColumn("Points", format="%d ⭐"),
        "total_time": "Time",
        "time_offset": "Gap",
    }

    if 'e_gap' in filtered_df.columns and pd.api.types.is_timedelta64_dtype(filtered_df['e_gap']):
        filtered_df['e_gap'] = filtered_df['e_gap'].apply(format_egap)

    filtered_df.index = range(1, len(filtered_df) + 1)

    st.dataframe(
        filtered_df.style.apply(highlight_podium, axis=1),
        use_container_width=True,
        hide_index=False,
        column_config=column_main_config
    )

    st.caption(f"Showing results for {selected_event} | {selected_sheet}")
