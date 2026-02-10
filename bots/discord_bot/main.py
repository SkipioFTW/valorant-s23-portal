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
try:
    import psycopg2
except ImportError:
    psycopg2 = None
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
SUPABASE_URL = os.getenv("SUPABASE_URL")

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

class UnifiedCursorWrapper:
    def __init__(self, cur, is_sqlite):
        self.cur = cur
        self.is_sqlite = is_sqlite
    
    def execute(self, sql, params=None):
        final_sql = sql
        if self.is_sqlite and "%s" in sql:
            final_sql = sql.replace("%s", "?")
        if params:
            return self.cur.execute(final_sql, params)
        return self.cur.execute(final_sql)
        
    def __getattr__(self, name):
        return getattr(self.cur, name)
    
    def __iter__(self):
        return iter(self.cur)

    # Add Context Manager support
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self.cur, "close"):
            self.cur.close()

class UnifiedDBWrapper:
    def __init__(self, conn):
        self.conn = conn
        self.is_sqlite = isinstance(conn, sqlite3.Connection)
        
    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur
        
    def cursor(self):
        return UnifiedCursorWrapper(self.conn.cursor(), self.is_sqlite)
        
    def commit(self):
        self.conn.commit()
    def close(self):
        self.conn.close()
    def rollback(self):
        self.conn.rollback()
    def __getattr__(self, name):
        return getattr(self.conn, name)
    
    # Add Context Manager support
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

def get_db_conn():
    # Priority: SUPABASE_DB_URL, then legacy SUPABASE_URL
    db_url = os.getenv("SUPABASE_DB_URL") or os.getenv("SUPABASE_URL")
    
    if db_url:
        import psycopg2
        conn = None
        # Check if it's a connection string
        if isinstance(db_url, str) and (db_url.startswith("postgresql") or "db.tekwoxehaktajyizaacj.supabase.co" in db_url):
            try:
                conn = psycopg2.connect(db_url)
            except Exception as e:
                # Fallback to manual parse if URL fails
                try:
                    import re
                    match = re.search(r'postgresql://([^:]+):([^@]+)@([^:/]+):(\d+)/(.+)', db_url)
                    if match:
                        user, pwd, host, port, db = match.groups()
                        from urllib.parse import unquote
                        conn = psycopg2.connect(
                            user=unquote(user),
                            password=unquote(pwd),
                            host=unquote(host),
                            port=port,
                            database=unquote(db),
                            connect_timeout=10
                        )
                except:
                    pass
        elif isinstance(db_url, dict):
            try:
                conn = psycopg2.connect(**db_url)
            except:
                pass
                
        if conn:
            return UnifiedDBWrapper(conn)
            
        print("Supabase connection failed, checking for local fallback...")
        if os.path.exists(DB_PATH):
            return UnifiedDBWrapper(sqlite3.connect(DB_PATH))
        return None
    
    if os.path.exists(DB_PATH):
        return UnifiedDBWrapper(sqlite3.connect(DB_PATH))
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
    cursor.execute("SELECT name FROM teams WHERE LOWER(name) = LOWER(%s)", (team_a,))
    if not cursor.fetchone():
        await interaction.followup.send(f"❌ Error: **Team A ('{team_a}')** not found in the database. Please check the spelling.")
        conn.close()
        return
        
    cursor.execute("SELECT name FROM teams WHERE LOWER(name) = LOWER(%s)", (team_b,))
    if not cursor.fetchone():
        await interaction.followup.send(f"❌ Error: **Team B ('{team_b}')** not found in the database. Please check the spelling.")
        conn.close()
        return

    # 2. INSERT into Pending Table
    try:
        cursor.execute("""
            INSERT INTO pending_matches (team_a, team_b, group_name, url, submitted_by)
            VALUES (%s, %s, %s, %s, %s)
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
            VALUES (%s, %s, %s, %s)
        """, (riot_id, clean_rank, discord_handle, str(interaction.user)))
        conn.commit()
        await interaction.followup.send(f"✅ **Registration Submitted!**\nPlayer: `{riot_id}`\nRank: `{clean_rank}`\nPending Approval in Admin Panel.")
    except Exception as e:
        await interaction.followup.send(f"❌ Database Error: {str(e)}")
    finally:
        conn.close()

@bot.tree.command(name="standings", description="View current group standings")
@discord.app_commands.describe(group="Group Name (e.g. ALPHA or BETA)")
async def standings(interaction: discord.Interaction, group: str):
    await interaction.response.defer()
    conn = get_db_conn()
    if not conn:
        await interaction.followup.send("❌ Error: Could not connect to database.")
        return
    
    try:
        is_postgres = not isinstance(conn, sqlite3.Connection)
        placeholder = "%s" if is_postgres else "?"
        cursor = conn.cursor()
        
        # Simple fetching of teams in the group
        cursor.execute(f"SELECT name FROM teams WHERE UPPER(group_name) = UPPER({placeholder})", (group,))
        teams = cursor.fetchall()
        if not teams:
            await interaction.followup.send(f"❌ No teams found in group `{group}`.")
            return

        msg = f"🏆 **Group {group.upper()} Teams**\n```\n"
        for row in teams:
            msg += f"- {row[0]}\n"
        msg += "```\n*Full standings with points/PD available in the portal.*"
        await interaction.followup.send(msg)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
    finally:
        conn.close()

@bot.tree.command(name="matches", description="Show upcoming matches")
async def matches(interaction: discord.Interaction):
    await interaction.response.defer()
    conn = get_db_conn()
    if not conn:
        await interaction.followup.send("❌ Error: Could not connect to database.")
        return
    
    try:
        cursor = conn.cursor()
        query = """
            SELECT m.week, t1.name, t2.name, m.status
            FROM matches m
            JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            WHERE m.status != 'completed'
            ORDER BY m.week ASC, m.id ASC
            LIMIT 5
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        if not results:
            await interaction.followup.send("📅 No upcoming matches scheduled.")
            return
            
        embed = discord.Embed(title="📅 Upcoming Matches", color=discord.Color.blue())
        for week, t1, t2, status in results:
            embed.add_field(
                name=f"Week {week}", 
                value=f"**{t1}** vs **{t2}**\nStatus: `{status}`", 
                inline=False
            )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
    finally:
        conn.close()

@bot.tree.command(name="player_info", description="Look up a player's profile")
@discord.app_commands.describe(name="Player name or Riot ID")
async def player_info(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    conn = get_db_conn()
    if not conn:
        await interaction.followup.send("❌ Error: Could not connect to database.")
        return
    
    try:
        is_postgres = not isinstance(conn, sqlite3.Connection)
        placeholder = "%s" if is_postgres else "?"
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT p.name, p.riot_id, p.rank, t.name as team_name
            FROM players p
            LEFT JOIN teams t ON p.default_team_id = t.id
            WHERE LOWER(p.name) = LOWER({placeholder}) OR LOWER(p.riot_id) = LOWER({placeholder})
        """, (name, name))
        
        row = cursor.fetchone()
        if not row:
            await interaction.followup.send(f"❌ Player `{name}` not found.")
            return
            
        p_name, riot_id, rank, team = row
        embed = discord.Embed(title=f"👤 Player: {p_name}", color=discord.Color.green())
        embed.add_field(name="Riot ID", value=f"`{riot_id or 'N/A'}`", inline=True)
        embed.add_field(name="Rank", value=f"`{rank or 'Unranked'}`", inline=True)
        embed.add_field(name="Team", value=f"`{team or 'Free Agent'}`", inline=True)
        
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
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
