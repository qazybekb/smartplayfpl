"""
Step 1: Data Collection for FPL ML Model
=========================================

This script collects historical gameweek data from the FPL API
and saves it to a CSV file for analysis and model training.

Usage:
    cd backend
    python ml/01_data_collection.py

Output:
    ml/data/fpl_gameweek_data.csv
"""

import asyncio
import httpx
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import time

# Configuration
API_BASE = "https://fantasy.premierleague.com/api"
MIN_MINUTES = 0  # Include ALL players (no minimum)
MAX_PLAYERS = None  # No limit - collect all players
OUTPUT_DIR = Path(__file__).parent / "data"


async def fetch_bootstrap():
    """Fetch main FPL data (players, teams, events)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{API_BASE}/bootstrap-static/",
            headers={"User-Agent": "GraphFPL-ML-Research"}
        )
        response.raise_for_status()
        return response.json()


async def fetch_player_history(client: httpx.AsyncClient, player_id: int) -> dict:
    """Fetch a single player's gameweek history."""
    try:
        response = await client.get(
            f"{API_BASE}/element-summary/{player_id}/",
            headers={"User-Agent": "GraphFPL-ML-Research"}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"  ⚠️ Error fetching player {player_id}: {e}")
        return None


async def collect_all_data():
    """Main data collection function."""
    print("=" * 60)
    print("FPL ML DATA COLLECTION")
    print("=" * 60)
    print()
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Fetch bootstrap data
    print("📥 Fetching bootstrap data...")
    bootstrap = await fetch_bootstrap()
    
    players = bootstrap["elements"]
    teams = {t["id"]: t for t in bootstrap["teams"]}
    events = bootstrap["events"]
    
    current_gw = next((e for e in events if e["is_current"]), events[-1])
    
    print(f"   Total players: {len(players)}")
    print(f"   Current gameweek: {current_gw['id']}")
    print()
    
    # Step 2: Filter players (or include all)
    if MIN_MINUTES > 0:
        active_players = [p for p in players if p.get("minutes", 0) >= MIN_MINUTES]
    else:
        # Include ALL players, even those with 0 minutes
        active_players = players
    
    active_players = sorted(active_players, key=lambda x: x.get("total_points", 0), reverse=True)
    
    if MAX_PLAYERS:
        active_players = active_players[:MAX_PLAYERS]
    
    print(f"📊 Collecting {len(active_players)} players (min {MIN_MINUTES} minutes)")
    print()
    
    # Step 3: Collect gameweek history for each player
    print("📥 Collecting gameweek histories...")
    print("   (This may take a few minutes)")
    print()
    
    all_records = []
    position_map = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        for i, player in enumerate(active_players):
            # Progress indicator
            if (i + 1) % 20 == 0 or i == 0:
                print(f"   Processing player {i + 1}/{len(active_players)}...")
            
            # Fetch history
            data = await fetch_player_history(client, player["id"])
            if not data:
                continue
            
            history = data.get("history", [])
            
            # Add player metadata to each GW record
            for gw in history:
                record = {
                    # Player info
                    "player_id": player["id"],
                    "player_name": player["web_name"],
                    "full_name": f"{player['first_name']} {player['second_name']}",
                    "position": position_map.get(player["element_type"], "UNK"),
                    "team_id": player["team"],
                    "team_name": teams[player["team"]]["short_name"],
                    
                    # Gameweek info
                    "gameweek": gw["round"],
                    "opponent_team_id": gw["opponent_team"],
                    "opponent_name": teams[gw["opponent_team"]]["short_name"],
                    "was_home": gw["was_home"],
                    "kickoff_time": gw["kickoff_time"],
                    
                    # Target variable
                    "total_points": gw["total_points"],
                    
                    # Playing time
                    "minutes": gw["minutes"],
                    "starts": gw.get("starts", 0),
                    
                    # Goals & assists
                    "goals_scored": gw["goals_scored"],
                    "assists": gw["assists"],
                    "clean_sheets": gw["clean_sheets"],
                    "goals_conceded": gw["goals_conceded"],
                    
                    # Other events
                    "own_goals": gw["own_goals"],
                    "penalties_saved": gw["penalties_saved"],
                    "penalties_missed": gw["penalties_missed"],
                    "yellow_cards": gw["yellow_cards"],
                    "red_cards": gw["red_cards"],
                    "saves": gw["saves"],
                    
                    # Bonus
                    "bonus": gw["bonus"],
                    "bps": gw["bps"],
                    
                    # ICT
                    "influence": float(gw["influence"]),
                    "creativity": float(gw["creativity"]),
                    "threat": float(gw["threat"]),
                    "ict_index": float(gw["ict_index"]),
                    
                    # Expected stats
                    "expected_goals": float(gw.get("expected_goals", 0) or 0),
                    "expected_assists": float(gw.get("expected_assists", 0) or 0),
                    "expected_goal_involvements": float(gw.get("expected_goal_involvements", 0) or 0),
                    "expected_goals_conceded": float(gw.get("expected_goals_conceded", 0) or 0),
                    
                    # Price & ownership at that GW
                    "value": gw["value"] / 10,  # Convert to millions
                    "selected": gw["selected"],
                    "transfers_in": gw["transfers_in"],
                    "transfers_out": gw["transfers_out"],
                    "transfers_balance": gw["transfers_balance"],
                }
                all_records.append(record)
            
            # Small delay to be nice to the API
            await asyncio.sleep(0.1)
    
    print()
    print(f"✅ Collected {len(all_records)} gameweek records")
    print()
    
    # Step 4: Create DataFrame and save
    df = pd.DataFrame(all_records)
    
    # Sort by player and gameweek
    df = df.sort_values(["player_id", "gameweek"]).reset_index(drop=True)
    
    # Save to CSV
    output_path = OUTPUT_DIR / "fpl_gameweek_data.csv"
    df.to_csv(output_path, index=False)
    print(f"💾 Saved to: {output_path}")
    
    # Also save metadata
    metadata = {
        "collected_at": datetime.now().isoformat(),
        "current_gameweek": current_gw["id"],
        "total_players": len(active_players),
        "total_records": len(all_records),
        "min_minutes_filter": MIN_MINUTES,
        "gameweeks_available": df["gameweek"].nunique(),
        "columns": list(df.columns),
    }
    
    metadata_path = OUTPUT_DIR / "collection_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"💾 Metadata saved to: {metadata_path}")
    
    # Print summary
    print()
    print("=" * 60)
    print("DATA COLLECTION SUMMARY")
    print("=" * 60)
    print(f"Total records: {len(df):,}")
    print(f"Unique players: {df['player_id'].nunique()}")
    print(f"Gameweeks: {df['gameweek'].min()} to {df['gameweek'].max()}")
    print()
    print("Records by position:")
    print(df.groupby("position").size().to_string())
    print()
    print("Records by gameweek:")
    print(df.groupby("gameweek").size().to_string())
    print()
    
    return df


if __name__ == "__main__":
    df = asyncio.run(collect_all_data())
    print()
    print("🎉 Data collection complete! Run 02_eda.py next.")

