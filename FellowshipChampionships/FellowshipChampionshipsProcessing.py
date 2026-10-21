# cd /Users/gleesonm/projects/FellowshipRaceSeries/FellowshipChampionships
# source ../../zwift-env/bin/activate

# NOTE: race IDs, race types, and sprint/KQOM lists below are copied from La Roja - update for the Fellowship Championships

# import 
from zpdatafetch import Result, Sprints
import json
import pandas as pd
import numpy as np
import asyncio
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

# set up information
round = {'Round 1': [],
         'Round 2': [],
         'Round 3': [],
         'Round 4': [],
         'Round 5': []}

race_type = {'Round 1': "scratch",
         'Round 2': "scratch",
         'Round 3': "TT",
         'Round 4': "scratch",
         'Round 5': "scratch"}

pen_order = ['A', 'B', 'C', 'D', 'E']
pen_rank = {p: i for i, p in enumerate(pen_order)}

#### LIST OF SPRINT SEGMENTS ####
sprint_list = {
    "Champion's Sprint": (
    [20,18,16,14,12,10,9,8,7,6,5,4,3,2,1]
),
    "Fuego Flats Short": (
    [20,18,16,14,12,10,9,8,7,6,5,4,3,2,1]
),
    "Champs-Élysées Sprint": (
    [20,18,16,14,12,10,9,8,7,6,5,4,3,2,1]
)
}
#### LIST OF KQOM SEGMENTS ####
KQOM_list = {
    'Sgurr Summit South': (
    [20,18,16,14,12,10,9,8,7,6,5,4,3,2,1]
),
    'Sgurr Summit North': (
    [20,18,16,14,12,10,9,8,7,6,5,4,3,2,1]
),
    'Montmartre KOM': (
    [20,18,16,14,12,10,9,8,7,6,5,4,3,2,1]
)
    
}


# define how to determine rank of rider if present in multiple rounds
def choose_pen(df):
    eligible = df[df['count'] >= len(round) - 1]
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

    print(f"Fetching results of race {i}")
    race_data = await result.afetch(race_id)

    data_dict = json.loads(result.json())
    raw_data = data_dict[f"{i}"]['data']

    df = pd.DataFrame(raw_data)

    return df 

async def fetch_prime_data(race_id):
    prime = Sprints()
    print(f"Getting KQOM and Sprint data for race {race_id}")
    prime_data = await prime.afetch(race_id)

    data_dict = json.loads(prime.json())

    return data_dict[str(race_id)]['data']


if args.mode == "all":
    #### INDIVIDUAL GC ####
    out = {}
    e_gap_raw = {}

    gc_cols = ['pen', 'category', 'zwift_id', 'name', 'team_name', 'age']
    columns = ['pen', 'category', 'zwift_id', 'name', 'team_name', 'age', 'time']

    ## Scrape raw result data for the columns listed above.
    dfs = []
    for idx, key in enumerate(round):
        dfs = [] 
        race_id = round[key]
        res = pd.DataFrame()
        res_e_gap = pd.DataFrame()
        if len(race_id) > 0:
            for i in race_id:
                df = asyncio.run(fetch_race_data(i))
                
                if len(df)>0:
                    df = df[columns]
                    df['race_id'] = np.zeros(len(df)) + i

                    
                    dfs.append(df)

            if len(dfs)>0:
                res = pd.concat(dfs, ignore_index=True)
                res_e_gap = res.copy()

                # if duplicates only take lowest time
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

    out['GC'] = gc[['zwift_id', 'pen', 'category', 'age', 'name', 'team_name', 'total_time', 'time_offset', 'races']]

            #### eGAP ####
    e_gap = {}

    max_race_ids = out['GC'].loc[out['GC']["races"] == out['GC']["races"].max(), "zwift_id"]

    for key, df in e_gap_raw.items():
        if df.empty:
            continue
            
        df_filtered = df[df["zwift_id"].isin(max_race_ids)].copy()
        
        if key != "GC":
            # Determine the round number dynamically (e.g., "Round 1" -> "1" -> "time1")
            round_num = key.split()[-1]
            time_col = f"time{round_num}"
            
            rtype = race_type.get(key, "scratch")
            
            if rtype == "TT":
                # Group by 'pen' and subtract the min round time within that pen
                min_times = df_filtered.groupby('pen')[time_col].transform('min')
                df_filtered['e_gap'] = df_filtered[time_col] - min_times
                
            elif rtype == "scratch":
                # Group by both 'pen' and 'race_id' and subtract the winning race time
                min_times = df_filtered.groupby(['pen', 'race_id'])[time_col].transform('min')
                df_filtered['e_gap'] = df_filtered[time_col] - min_times

            df_filtered = df_filtered.loc[df_filtered.groupby('zwift_id')['e_gap'].idxmin()].reset_index(drop=True)

            e_gap[key] = df_filtered
        # else:
            
    egap_gc = out['GC'].copy()
    egap_gc_filtered = egap_gc[egap_gc["zwift_id"].isin(max_race_ids)].copy()
    e_gap['GC'] = egap_gc_filtered

    # for k, d in e_gap.items():
    #     if k == 'GC':
    #         continue
    #     print(k, len(d), d['e_gap'].describe(), d['zwift_id'].dtype)
    # print('GC zwift_id dtype:', e_gap['GC']['zwift_id'].dtype, len(e_gap['GC']))

    egap_totals = (
        pd.concat([
            df[['zwift_id', 'e_gap']] 
            for k, df in e_gap.items() 
            if k != 'GC' and 'e_gap' in df.columns
        ])
        .groupby('zwift_id', as_index=False)['e_gap']
        .sum()
    )

    # Merge the accumulated total into the GC DataFrame
    e_gap['GC'] = e_gap['GC'].merge(egap_totals, on='zwift_id', how='left')

    e_gap['GC'] = e_gap['GC'][['zwift_id', 'pen', 'category', 'age', 'name', 'team_name', 'e_gap', 'total_time']]

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
                    race_sprint[i] = asyncio.run(fetch_prime_data(i))

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

elif args.mode == "add":
    race_id = args.races

    ###### Individual GC ######

    gc_cols = ['pen', 'category', 'zwift_id', 'name', 'team_name', 'age']
    columns = ['pen', 'category', 'zwift_id', 'name', 'team_name', 'age', 'time']

    with open('gc_raw.pkl', 'rb') as f:
        out = pickle.load(f)

    with open('e_gap_raw.pkl', 'rb') as f:
        e_gap_raw = pickle.load(f)

    round_idx = 1
    for i in race_id:
        # identify round
        matched_round = next(
            (key for key, ids in round.items() if i in ids), None
        )

        # load new race
        df = asyncio.run(fetch_race_data(i))
        
        df = df[columns]
        df['race_id'] = np.zeros(len(df)) + i

        res = out[matched_round]
        res = res.rename(columns={'time'+matched_round[-1]: 'time'})
        res = pd.concat([res, df], ignore_index=True)

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

    with open('e_gap_raw.pkl', 'wb') as f:
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

    out['GC'] = gc[['zwift_id', 'pen', 'category', 'age', 'name', 'team_name', 'total_time', 'time_offset', 'races']]

        #### eGAP ####
    e_gap = {}

    max_race_ids = out['GC'].loc[out['GC']["races"] == out['GC']["races"].max(), "zwift_id"]

    for key, df in e_gap_raw.items():
        if df.empty:
            continue
            
        df_filtered = df[df["zwift_id"].isin(max_race_ids)].copy()
        
        if key != "GC":
            # Determine the round number dynamically (e.g., "Round 1" -> "1" -> "time1")
            round_num = key.split()[-1]
            time_col = f"time{round_num}"
            
            rtype = race_type.get(key, "scratch")
            
            if rtype == "TT":
                # Group by 'pen' and subtract the min round time within that pen
                min_times = df_filtered.groupby('pen')[time_col].transform('min')
                df_filtered['e_gap'] = df_filtered[time_col] - min_times
                
            elif rtype == "scratch":
                # Group by both 'pen' and 'race_id' and subtract the winning race time
                min_times = df_filtered.groupby(['pen', 'race_id'])[time_col].transform('min')
                df_filtered['e_gap'] = df_filtered[time_col] - min_times

            df_filtered = df_filtered.loc[df_filtered.groupby('zwift_id')['e_gap'].idxmin()].reset_index(drop=True)

            e_gap[key] = df_filtered

    e_gap['GC'] = out['GC']
    egap_totals = (
        pd.concat([
            df[['zwift_id', 'e_gap']] 
            for k, df in e_gap.items() 
            if k != 'GC' and 'e_gap' in df.columns
        ])
        .groupby('zwift_id', as_index=False)['e_gap']
        .sum()
    )

    # Merge the accumulated total into the GC DataFrame
    e_gap['GC'] = e_gap['GC'].merge(egap_totals, on='zwift_id', how='left')

    e_gap['GC'] = e_gap['GC'][['zwift_id', 'pen', 'category', 'age', 'name', 'team_name', 'e_gap', 'total_time']]


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
        race_sprint[i] = asyncio.run(fetch_prime_data(i))

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
