import pandas as pd
import requests

def get_ipl_players():
    url = "https://stats.espncricinfo.com/ci/engine/stats/index.html?class=3;template=results;type=allround"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    tables = pd.read_html(response.text)

    # Find the table that has a "Player" column
    df = None
    for table in tables:
        # Convert all column names to strings first
        cols = [str(c).strip().lower() for c in table.columns]
        if "player" in cols:
            df = table.copy()
            break

    if df is None:
        raise ValueError("Could not find the Player table on ESPN Cricinfo")

    # Ensure all column names are strings
    df.columns = [str(c).strip() for c in df.columns]

    # Dynamically identify the player column
    player_col = [c for c in df.columns if "player" in c.lower()][0]

    # Remove duplicate header rows
    df = df[df[player_col] != player_col]

    players = []
    for _, row in df.head(100).iterrows():
        player_name = str(row[player_col])

        # Extract country from brackets if present
        if "(" in player_name:
            name = player_name.split("(")[0].strip()
            country = player_name.split("(")[1].replace(")", "").strip()
        else:
            name = player_name.strip()
            country = "Unknown"

        # Helper functions to parse stats safely
        def parse_int(x):
            try:
                return int(x)
            except:
                return 0

        def parse_float(x):
            try:
                return float(x)
            except:
                return 0.0

        # Dynamically find numeric columns
        runs_col = [c for c in df.columns if "runs" in c.lower()][0]
        bat_avg_col = [c for c in df.columns if "bat av" in c.lower() or "bat avg" in c.lower()][0]
        wkts_col = [c for c in df.columns if "wkt" in c.lower() or "wkts" in c.lower()][0]
        bowl_avg_col = [c for c in df.columns if "bowl av" in c.lower() or "bowl avg" in c.lower()][0]

        player = {
            "name": name,
            "country": country,
            "runs": parse_int(row[runs_col]),
            "bat_avg": parse_float(row[bat_avg_col]),
            "wickets": parse_int(row[wkts_col]),
            "bowl_avg": parse_float(row[bowl_avg_col]),
            "team": "Unsold"
        }

        players.append(player)

    return players