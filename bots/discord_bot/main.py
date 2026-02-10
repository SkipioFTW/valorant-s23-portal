import discord
from discord.ext import commands
import os
import json
import asyncio
import tempfile
import re
import sys
import base64
import requests
import sqlite3
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path to import scripts if needed
# But for a standalone bot, we might duplicate the scraper logic or import it
# if we mount the volume. For now, we will duplicate the critical scraper logic
# to ensure it runs standalone in the container without complex mounting.

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GH_TOKEN = os.getenv("GH_TOKEN")
GH_OWNER = os.getenv("GH_OWNER", "SkipioFTW") # Default owner
GH_REPO = os.getenv("GH_REPO", "valorant-s23-portal") # Default repo
GUILD_ID = int(os.getenv("GUILD_ID", "1470636024110776322"))

# Database path (relative or absolute)
DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "valorant_s23.db"))

# Intents
intents = discord.Intents.default()
# intents.message_content = True # Not strictly needed for slash commands, but good to have

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Sync commands to the specific guild for instant updates during dev
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        print(f"Synced commands to guild {GUILD_ID}")

bot = MyBot()

# --- HELPER FUNCTIONS ---

def get_headers():
    return {
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Authorization': f"Bearer {GH_TOKEN}"
    }

def upload_to_github(path, content_str, message):
    if not GH_TOKEN:
        return False, "GH_TOKEN not set"
    
    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json" 
    }
    
    # Check if exists
    sha = None
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")
        
    payload = {
        "message": message,
        "content": base64.b64encode(content_str.encode('utf-8')).decode('ascii'),
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha
        
    r = requests.put(url, headers=headers, json=payload)
    if r.status_code in [200, 201]:
        return True, f"https://github.com/{GH_OWNER}/{GH_REPO}/blob/main/{path}"
    else:
        return False, f"Error {r.status_code}: {r.text}"

def get_db_conn():
    try:
        return sqlite3.connect(DB_PATH)
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

# Allowed ranks for validation
ALLOWED_RANKS = ["Unranked", "Iron/Bronze", "Silver", "Gold", "Platinum", "Diamond", "Ascendant", "Immortal 1/2", "Immortal 3/Radiant"]



# --- SLASH COMMANDS ---

@bot.tree.command(name="match", description="Submit a match for Admin verification")
@discord.app_commands.describe(
    team_a="Name of Team A", 
    team_b="Name of Team B", 
    group="Group Name (e.g. ALPHA)", 
    url="Tracker.gg Match URL"
)
async def match(interaction: discord.Interaction, team_a: str, team_b: str, group: str, url: str):
    await interaction.response.defer(thinking=True)
    
    conn = get_db_conn()
    if not conn:
        await interaction.followup.send("❌ Error: Could not connect to the database. Please contact an Admin.")
        return

    # 1. VALIDATION: Check if Teams exist
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM teams WHERE LOWER(name) = LOWER(?)", (team_a,))
    if not cursor.fetchone():
        await interaction.followup.send(f"❌ Error: **Team A ('{team_a}')** not found in the database. Please check the spelling.")
        conn.close()
        return
        
    cursor.execute("SELECT name FROM teams WHERE LOWER(name) = LOWER(?)", (team_b,))
    if not cursor.fetchone():
        await interaction.followup.send(f"❌ Error: **Team B ('{team_b}')** not found in the database. Please check the spelling.")
        conn.close()
        return

    # 2. INSERT into Pending Table
    try:
        cursor.execute("""
            INSERT INTO pending_matches (team_a, team_b, group_name, url, submitted_by)
            VALUES (?, ?, ?, ?, ?)
        """, (team_a, team_b, group, url, str(interaction.user)))
        conn.commit()
        await interaction.followup.send(f"✅ **Match Queued!**\nTeams: `{team_a} vs {team_b}`\nAdmin will verify the data in the dashboard.")
    except Exception as e:
        await interaction.followup.send(f"❌ Database Error: {str(e)}")
    finally:
        conn.close()

@bot.tree.command(name="player", description="Register a new player for approval")
@discord.app_commands.describe(
    discord_handle="Player's Discord @ (e.g. @User)", 
    riot_id="Riot ID (Name#TAG)", 
    rank="Current Rank"
)
async def player(interaction: discord.Interaction, discord_handle: str, riot_id: str, rank: str):
    await interaction.response.defer()
    
    # 1. VALIDATION: Check Rank
    clean_rank = rank.strip()
    if clean_rank not in ALLOWED_RANKS:
        ranks_list = "\n".join([f"- {r}" for r in ALLOWED_RANKS])
        await interaction.followup.send(f"❌ Error: **'{rank}'** is not a valid rank.\nPlease use one of the following:\n{ranks_list}")
        return

    # 2. INSERT into Pending Table
    conn = get_db_conn()
    if not conn:
        await interaction.followup.send("❌ Error: Could not connect to the database.")
        return

    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pending_players (riot_id, rank, discord_handle, submitted_by)
            VALUES (?, ?, ?, ?)
        """, (riot_id, clean_rank, discord_handle, str(interaction.user)))
        conn.commit()
        await interaction.followup.send(f"✅ **Registration Submitted!**\nPlayer: `{riot_id}`\nRank: `{clean_rank}`\nPending Approval in Admin Panel.")
    except Exception as e:
        await interaction.followup.send(f"❌ Database Error: {str(e)}")
    finally:
        conn.close()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not set")
    else:
        try:
            bot.run(DISCORD_TOKEN)
        except Exception as e:
            print(f"Error running bot: {e}")
