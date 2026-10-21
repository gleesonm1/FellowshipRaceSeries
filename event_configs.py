import os
import streamlit as st

# --- 1. EVENT CONFIGURATIONS ---
EVENT_CONFIG = {
    "Fellowship Championships": {
        "file": "FellowshipChampionships/FellowshipChampionships.xlsx",
        "default_sheet": "e_gap",
        "sorting": lambda sheet:
            (['races', 'total_time'], [True, True]) if sheet == "GC" else
            (['racers', 'total_time'], [False, True]) if sheet == "Team GC" else
            (['pen', f"time{sheet[-1]}"], [True, True]) if "Round" in sheet else
            (['pen', 'e_gap', 'total_time'], [True, True,True]) if sheet == "e_gap" else
            (['pen', 'Total Points'], [True, False])
    }
}

# --- 2. EVENT RULES & INFO RENDERER ---
def render_event_info(selected_event):
    """Renders images, rules, and announcements for the selected event."""
    if selected_event == "Fellowship Championships":
        st.markdown("## Fellowship Championships")

        # Display image if present
        hero_image = "FellowshipChampionships/ChampDetails.png"
        if os.path.exists(hero_image):
            st.image(hero_image, width=600)

        st.markdown("""
**Results will be updated at least twice a day, at approximately 8 am and 10 pm Pacific Time**

## Rules
Rules to be added.
        """)
