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
    
    # Extract intended ID or use random UUID if URL is weird
    match_id = "unknown"
    try:
        if "tracker.gg" in url:
            match_id = url.split('/')[-1]
        else:
            import uuid
            match_id = str(uuid.uuid4())[:8]
    except:
        match_id = "unknown"

    # Create Pending Match Object
    data = {
        "team_a": team_a,
        "team_b": team_b,
        "group": group,
        "url": url,
        "submitted_by": str(interaction.user),
        "status": "pending_verification",
        "timestamp": str(interaction.created_at)
    }

    # Upload to pending_matches folder
    json_str = json.dumps(data, indent=4)
    file_path = f"assets/pending_matches/pending_{match_id}.json"
    
    success, result = upload_to_github(file_path, json_str, f"Bot Add Pending Match {match_id}")
    
    if success:
        await interaction.followup.send(f"✅ **Match Queued for Verification!**\nAdmin will verify scrape data.\nFile: `{file_path}`")
    else:
        await interaction.followup.send(f"❌ GitHub Upload Failed: {result}")

@bot.tree.command(name="player", description="Register a new player for approval")
@discord.app_commands.describe(
    discord_handle="Player's Discord @ (e.g. @User)", 
    riot_id="Riot ID (Name#TAG)", 
    rank="Current Rank"
)
async def player(interaction: discord.Interaction, discord_handle: str, riot_id: str, rank: str):
    await interaction.response.defer()
    
    # Create valid filename
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', riot_id)
    
    data = {
        "discord_handle": discord_handle,
        "riot_id": riot_id,
        "rank": rank,
        "submitted_by": str(interaction.user),
        "status": "pending",
        "timestamp": str(interaction.created_at)
    }
    
    json_str = json.dumps(data, indent=4)
    file_path = f"assets/pending_players/{safe_name}.json"
    
    success, result = upload_to_github(file_path, json_str, f"Bot Add Pending Player {riot_id}")
    
    if success:
        await interaction.followup.send(f"✅ **Player Registration Submitted!**\nPlayer: `{riot_id}`\nRank: `{rank}`\nPending Approval in Admin Panel.")
    else:
        await interaction.followup.send(f"❌ Upload Failed: {result}")

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
