# cd /Users/gleesonm/projects/FellowshipRaceSeries/FellowshipChampionships
# source ../../zwift-env/bin/activate

# NOTE: race IDs, race types, and sprint/KQOM lists below are copied from La Roja - update for the Fellowship Championships

# import 
from zpdatafetch import Result, Sprints, ZP
import json
import pandas as pd
import numpy as np
import asyncio
import time
import argparse
import os
import pickle

parser = argparse.ArgumentParser(description="Process Zwift Stage Race Data")
parser.add_argument(
    "--mode",
    choices=["all", "add"],
    default="all",
    help="'all' rebuilds everything from scratch; 'add' fetches only new/unprocessed races.",
)
parser.add_argument(
    "--races",
    nargs="+",
    type=int,
    help="Space-separated list of race IDs to fetch (e.g. --races 5604936 5604938)",
)

args = parser.parse_args()

# Log in to Zwiftpower once and share the session with every fetch;
# logging in separately for each race gets rejected (403) after a few races
zp_session = ZP()
zp_session.login()

# set up information
round = {'Round 1': [5752680,5752682,5752683,
                     5752684,5752685,5752686,
                     5752687,5752688],
         'Round 2': [5752710, 5752711,5752712,
                     5752713,5752714,5752715,
                     5752716,5752717],
         'Round 3': [5752719,5752724,5752727,
                     5752729,5752730,5752731,
                     5752734,5752735],
         'Round 4': [5752737,5752741,5752742,
                     5752743,5752744,5752745,
                     5752746,5752747],
         'Round 5': [5752748,5752750,5752751,
                     5752752,5752753,5752754,
                     5752755,5752756]}

race_type = {'Round 1': "scratch",
         'Round 2': "scratch",
         'Round 3': "Epic",
         'Round 4': "TT",
         'Round 5': "scratch"}

# round = {'Round 1': [5653189,5653191,5653192,5653193,5653194,5653195],
#          'Round 2': [5653196,5653197,5653198,5653199,5653200,5653201],
#          'Round 3': [5653202,5653203,5653204,5653205,5653206,5653207],
#          'Round 4': [5653208,5653209,5653210,5653211,5653212,5653213],
#          'Round 5': [5653214,5653215,5653216,5653217,5653218,5653219]}

# race_type = {'Round 1': "Epic",
#          'Round 2': "Epic",
#          'Round 3': "TT",
#          'Round 4': "Epic",
#          'Round 5': "Epic"}

pen_order = ['A', 'B', 'C', 'D', 'E']
pen_rank = {p: i for i, p in enumerate(pen_order)}

#### LIST OF SPRINT SEGMENTS ####
points = [30,25,22,20,18,16,14,13,12,11,
          10,9,8,7,6,5,4,3,2,1]
sprint_list = {
    "Champion's Sprint": (
    points
),
    "Fuego Flats Short": (
    points
),
    "Champs-Élysées Sprint": (
    points
)
}
#### LIST OF KQOM SEGMENTS ####
KQOM_list = {
    'Sgurr Summit South': (
    points
),
    'Sgurr Summit North': (
    points
),
    'Montmartre KOM': (
    points
)
    
}


# define how to determine rank of rider if present in multiple rounds
def choose_pen(df):
    eligible = df[df['count'] >= len(round)]
    if not eligible.empty:
        return (
            eligible
            .sort_values(
                by=['count', 'pen'],
                ascending=[False, True],
                key=lambda s: s.map(pen_rank) if s.name == 'pen' else s
            )
            .iloc[0]['pen']
        )

    return (
        df
        .sort_values(by='pen', key=lambda s: s.map(pen_rank))
        .iloc[0]['pen']
    )

def keep_highest_pen(df):
    """If a rider has results in several pens (e.g. within one round), keep only the rows in their highest pen."""
    rank = df['pen'].map(pen_rank).fillna(len(pen_order))
    return df[rank == rank.groupby(df['zwift_id']).transform('min')]

LOWER_PEN_EGAP = 120.0  # seconds, applied to rounds raced in a lower pen than the rider's series pen

def calc_egap(e_gap_raw, gc):
    """Builds the eGap GC table from the raw (all entries) round results.

    Each rider's series pen is the highest pen they entered in any round.
    i   - rides in a lower pen than the series pen are removed before eGaps are calculated, so they
          never set the winning time (this includes a lower pen ridden alongside a higher one in the same round)
    ii  - a round where the rider only has lower-pen rides scores LOWER_PEN_EGAP
    iii - a round with results that the rider missed scores the largest eGap in their pen for that round
    """
    rounds = {}
    for key, df in e_gap_raw.items():
        if not df.empty:
            df = df.copy()
            df['pen_rank'] = df['pen'].map(pen_rank).fillna(len(pen_order))
            rounds[key] = df

    if not rounds:
        return pd.DataFrame()

    # Series pen = highest pen entered in any round
    all_rows = pd.concat([d[['zwift_id', 'pen', 'pen_rank']] for d in rounds.values()])
    series_rank = all_rows.groupby('zwift_id')['pen_rank'].min()
    series_pen = all_rows.sort_values('pen_rank').groupby('zwift_id')['pen'].first()

    egap = pd.DataFrame({'pen': series_pen})
    egap['races completed'] = 0
    egap_cols = []
    for key, df in rounds.items():
        time_col = f"time{key.split()[-1]}"
        col = f"e_gap{key.split()[-1]}"
        egap_cols.append(col)

        # (i) only rides in the rider's series pen count towards the eGap calculation
        counted = df[df['pen_rank'] == df['zwift_id'].map(series_rank)].copy()

        # TT: eGap to the fastest in the pen across all events; scratch: to the winner of that event
        groups = ['pen'] if race_type.get(key, "scratch") == "TT" else ['pen', 'race_id']
        counted['e_gap'] = counted[time_col] - counted.groupby(groups)[time_col].transform('min')
        ref = counted.groupby(groups)[time_col].min().rename('ref_time').reset_index()
        counted = counted.loc[counted.groupby('zwift_id')['e_gap'].idxmin()].set_index('zwift_id')

        egap[col] = counted['e_gap']

        # (ii) - a round where the rider only has lower-pen rides scores LOWER_PEN_EGAP for scratch races; for TT / Epic it scores the gap to the fastest time in their series pen / TT: across all races in the round, Epic: in the same race_id)
        lower = df[~df['zwift_id'].isin(counted.index)].copy()
        if not lower.empty:
            if race_type.get(key, "scratch") in ("TT", "Epic"):
                # gap to the fastest time in the rider's series pen
                # TT: across all races in the round; Epic: in the same race_id they rode
                lower['pen'] = lower['zwift_id'].map(series_pen)
                lower = lower.merge(ref, on=groups, how='left')
                lower['e_gap'] = (lower[time_col] - lower['ref_time']).clip(lower=0)
                promoted_egap = lower.groupby('zwift_id')['e_gap'].min().fillna(LOWER_PEN_EGAP)
            else:
                promoted_egap = pd.Series(LOWER_PEN_EGAP, index=lower['zwift_id'].unique())
            egap.loc[promoted_egap.index, col] = promoted_egap

        # rode this round (in any pen) - counted before missed rounds are filled in
        egap['races completed'] += egap[col].notna().astype(int)

        # (iii) missed rounds take the largest eGap in the rider's pen, or the LOWER_PEN_EGAP values, whichever is higher.
        fill = egap.groupby('pen')[col].transform('max').clip(lower=LOWER_PEN_EGAP).fillna(LOWER_PEN_EGAP)
        egap[col] = egap[col].fillna(fill)

    egap['e_gap'] = egap[egap_cols].sum(axis=1)
    egap = egap.reset_index(names='zwift_id')

    info_cols = [c for c in ['zwift_id', 'category', 'age', 'name', 'team_name', 'gender', 'total_time'] if c in gc.columns]
    egap = gc[info_cols].merge(egap, on='zwift_id', how='left')

    egap = egap.sort_values(by=['pen', 'e_gap'], key=lambda s: s.map(pen_rank) if s.name == 'pen' else s,
                            ignore_index=True)

    first_cols = ['zwift_id', 'pen', 'category', 'age', 'name', 'team_name', 'gender', 'e_gap', 'total_time', 'races completed']
    first_cols = [c for c in first_cols if c in egap.columns]
    return egap[first_cols + egap_cols]

def assign_points(df, segment, points_scale):
    points_col = segment + " points"

    df[points_col] = 0  # default

    for pen, g in df.groupby('pen'):
        valid = g[g[segment].notna()].copy()

        if valid.empty:
            continue

        valid = valid.sort_values(segment)
        valid['rank'] = range(1, len(valid) + 1)

        valid[points_col] = valid['rank'].apply(
            lambda r: points_scale[r - 1] if r <= len(points_scale) else 0
        )

        df.loc[valid.index, points_col] = valid[points_col]

    return df

# Function to convert seconds to hh:mm:ss
def format_seconds(total_seconds):
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    dec = int(np.round(1000*(total_seconds % 1)))
    if np.nanmax(hours) > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{dec:03d}"
    elif np.nanmax(minutes) > 0:
        return f"{minutes:02d}:{seconds:02d}.{dec:03d}"
    else:
        return f"{seconds:02d}.{dec:03d}"

async def fetch_race_data(race_id):
    result = Result()
    result.set_zp_session(zp_session)

    print(f"Fetching results of race {race_id}")
    race_data = await result.afetch(race_id)

    data_dict = json.loads(result.json())
    raw_data = data_dict[f"{race_id}"]['data']

    df = pd.DataFrame(raw_data)

    return df 

async def fetch_prime_data(race_id):
    prime = Sprints()
    prime.set_zp_session(zp_session)
    print(f"Getting KQOM and Sprint data for race {race_id}")
    prime_data = await prime.afetch(race_id)

    data_dict = json.loads(prime.json())

    return data_dict[str(race_id)]['data']

# Zwiftpower rate limits requests (429). Each Sprints fetch also fires ~10 primes requests at once,
# so pause between races and back off when rate limited.
REQUEST_DELAY = 3                     # seconds before every fetch
RATE_LIMIT_WAITS = [30, 60, 120, 240] # seconds to wait before each retry after a 429

def is_rate_limited(e):
    """True if a 429 appears anywhere in the exception, its causes or (for task groups) its sub-exceptions."""
    if e is None:
        return False
    if '429' in str(e):
        return True
    if any(is_rate_limited(sub) for sub in getattr(e, 'exceptions', [])):
        return True
    return is_rate_limited(e.__cause__)

def run_fetch(fetch, race_id):
    """Runs fetch_race_data / fetch_prime_data for one race with a delay and 429 retries."""
    for wait in RATE_LIMIT_WAITS + [None]:
        time.sleep(REQUEST_DELAY)
        try:
            return asyncio.run(fetch(race_id))
        except Exception as e:
            if wait is None or not is_rate_limited(e):
                raise
            print(f"Rate limited by Zwiftpower on race {race_id}, waiting {wait}s before retrying")
            time.sleep(wait)


if args.mode == "all":
    #### INDIVIDUAL GC ####
    out = {}
    e_gap_raw = {}

    gc_cols = ['pen', 'category', 'zwift_id', 'name', 'team_name', 'age', 'gender']
    columns = ['pen', 'category', 'zwift_id', 'name', 'team_name', 'age', 'gender', 'time']

    ## Scrape raw result data for the columns listed above.
    dfs = []
    for idx, key in enumerate(round):
        dfs = [] 
        race_id = round[key]
        res = pd.DataFrame()
        res_e_gap = pd.DataFrame()
        if len(race_id) > 0:
            for i in race_id:
                df = run_fetch(fetch_race_data, i)
                
                if len(df)>0:
                    df = df[columns]
                    df['race_id'] = np.zeros(len(df)) + i

                    
                    dfs.append(df)

            if len(dfs)>0:
                res = pd.concat(dfs, ignore_index=True)
                res_e_gap = res.copy()

                # if duplicates only keep the highest pen entered this round, then the lowest time
                res = keep_highest_pen(res)
                res = res.loc[res.groupby('zwift_id')['time'].idxmin()].reset_index(drop=True)

                res.sort_values(by = ['pen', 'time'], ignore_index=True, inplace = True)
                res_e_gap.sort_values(by = ['pen','time'], ignore_index=True, inplace=True)

                res = res.rename(columns={'time': 'time'+str(idx+1)})
                res_e_gap = res_e_gap.rename(columns = {'time':'time'+str(idx+1)})
                
                gc_cols.append('time'+str(idx+1))

        out[key] = res
        e_gap_raw[key] = res_e_gap

    with open('gc_raw.pkl', 'wb') as f:
        pickle.dump(out, f)

    with open('egap_raw.pkl', 'wb') as f:
        pickle.dump(e_gap_raw, f)

    all_rounds = [
        df[df.columns.intersection(gc_cols)] # Only take columns that exist in THIS df
        for key, df in out.items()
        if key != 'GC' and not df.empty
    ]

    all_gc_rows = pd.concat(all_rounds, ignore_index=True)
    time_cols = [c for c in all_gc_rows.columns if c.startswith('time')]
    assert all_gc_rows.groupby('zwift_id')[time_cols].count().max().max() <= 1

    pen_counts = (
        all_gc_rows
        .groupby(['zwift_id', 'pen'])
        .size()
        .reset_index(name='count')
    )

    gc_pen = (
        pen_counts
        .groupby('zwift_id')
        .apply(choose_pen, include_groups = False)
        .reset_index(name='pen')
    )

    gc_base = (
        all_gc_rows
        .groupby('zwift_id', as_index=False)
        .agg({
            'category': 'first',
            'name': 'first',
            'team_name': 'first',
            'age': 'first',
            'gender': 'first',
            **{c: 'min' for c in time_cols}   # keep round times
        })
    )

    gc = (
        gc_base
        .merge(gc_pen, on='zwift_id', how='left')
        .sort_values(by='pen', key=lambda s: s.map(pen_rank), ignore_index=True)
    )

    gc['races'] = gc[time_cols].count(axis=1)

    # calculate offsets
    gc['total_time'] = gc[time_cols].sum(axis=1)

    gc['time_offset'] = np.zeros(len(gc))
    gc.loc[gc['races'] == gc['races'].max(),'time_offset'] = gc['total_time'] - gc.loc[gc['races'] == gc['races'].max()].groupby('pen')['total_time'].transform('min')
    gc.loc[gc['races'] < gc['races'].max(), 'time_offset'] = np.nan

    gc.sort_values(by = ['pen', 'races', 'total_time'], ascending = [True, False, True], 
                ignore_index=True, inplace = True)
    
    # gc = add_velo(gc)

    out['GC'] = gc[['zwift_id', 'pen', 'category', 'age', 'name', 'gender', 'team_name', 'total_time', 'time_offset', 'races']]

    #### eGAP ####
    e_gap = {'GC': calc_egap(e_gap_raw, out['GC'])}

    #### TEAM GC ######
    teams = gc['team_name'].unique()

    team_gc = {}
    team_gc_cols = ['pen','team_name']

    for idx, key in enumerate(round):
        rows = []
        if key != "GC" and not out[key].empty:
            df = out[key]
            time_col = f"time{idx+1}"

            for (pen, team), g in df.groupby(['pen', 'team_name']):
                if len(g) >= 3:
                    if len(team)>0:
                        team_time = g[time_col].nsmallest(3).sum()
                        rows.append({
                            'round': key,
                            'pen': pen,
                            'team_name': team,
                            f'time{idx+1}': team_time,
                            f'racers{idx+1}': 3,
                        })
                else:
                    if len(team)>0:
                        team_time = g[time_col].sum()
                        rows.append({
                            'round': key,
                            'pen': pen,
                            'team_name': team,
                            f'time{idx+1}': team_time,
                            f'racers{idx+1}': len(g),
                        })

            team_gc_cols.append(f"time{idx+1}")
            team_gc_cols.append(f"racers{idx+1}")

        team_gc[key] = pd.DataFrame(rows)

    all_rounds = [
        df[df.columns.intersection(team_gc_cols)] # Only take columns that exist in THIS df
        for key, df in team_gc.items()
        if key != 'GC' and not df.empty
    ]

    if len(all_rounds) > 0:
        all_team_rows = pd.concat(all_rounds, ignore_index=True)
        time_cols = [c for c in all_team_rows.columns if c.startswith('time')]
        racer_cols = [c for c in all_team_rows.columns if c.startswith('racers')]
        # assert all_team_rows.groupby('team_name')[time_cols].count().max().max() <= 1

        pen_counts = (
            all_team_rows
            .groupby(['pen', 'team_name'])
            .size()
            .reset_index(name='count')
        )

        gc_team = (
            all_team_rows
            .groupby(['team_name', 'pen'], as_index=False)
            .agg({
                **{c: 'min' for c in time_cols},     # Keep round times (minimum time)
                **{c: 'first' for c in racer_cols}  # Copy across racer data
            })
        )

        gc_team['racers'] = gc_team[racer_cols].sum(axis=1)
        gc_team['total_time'] = gc_team[time_cols].sum(axis=1)

        gc_team['time_offset'] = np.zeros(len(gc_team))
        gc_team.loc[gc_team['racers'] == gc_team['racers'].max(),'time_offset'] = gc_team['total_time'] - gc_team.loc[gc_team['racers'] == gc_team['racers'].max()].groupby('pen')['total_time'].transform('min')
        gc_team.loc[gc_team['racers'] < gc_team['racers'].max(), 'time_offset'] = np.nan

        gc_team.sort_values(by=['pen', 'racers', 'total_time'], ascending=[True, False, True], 
                    ignore_index=True, inplace=True)

        # 1. Interleave time_cols and racer_cols (e.g., time1, racers1, time2, racers2)
        alternating_cols = [col for pair in zip(time_cols, racer_cols) for col in pair]
        
        # 2. Define your base columns
        base_cols = ['pen', 'team_name', 'total_time', 'time_offset', 'racers']
        
        # 3. Combine them to slice the DataFrame
        team_gc['GC'] = gc_team[base_cols + alternating_cols]
    else:
        team_gc['GC'] = pd.DataFrame()

    # #### ISOLATE THE SPRINT AND KOMS FOUND IN THE RACES ####
    sprint = gc[["zwift_id", "pen", "category", "name", "team_name", "races"]].copy()
    KQOM = gc[["zwift_id", "pen", "category", "name", "team_name", "races"]].copy()

    names = []
    race_sprint = {} 
    for idx, key in enumerate(round):
        if race_type[key] != "TT":
            race_id = round[key]
            if len(race_id) > 0:
                for i in race_id: 
                    race_sprint[i] = run_fetch(fetch_prime_data, i)

                    if len(race_sprint[i])>0.0:
                        for k in range(len(race_sprint[i][0]['sprints'])):
                            name = race_sprint[i][0]['sprints'][k]['name']
                            if name not in names:
                                names.append(name)

    with open('prime_raw.pkl', 'wb') as f:
        pickle.dump([names, race_sprint], f)

    sprints = [x for x in names if x in sprint_list or 'Sprint' in x]
    kqoms = [x for x in names if x in KQOM_list or 'KOM' in x]
    for x in names:
        if "Sprint" in x:
            sprint_list.update({x: points})
        if "KOM" in x:
            KQOM_list.update({x: points})
    sprint[sprints] = 0.0
    KQOM[kqoms] = 0.0

    # sprint = sprint.loc[sprint['races'] == np.nanmax(sprint['races'])].reset_index(drop = True)
    # KQOM = KQOM.loc[(KQOM['races'] == np.nanmax(KQOM['races']))].reset_index(drop = True)

    for race_key, race in race_sprint.items():
        for i in range(len(race)):
            rider = race[i]['zwift_id']
            for k in race[i]['sprints']:
                if k['name'] in sprint.columns:
                    if len(sprint.loc[sprint['zwift_id'] == rider, k['name']]) > 0.0:
                        if sprint.loc[sprint['zwift_id'] == rider, k['name']].values[0] == 0.0:
                            sprint.loc[sprint['zwift_id'] == rider, k['name']] = k['msec']
                        else:
                            sprint.loc[sprint['zwift_id'] == rider, k['name']] = np.nanmin([sprint.loc[sprint['zwift_id'] == rider, k['name']].values[0],k['msec']])      
                if k['name'] in KQOM.columns:
                    if len(KQOM.loc[KQOM['zwift_id'] == rider, k['name']]) > 0.0:
                        if KQOM.loc[KQOM['zwift_id'] == rider, k['name']].values[0] == 0.0:
                            KQOM.loc[KQOM['zwift_id'] == rider, k['name']] = k['msec']
                        else:
                            KQOM.loc[KQOM['zwift_id'] == rider, k['name']] = np.nanmin([KQOM.loc[KQOM['zwift_id'] == rider, k['name']].values[0],k['msec']])

    sprint = sprint.replace(0.0, np.nan)
    KQOM = KQOM.replace(0.0, np.nan)

    #### Create final sprint and KQOM tables for export ####
    for s in sprint_list.keys():
        if s in sprint:
            sprint = assign_points(sprint, s, sprint_list[s])

    if "Total Points" in sprint.columns:
        sprint = sprint.drop(columns="Total Points")

    sprint['Total Points'] = sprint.loc[:,sprint.columns.str.contains("points")].sum(axis = 1)
    sprint = sprint[list(sprint.columns[:5]) + ["Total Points"] + list(sprint.columns[5:-1])]
    sprint = sprint.sort_values(['pen', 'Total Points'], ascending = [True,False])

    for k in KQOM_list.keys():
        if k in KQOM:
            KQOM = assign_points(KQOM, k, KQOM_list[k])

    if "Total Points" in KQOM.columns:
        KQOM = KQOM.drop(columns="Total Points")

    KQOM['Total Points'] = KQOM.loc[:,KQOM.columns.str.contains("points")].sum(axis = 1)
    KQOM = KQOM[list(KQOM.columns[:5]) + ["Total Points"] + list(KQOM.columns[5:-1])]
    KQOM = KQOM.sort_values(['pen', 'Total Points'], ascending = [True,False])

elif args.mode == "add":
    race_id = args.races

    ###### Individual GC ######

    gc_cols = ['pen', 'category', 'zwift_id', 'name', 'team_name', 'age', 'gender']
    columns = ['pen', 'category', 'zwift_id', 'name', 'team_name', 'age', 'gender', 'time']

    with open('gc_raw.pkl', 'rb') as f:
        out = pickle.load(f)

    with open('egap_raw.pkl', 'rb') as f:
        e_gap_raw = pickle.load(f)

    round_idx = 1
    for i in race_id:
        # identify round
        matched_round = next(
            (key for key, ids in round.items() if i in ids), None
        )

        # load new race
        df = run_fetch(fetch_race_data, i)
        
        df = df[columns]
        df['race_id'] = np.zeros(len(df)) + i

        res = out[matched_round]
        res = res.rename(columns={'time'+matched_round[-1]: 'time'})
        res = pd.concat([res, df], ignore_index=True)

        res = keep_highest_pen(res)
        res = res.loc[res.groupby('zwift_id')['time'].idxmin()].reset_index(drop=True)

        res = res.rename(columns={'time': 'time'+matched_round[-1]})

        res_egap = e_gap_raw[matched_round]
        res_egap = res_egap.rename(columns={'time'+matched_round[-1]: 'time'})
        res_egap = pd.concat([res_egap, df], ignore_index=True)

        res_egap = res_egap.rename(columns={'time': 'time'+matched_round[-1]})

        e_gap_raw[matched_round] = res_egap

        # round = int(matched_round[-1])
    while round_idx <= int(5):
        gc_cols.append('time'+str(round_idx))
        round_idx = round_idx + 1

    with open('gc_raw.pkl', 'wb') as f:
        pickle.dump(out, f)

    with open('egap_raw.pkl', 'wb') as f:
        pickle.dump(e_gap_raw, f)

    gc_cols = list(dict.fromkeys(gc_cols))

    all_rounds = [
        df[df.columns.intersection(gc_cols)] # Only take columns that exist in THIS df
        for key, df in out.items()
        if key != 'GC' and not df.empty
    ]

    all_gc_rows = pd.concat(all_rounds, ignore_index=True)
    time_cols = [c for c in all_gc_rows.columns if c.startswith('time')]
    assert all_gc_rows.groupby('zwift_id')[time_cols].count().max().max() <= 1

    pen_counts = (
        all_gc_rows
        .groupby(['zwift_id', 'pen'])
        .size()
        .reset_index(name='count')
    )

    gc_pen = (
        pen_counts
        .groupby('zwift_id')
        .apply(choose_pen, include_groups = False)
        .reset_index(name='pen')
    )

    gc_base = (
        all_gc_rows
        .groupby('zwift_id', as_index=False)
        .agg({
            'category': 'first',
            'name': 'first',
            'team_name': 'first',
            'age': 'first',
            'gender': 'first',
            **{c: 'min' for c in time_cols}   # keep round times
        })
    )

    gc = (
        gc_base
        .merge(gc_pen, on='zwift_id', how='left')
        .sort_values(by='pen', key=lambda s: s.map(pen_rank), ignore_index=True)
    )

    gc['races'] = gc[time_cols].count(axis=1)

    # calculate offsets
    gc['total_time'] = gc[time_cols].sum(axis=1)

    gc['time_offset'] = np.zeros(len(gc))
    gc.loc[gc['races'] == gc['races'].max(),'time_offset'] = gc['total_time'] - gc.loc[gc['races'] == gc['races'].max()].groupby('pen')['total_time'].transform('min')
    gc.loc[gc['races'] < gc['races'].max(), 'time_offset'] = np.nan

    gc.sort_values(by = ['pen', 'races', 'total_time'], ascending = [True, False, True], 
                ignore_index=True, inplace = True)

    # gc = add_velo(gc)

    out['GC'] = gc[['zwift_id', 'pen', 'category', 'age', 'name', 'gender', 'team_name', 'total_time', 'time_offset', 'races']]

    #### eGAP ####
    e_gap = {'GC': calc_egap(e_gap_raw, out['GC'])}


    #### TEAM GC ######
    teams = gc['team_name'].unique()

    team_gc = {}
    team_gc_cols = ['pen','team_name']

    for idx, key in enumerate(round):
        rows = []
        if key != "GC" and not out[key].empty:
            df = out[key]
            time_col = f"time{idx+1}"

            for (pen, team), g in df.groupby(['pen', 'team_name']):
                if len(g) >= 3:
                    if len(team)>0:
                        team_time = g[time_col].nsmallest(3).sum()
                        rows.append({
                            'round': key,
                            'pen': pen,
                            'team_name': team,
                            f'time{idx+1}': team_time,
                            f'racers{idx+1}': 3,
                        })
                else:
                    if len(team)>0:
                        team_time = g[time_col].sum()
                        rows.append({
                            'round': key,
                            'pen': pen,
                            'team_name': team,
                            f'time{idx+1}': team_time,
                            f'racers{idx+1}': len(g),
                        })

            team_gc_cols.append(f"time{idx+1}")
            team_gc_cols.append(f"racers{idx+1}")

        team_gc[key] = pd.DataFrame(rows)

    all_rounds = [
        df[df.columns.intersection(team_gc_cols)] # Only take columns that exist in THIS df
        for key, df in team_gc.items()
        if key != 'GC' and not df.empty
    ]

    if len(all_rounds) > 0:
        all_team_rows = pd.concat(all_rounds, ignore_index=True)
        time_cols = [c for c in all_team_rows.columns if c.startswith('time')]
        racer_cols = [c for c in all_team_rows.columns if c.startswith('racers')]
        # assert all_team_rows.groupby('team_name')[time_cols].count().max().max() <= 1

        pen_counts = (
            all_team_rows
            .groupby(['pen', 'team_name'])
            .size()
            .reset_index(name='count')
        )

        gc_team = (
            all_team_rows
            .groupby(['team_name', 'pen'], as_index=False)
            .agg({
                **{c: 'min' for c in time_cols},     # Keep round times (minimum time)
                **{c: 'first' for c in racer_cols}  # Copy across racer data
            })
        )

        gc_team['racers'] = gc_team[racer_cols].sum(axis=1)
        gc_team['total_time'] = gc_team[time_cols].sum(axis=1)

        gc_team['time_offset'] = np.zeros(len(gc_team))
        gc_team.loc[gc_team['racers'] == gc_team['racers'].max(),'time_offset'] = gc_team['total_time'] - gc_team.loc[gc_team['racers'] == gc_team['racers'].max()].groupby('pen')['total_time'].transform('min')
        gc_team.loc[gc_team['racers'] < gc_team['racers'].max(), 'time_offset'] = np.nan

        gc_team.sort_values(by=['pen', 'racers', 'total_time'], ascending=[True, False, True], 
                    ignore_index=True, inplace=True)

        # 1. Interleave time_cols and racer_cols (e.g., time1, racers1, time2, racers2)
        alternating_cols = [col for pair in zip(time_cols, racer_cols) for col in pair]
        
        # 2. Define your base columns
        base_cols = ['pen', 'team_name', 'total_time', 'time_offset', 'racers']
        
        # 3. Combine them to slice the DataFrame
        team_gc['GC'] = gc_team[base_cols + alternating_cols]
    else:
        team_gc['GC'] = pd.DataFrame()

    # #### ISOLATE THE SPRINT AND KOMS FOUND IN THE RACES ####
    sprint = gc[["zwift_id", "pen", "category", "name", "team_name", "races"]].copy()
    KQOM = gc[["zwift_id", "pen", "category", "name", "team_name", "races"]].copy()

    with open('prime_raw.pkl', 'rb') as f:
        names, race_sprint = pickle.load(f)

    
    for i in args.races:
        # match "all" mode: no sprint/KQOM scoring in TT rounds
        matched_round = next((key for key, ids in round.items() if i in ids), None)
        if race_type.get(matched_round) == "TT":
            continue

        race_sprint[i] = run_fetch(fetch_prime_data, i)

        if len(race_sprint[i])>0.0:
            for k in range(len(race_sprint[i][0]['sprints'])):
                name = race_sprint[i][0]['sprints'][k]['name']
                if name not in names:
                    names.append(name)

    with open('prime_raw.pkl', 'wb') as f:
         pickle.dump([names, race_sprint], f)

    sprints = [x for x in names if x in sprint_list or 'Sprint' in x]
    kqoms = [x for x in names if x in KQOM_list or 'KOM' in x]
    for x in names:
        if "Sprint" in x:
            sprint_list.update({x: [20,18,16,14,12,10,9,8,7,6,5,4,3,2,1]})
        if "KOM" in x:
            KQOM_list.update({x: [20,18,16,14,12,10,9,8,7,6,5,4,3,2,1]})
    sprint[sprints] = 0.0
    KQOM[kqoms] = 0.0

    sprint = sprint.loc[sprint['races'] == np.nanmax(sprint['races'])].reset_index(drop = True)
    KQOM = KQOM.loc[(KQOM['races'] == np.nanmax(KQOM['races']))].reset_index(drop = True)

    for race_key, race in race_sprint.items():
        for i in range(len(race)):
            rider = race[i]['zwift_id']
            for k in race[i]['sprints']:
                if k['name'] in sprint.columns:
                    if len(sprint.loc[sprint['zwift_id'] == rider, k['name']]) > 0.0:
                        if sprint.loc[sprint['zwift_id'] == rider, k['name']].values[0] == 0.0:
                            sprint.loc[sprint['zwift_id'] == rider, k['name']] = k['msec']
                        else:
                            sprint.loc[sprint['zwift_id'] == rider, k['name']] = np.nanmin([sprint.loc[sprint['zwift_id'] == rider, k['name']].values[0],k['msec']])      
                if k['name'] in KQOM.columns:
                    if len(KQOM.loc[KQOM['zwift_id'] == rider, k['name']]) > 0.0:
                        if KQOM.loc[KQOM['zwift_id'] == rider, k['name']].values[0] == 0.0:
                            KQOM.loc[KQOM['zwift_id'] == rider, k['name']] = k['msec']
                        else:
                            KQOM.loc[KQOM['zwift_id'] == rider, k['name']] = np.nanmin([KQOM.loc[KQOM['zwift_id'] == rider, k['name']].values[0],k['msec']])

    sprint = sprint.replace(0.0, np.nan)
    KQOM = KQOM.replace(0.0, np.nan)

    #### Create final sprint and KQOM tables for export ####
    for s in sprint_list.keys():
        if s in sprint:
            sprint = assign_points(sprint, s, sprint_list[s])

    if "Total Points" in sprint.columns:
        sprint = sprint.drop(columns="Total Points")

    sprint['Total Points'] = sprint.loc[:,sprint.columns.str.contains("points")].sum(axis = 1)
    sprint = sprint[list(sprint.columns[:5]) + ["Total Points"] + list(sprint.columns[5:-1])]
    sprint = sprint.sort_values(['pen', 'Total Points'], ascending = [True,False])

    for k in KQOM_list.keys():
        if k in KQOM:
            KQOM = assign_points(KQOM, k, KQOM_list[k])

    if "Total Points" in KQOM.columns:
        KQOM = KQOM.drop(columns="Total Points")

    KQOM['Total Points'] = KQOM.loc[:,KQOM.columns.str.contains("points")].sum(axis = 1)
    KQOM = KQOM[list(KQOM.columns[:5]) + ["Total Points"] + list(KQOM.columns[5:-1])]
    KQOM = KQOM.sort_values(['pen', 'Total Points'], ascending = [True,False])

final = {}
final['GC'] = out['GC']
final['e_gap'] = e_gap['GC']
final['Team GC'] = team_gc['GC']
final['Sprints'] = sprint
final['KQOM'] = KQOM 
for r in out:
    final[r] = out[r]

for f in final:
    final[f] = final[f].fillna(0.0)
    for k in final[f].columns:
        if 'time' in k:
            final[f][k] = final[f][k].apply(format_seconds)
        elif 'e_gap' in k:
            final[f][k] = final[f][k].apply(format_seconds)
    
    if "races" in final[f]:
        final[f].loc[final[f]['races'] < np.nanmax(final[f]['races']), 'time_offset'] = np.nan


with pd.ExcelWriter("FellowshipChampionships.xlsx") as writer:
    for sheet, df in final.items():
        df.to_excel(writer, sheet_name=sheet, index=False)
