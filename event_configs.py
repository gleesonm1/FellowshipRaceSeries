import os
import streamlit as st

# --- 1. EVENT CONFIGURATIONS ---
EVENT_CONFIG = {
    "Fellowship Championships": {
        "file": "FellowshipChampionships/FellowshipChampionships.xlsx",
        "default_sheet": "e_gap",
        # "poster": "FellowshipChampionships/ChampDetails.jpg",
        "sorting": lambda sheet:
            (['races', 'total_time'], [True, True]) if sheet == "GC" else
            (['racers', 'total_time'], [False, True]) if sheet == "Team GC" else
            (['pen', f"time{sheet[-1]}"], [True, True]) if "Round" in sheet else
            (['e_gap', 'total_time'], [True,True]) if sheet == "e_gap" else
            (['pen', 'Total Points'], [True, False])
    }
}

# --- 2. EVENT RULES & INFO RENDERER ---
def render_event_info(selected_event):
    """Renders rules and announcements for the selected event (the poster is placed by app.py)."""
    if selected_event == "Fellowship Championships":
        st.markdown("## Fellowship Championships")

        st.markdown("**Results will be updated at least twice a day, at approximately 8 am and 10 pm Pacific Time**")

        # Collapsed by default; click the heading to show the rules
        with st.expander("**Rules - Please read carefully**", expanded=False):
            st.markdown("""
### GC and eGap
eGap is the primary ranking for this series. Your eGap in a race is your time gap to the fastest rider in your category, so the winner scores 0s. A traditional time-based GC is also published.

The series mixes a TT, a mass-start "Epic" race and three races with staggered starts for different categories, so please read the rules below carefully.

- **Everyone in your category counts.** eGap is calculated against every rider in your category in that event/race, whether or not they are riding the full series. Watch out for anyone sneaking up the road. The only exception is the stage 4 TT, where the eGap will be calculated against the times of all riders in your category regardless of which event they joined. 
- Any rider that: (i) wins a race; (ii) upgrades as a result of that ride (i.e., moves above the ZRS category limit); and (iii) does not race another stage of the championships will be removed from the eGap calculations. This is so that riders upgrading do not influence the final eGap standings (see information below on how riders upgrading throughout the series are handled).
- **Sandbagging.** If you believe a rider deliberately raced a category too low and won by a considerable margin, contact the race committee (Matt and Chase). We may manually remove their influence on the calculated eGap.

#### Category classifications
Each category has its own champion: the rider with the lowest total eGap in that category. For these classifications, every rider is placed in the highest category they completed a race in.

If you move up a category, your eGap for every race you have already completed is recalculated as 120 seconds per race. The exception is the Epic race and TT where a direct eGap to the category above is simple to calculate. Your results will also be removed from the lower category's results, so the eGaps of the riders you raced against are recalculated too.

For example, in race 1 Rider A wins Cat D (eGap 0s) and is promoted and Rider B is second (eGap 10s) but not promoted. Rider A then races race 2 in Cat C:

- Rider A's race 1 eGap becomes 120 seconds.
- Rider B is now the fastest Cat D rider in race 1, so their race 1 eGap becomes 0s.

### Team classification
The team classification uses total time, not eGap. In each round, a team's score is the sum of its three fastest times in each category (each rider can only be counted once). Across the five races that is 15 times counted, and the team with the lowest total wins.

To be competitive, your club needs at least three riders to finish every stage.

### KOM and Sprint classifications
KOM and Sprint champions are decided by fastest time through each segment (FTS). Every KOM and Sprint segment on every stage counts, except the stage 4 TT, with seperate Sprint and KOM champions announced at the end of the series.

Points are awarded for the fastest times through each segment across all races in a round. You are not just competing against the riders in your race, but against everyone who rode that round.

From 1st to 20th quickest times for each segments points will be awarded using the following scale:

[30, 25, 22, 20, 18, 16, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
            """)

        with st.expander("**Rider DQs and promotions**", expanded=False):
            st.markdown("""
Clau Pirata -- Deliberate sandbagging of ZRS prior to event.
                        """)
