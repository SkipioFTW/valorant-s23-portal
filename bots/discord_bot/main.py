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
from supabase import create_client, Client
import pandas as pd

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
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

# Initialize Supabase Client
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL.strip('"'), SUPABASE_KEY.strip('"'))
        print("Supabase client initialized successfully!")
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")

# Database path (relative or absolute) for SQLite fallback
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
    # If using Supabase SDK, we don't strictly need a 'connection' object
    # for SELECT/INSERT, but we'll keep the wrapper for SQLite fallback logic
    # though eventually we want to move away from it.
    
    db_url = SUPABASE_DB_URL or os.getenv("SUPABASE_URL") # Try to get any DB string
    
    if db_url and "postgresql" in str(db_url):
        import psycopg2
        conn = None
        try:
            conn = psycopg2.connect(db_url)
        except Exception as e:
            # Fallback to manual parse if URL fails (special characters)
            try:
                import re
                match = re.search(r'postgresql://([^:]+):([^@]+)@([^:/]+):(\d+)/(.+)', str(db_url))
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
        
        if conn:
            return UnifiedDBWrapper(conn)
            
    # Always fallback to SQLite if Supabase DB connection fails
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
    
    # Use Supabase SDK if available
    if supabase:
        try:
            # 1. VALIDATION: Check if Teams exist
            res_a = supabase.table("teams").select("name").ilike("name", team_a).execute()
            if not res_a.data:
                await interaction.followup.send(f"❌ Error: **Team A ('{team_a}')** not found. Please check spelling.")
                return
            
            res_b = supabase.table("teams").select("name").ilike("name", team_b).execute()
            if not res_b.data:
                await interaction.followup.send(f"❌ Error: **Team B ('{team_b}')** not found. Please check spelling.")
                return

            # 2. INSERT into Pending Table
            supabase.table("pending_matches").insert({
                "team_a": team_a,
                "team_b": team_b,
                "group_name": group,
                "url": url,
                "submitted_by": str(interaction.user)
            }).execute()
            
            await interaction.followup.send(f"✅ **Match Queued!**\nTeams: `{team_a} vs {team_b}`\nAdmin will verify in the dashboard.")
            return
        except Exception as e:
            print(f"Supabase SDK Error: {e}")
            # Fallback to legacy SQL below

    conn = get_db_conn()
    if not conn:
        await interaction.followup.send("❌ Error: Database connection failed.")
        return

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM teams WHERE LOWER(name) = LOWER(%s)", (team_a,))
        if not cursor.fetchone():
            await interaction.followup.send(f"❌ Error: **Team A ('{team_a}')** not found.")
            return
            
        cursor.execute("SELECT name FROM teams WHERE LOWER(name) = LOWER(%s)", (team_b,))
        if not cursor.fetchone():
            await interaction.followup.send(f"❌ Error: **Team B ('{team_b}')** not found.")
            return

        cursor.execute("""
            INSERT INTO pending_matches (team_a, team_b, group_name, url, submitted_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (team_a, team_b, group, url, str(interaction.user)))
        conn.commit()
        await interaction.followup.send(f"✅ **Match Queued!** (SQLite Fallback)")
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
    
    clean_rank = rank.strip()
    if clean_rank not in ALLOWED_RANKS:
        ranks_list = "\n".join([f"- {r}" for r in ALLOWED_RANKS])
        await interaction.followup.send(f"❌ Error: **'{rank}'** is invalid.\nOptions:\n{ranks_list}")
        return

    if supabase:
        try:
            supabase.table("pending_players").insert({
                "riot_id": riot_id,
                "rank": clean_rank,
                "discord_handle": discord_handle,
                "submitted_by": str(interaction.user)
            }).execute()
            await interaction.followup.send(f"✅ **Registration Submitted!**\nPlayer: `{riot_id}`\nPending Approval.")
            return
        except Exception as e:
            print(f"Supabase SDK Error: {e}")

    conn = get_db_conn()
    if not conn:
        await interaction.followup.send("❌ Error: Database connection failed.")
        return

    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pending_players (riot_id, rank, discord_handle, submitted_by)
            VALUES (%s, %s, %s, %s)
        """, (riot_id, clean_rank, discord_handle, str(interaction.user)))
        conn.commit()
        await interaction.followup.send(f"✅ **Registration Submitted!** (SQLite Fallback)")
    except Exception as e:
        await interaction.followup.send(f"❌ Database Error: {str(e)}")
    finally:
        conn.close()

@bot.tree.command(name="standings", description="View current group standings")
@discord.app_commands.describe(group="Group Name (e.g. ALPHA or BETA)")
async def standings(interaction: discord.Interaction, group: str):
    await interaction.response.defer()
    
    if supabase:
        try:
            # 1) Get teams for this group
            res_teams = supabase.table("teams").select("id, name, group_name").ilike("group_name", group).execute()
            teams = res_teams.data or []
            if not teams:
                await interaction.followup.send(f"❌ No teams found in group `{group}`.")
                return
            team_df = pd.DataFrame(teams)
            ids = team_df['id'].tolist()

            # 2) Get matches and filter by both teams belonging to this group
            #    (handles cases where match.group_name is missing or inconsistent)
            res_matches = supabase.table("matches")\
                .select("id, team1_id, team2_id, group_name, status, match_type, format, score_t1, score_t2")\
                .execute()
            matches = res_matches.data or []
            if not matches:
                # Show teams list if no matches yet
                msg = f"🏆 **Group {group.upper()} Teams**\n```\n"
                for row in teams:
                    msg += f"- {row['name']}\n"
                msg += "```\n_No completed matches yet_"
                await interaction.followup.send(msg)
                return
            mdf = pd.DataFrame(matches)
            mdf['status'] = mdf['status'].astype(str).str.lower()
            mdf = mdf[(mdf['match_type'].fillna('').str.lower() != 'playoff')]
            # Keep only matches where both teams are within the group's team ids
            team_ids = set(ids)
            mdf = mdf[mdf['team1_id'].isin(team_ids) & mdf['team2_id'].isin(team_ids)]

            # 3) Join map rounds for these matches
            res_maps = supabase.table("match_maps").select("match_id, map_index, team1_rounds, team2_rounds, winner_id").in_("match_id", mdf['id'].tolist()).execute()
            maps = res_maps.data or []
            maps_df = pd.DataFrame(maps)
            if not maps_df.empty:
                agg = maps_df.groupby('match_id').agg({'team1_rounds':'sum','team2_rounds':'sum'}).reset_index()
                agg.columns = ['id','agg_t1_rounds','agg_t2_rounds']
                mdf = mdf.merge(agg, on='id', how='left')

                # Map win counts
                cnt = maps_df.groupby(['match_id','winner_id']).size().reset_index(name='win_count')
                m_t1 = mdf.merge(cnt, left_on=['id','team1_id'], right_on=['match_id','winner_id'], how='left')
                mdf['wins_t1'] = m_t1['win_count'].fillna(0).astype(int)
                m_t2 = mdf.merge(cnt, left_on=['id','team2_id'], right_on=['match_id','winner_id'], how='left')
                mdf['wins_t2'] = m_t2['win_count'].fillna(0).astype(int)

            # 4) Derive match scores
            for col in ['agg_t1_rounds','agg_t2_rounds','wins_t1','wins_t2','score_t1','score_t2']:
                if col in mdf.columns:
                    mdf[col] = pd.to_numeric(mdf[col], errors='coerce').fillna(0)
            if 'score_t1' not in mdf.columns:
                mdf['score_t1'] = 0
            if 'score_t2' not in mdf.columns:
                mdf['score_t2'] = 0
            # Override with aggregated rounds when available
            if 'agg_t1_rounds' in mdf.columns:
                mdf['score_t1'] = mdf.apply(lambda r: (r['agg_t1_rounds'] if r['agg_t1_rounds'] > 0 else r['score_t1']), axis=1)
            if 'agg_t2_rounds' in mdf.columns:
                mdf['score_t2'] = mdf.apply(lambda r: (r['agg_t2_rounds'] if r['agg_t2_rounds'] > 0 else r['score_t2']), axis=1)
            # fallback to map wins if rounds missing
            if 'wins_t1' in mdf.columns:
                mdf['score_t1'] = mdf.apply(lambda r: (r['wins_t1'] if r['score_t1'] == 0 else r['score_t1']), axis=1)
            if 'wins_t2' in mdf.columns:
                mdf['score_t2'] = mdf.apply(lambda r: (r['wins_t2'] if r['score_t2'] == 0 else r['score_t2']), axis=1)

            # Only count matches that are effectively played: completed OR have rounds/scores
            played_mask = (
                mdf['status'] == 'completed'
            ) | (
                ((mdf['agg_t1_rounds'] + mdf['agg_t2_rounds']) > 0) if ('agg_t1_rounds' in mdf.columns and 'agg_t2_rounds' in mdf.columns) else False
            ) | (
                ((mdf['score_t1'] + mdf['score_t2']) > 0)
            )
            mdf = mdf[played_mask]

            # 5) Points model (same as portal): win => 15, else min(rounds,12)
            mdf['p1'] = mdf.apply(lambda r: (15 if r['score_t1'] > r['score_t2'] else min(int(r['score_t1']), 12)), axis=1)
            mdf['p2'] = mdf.apply(lambda r: (15 if r['score_t2'] > r['score_t1'] else min(int(r['score_t2']), 12)), axis=1)
            mdf['t1_win'] = (mdf['score_t1'] > mdf['score_t2']).astype(int)
            mdf['t2_win'] = (mdf['score_t2'] > mdf['score_t1']).astype(int)

            # 6) Aggregate to team standings
            t1_stats = mdf.groupby('team1_id').agg({'t1_win':'sum','t2_win':'sum','p1':'sum','p2':'sum','id':'count'}).rename(columns={'t1_win':'Wins','t2_win':'Losses','p1':'Points','p2':'Points Against','id':'Played'})
            t2_stats = mdf.groupby('team2_id').agg({'t2_win':'sum','t1_win':'sum','p2':'sum','p1':'sum','id':'count'}).rename(columns={'t2_win':'Wins','t1_win':'Losses','p2':'Points','p1':'Points Against','id':'Played'})
            combined = pd.concat([t1_stats, t2_stats]).groupby(level=0).sum()
            combined['PD'] = combined['Points'] - combined['Points Against']
            combined = combined.reset_index().rename(columns={'index':'team_id'})
            final = team_df.merge(combined, left_on='id', right_on='team_id', how='left').fillna(0)
            final[['Wins','Losses','Points','Points Against','Played','PD']] = final[['Wins','Losses','Points','Points Against','Played','PD']].astype(int)
            final = final.sort_values(['Points','PD'], ascending=[False, False])

            # 7) Format message
            msg = f"🏆 **Group {group.upper()} Standings**\n"
            msg += "```\nRank  Team                         P  W  L  Pts  PD\n"
            for i, row in enumerate(final.itertuples(), start=1):
                name = row.name
                msg += f"{i:>2}    {name[:26]:<26}  {row.Played:>2} {row.Wins:>2} {row.Losses:>2} {row.Points:>3} {row.PD:>3}\n"
            msg += "```"
            await interaction.followup.send(msg)
            return
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}")
            return

    conn = get_db_conn()
    if not conn:
        await interaction.followup.send("❌ Error: Database connection failed.")
        return
    
    try:
        cursor = conn.cursor()
        # Get team ids and names in group
        cursor.execute("SELECT id, name FROM teams WHERE UPPER(group_name) = UPPER(%s)", (group,))
        trows = cursor.fetchall()
        if not trows:
            await interaction.followup.send(f"❌ No teams in group `{group}`.")
            return
        ids = [r[0] for r in trows]
        team_map = {r[0]: r[1] for r in trows}

        # Completed matches in this group
        cursor.execute("SELECT id, team1_id, team2_id FROM matches WHERE status='completed' AND UPPER(group_name) = UPPER(%s)", (group,))
        mrows = cursor.fetchall()
        if not mrows:
            msg = f"🏆 **Group {group.upper()} Teams** (Fallback)\n" + "\n".join([f"- {team_map[i]}" for i in ids])
            await interaction.followup.send(msg)
            return

        # Map rounds for these matches
        mids = tuple([r[0] for r in mrows])
        cursor.execute("SELECT match_id, map_index, team1_rounds, team2_rounds, winner_id FROM match_maps WHERE match_id IN (%s)" % ",".join(["%s"]*len(mids)), mids)
        maps = cursor.fetchall()
        mdf = pd.DataFrame(mrows, columns=['id','team1_id','team2_id'])
        if maps:
            mdf2 = pd.DataFrame(maps, columns=['match_id','map_index','team1_rounds','team2_rounds','winner_id'])
            agg = mdf2.groupby('match_id')[['team1_rounds','team2_rounds']].sum().reset_index().rename(columns={'match_id':'id','team1_rounds':'agg_t1_rounds','team2_rounds':'agg_t2_rounds'})
            mdf = mdf.merge(agg, on='id', how='left')
        mdf = mdf.fillna(0)

        # scores and points
        mdf['score_t1'] = mdf['agg_t1_rounds']
        mdf['score_t2'] = mdf['agg_t2_rounds']
        mdf['p1'] = mdf.apply(lambda r: (15 if r['score_t1'] > r['score_t2'] else min(int(r['score_t1']), 12)), axis=1)
        mdf['p2'] = mdf.apply(lambda r: (15 if r['score_t2'] > r['score_t1'] else min(int(r['score_t2']), 12)), axis=1)
        mdf['t1_win'] = (mdf['score_t1'] > mdf['score_t2']).astype(int)
        mdf['t2_win'] = (mdf['score_t2'] > mdf['score_t1']).astype(int)

        import numpy as np
        t1_stats = mdf.groupby('team1_id').agg({'t1_win':'sum','t2_win':'sum','p1':'sum','p2':'sum','id':'count'}).rename(columns={'t1_win':'Wins','t2_win':'Losses','p1':'Points','p2':'Points Against','id':'Played'})
        t2_stats = mdf.groupby('team2_id').agg({'t2_win':'sum','t1_win':'sum','p2':'sum','p1':'sum','id':'count'}).rename(columns={'t2_win':'Wins','t1_win':'Losses','p2':'Points','p1':'Points Against','id':'Played'})
        combined = pd.concat([t1_stats, t2_stats]).groupby(level=0).sum()
        combined['PD'] = combined['Points'] - combined['Points Against']
        combined = combined.reset_index().rename(columns={'index':'team_id'})
        final_rows = []
        for tid, name in team_map.items():
            row = combined[combined['team_id'] == tid]
            if row.empty:
                final_rows.append({'name': name, 'Played': 0, 'Wins': 0, 'Losses': 0, 'Points': 0, 'PD': 0})
            else:
                r = row.iloc[0]
                final_rows.append({'name': name, 'Played': int(r['Played']), 'Wins': int(r['Wins']), 'Losses': int(r['Losses']), 'Points': int(r['Points']), 'PD': int(r['PD'])})
        final = pd.DataFrame(final_rows).sort_values(['Points','PD'], ascending=[False, False])

        msg = f"🏆 **Group {group.upper()} Standings** (Fallback)\n"
        msg += "```\nRank  Team                         P  W  L  Pts  PD\n"
        for i, row in enumerate(final.itertuples(), start=1):
            msg += f"{i:>2}    {row.name[:26]:<26}  {row.Played:>2} {row.Wins:>2} {row.Losses:>2} {row.Points:>3} {row.PD:>3}\n"
        msg += "```"
        await interaction.followup.send(msg)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
    finally:
        conn.close()

@bot.tree.command(name="matches", description="Show upcoming matches")
async def matches(interaction: discord.Interaction):
    await interaction.response.defer()
    
    if supabase:
        try:
            # Query matches with team names using SDK
            # Note: Supabase SDK can do joins if foreign keys are defined, 
            # but for simplicity we'll fetch matches and teams and join in Python 
            # or use a smarter select if the schema supports it.
            res = supabase.table("matches") \
                .select("week, status, team1:teams!team1_id(name), team2:teams!team2_id(name)") \
                .neq("status", "completed") \
                .order("week") \
                .limit(5) \
                .execute()
            
            if not res.data:
                await interaction.followup.send("📅 No upcoming matches.")
                return

            embed = discord.Embed(title="📅 Upcoming Matches", color=discord.Color.blue())
            for m in res.data:
                t1 = m['team1']['name']
                t2 = m['team2']['name']
                embed.add_field(
                    name=f"Week {m['week']}", 
                    value=f"**{t1}** vs **{t2}**\nStatus: `{m['status']}`", 
                    inline=False
                )
            await interaction.followup.send(embed=embed)
            return
        except Exception as e:
            print(f"Supabase SDK Error: {e}")

    conn = get_db_conn()
    if not conn:
        await interaction.followup.send("❌ Error: Database connection failed.")
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
            await interaction.followup.send("📅 No upcoming matches.")
            return
            
        embed = discord.Embed(title="📅 Upcoming Matches (Fallback)", color=discord.Color.blue())
        for week, t1, t2, status in results:
            embed.add_field(name=f"Week {week}", value=f"**{t1}** vs **{t2}**\nStatus: `{status}`", inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
    finally:
        conn.close()

@bot.tree.command(name="player_info", description="Look up a player's profile with performance stats")
@discord.app_commands.describe(name="Player name or Riot ID")
async def player_info(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    
    if supabase:
        try:
            res = supabase.table("players") \
                .select("id,name,riot_id,rank, team:teams!default_team_id(name)") \
                .or_(f"name.ilike.{name},riot_id.ilike.{name}") \
                .limit(1) \
                .execute()
            if res.data:
                p = res.data[0]
                pid = p.get('id')
                team_name = p.get('team', {}).get('name') if p.get('team') else 'Free Agent'
                games = 0; avg_acs = 0.0; kd = 0.0; top_agent = 'N/A'
                agents = []
                if pid:
                    rs = supabase.table("match_stats_map").select("acs,kills,deaths,assists,agent,match_id").eq("player_id", pid).execute()
                    if rs.data:
                        sdf = pd.DataFrame(rs.data)
                        if not sdf.empty:
                            games = sdf['match_id'].nunique()
                            avg_acs = float(sdf['acs'].mean())
                            total_k = int(sdf['kills'].sum()); total_d = int(sdf['deaths'].sum())
                            kd = (total_k / (total_d if total_d != 0 else 1)) if total_k or total_d else 0.0
                            if 'agent' in sdf.columns:
                                ag = sdf.groupby('agent').agg(maps=('match_id','nunique'), avg_acs=('acs','mean')).reset_index()
                                ag = ag.sort_values(['maps','avg_acs'], ascending=[False, False])
                                agents = ag.head(3).values.tolist()
                                if not ag.empty:
                                    top_agent = str(ag.iloc[0]['agent'])
                embed = discord.Embed(title=f"👤 Player: {p['name']}", color=discord.Color.green())
                embed.add_field(name="Riot ID", value=f"`{p.get('riot_id') or 'N/A'}`", inline=True)
                embed.add_field(name="Rank", value=f"`{p.get('rank') or 'Unranked'}`", inline=True)
                embed.add_field(name="Team", value=f"`{team_name}`", inline=True)
                embed.add_field(name="Games", value=f"`{games}`", inline=True)
                embed.add_field(name="Avg ACS", value=f"`{round(avg_acs,1)}`", inline=True)
                embed.add_field(name="KD Ratio", value=f"`{round(kd,2)}`", inline=True)
                if top_agent and top_agent != 'N/A':
                    try:
                        ta_row = [r for r in agents if r[0] == top_agent]
                        maps_played = int(ta_row[0][1]) if ta_row else 0
                        ta_acs = float(ta_row[0][2]) if ta_row else 0.0
                    except Exception:
                        maps_played = 0; ta_acs = 0.0
                    embed.add_field(name="Top Agent", value=f"`{top_agent}` — maps: `{maps_played}`, avg ACS: `{round(ta_acs,1)}`", inline=False)
                if agents:
                    lines = []
                    for row in agents:
                        # row: [agent, maps, avg_acs]
                        lines.append(f"{row[0]} — maps: {int(row[1])}, ACS: {round(float(row[2]),1)}")
                    embed.add_field(name="Agent Summary", value="\n".join(lines), inline=False)
                await interaction.followup.send(embed=embed)
                return
        except Exception as e:
            print(f"Supabase SDK Error: {e}")

    conn = get_db_conn()
    if not conn:
        await interaction.followup.send("❌ Error: Database connection failed.")
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.name, p.riot_id, p.rank, t.name as team_name
            FROM players p
            LEFT JOIN teams t ON p.default_team_id = t.id
            WHERE LOWER(p.name) = LOWER(%s) OR LOWER(p.riot_id) = LOWER(%s)
            LIMIT 1
        """, (name, name))
        row = cursor.fetchone()
        if not row:
            await interaction.followup.send(f"❌ Player `{name}` not found.")
            return
        pid, p_name, r_id, p_rank, t_name = row
        # Gather stats
        games = 0; avg_acs = 0.0; kd = 0.0; top_agent = 'N/A'; agents = []
        try:
            cursor.execute("""
                SELECT acs, kills, deaths, assists, agent, match_id
                FROM match_stats_map
                WHERE player_id = %s
            """, (pid,))
            rows = cursor.fetchall()
            if rows:
                sdf = pd.DataFrame(rows, columns=['acs','kills','deaths','assists','agent','match_id'])
                games = sdf['match_id'].nunique()
                avg_acs = float(sdf['acs'].mean())
                total_k = int(sdf['kills'].sum()); total_d = int(sdf['deaths'].sum())
                kd = (total_k / (total_d if total_d != 0 else 1)) if total_k or total_d else 0.0
                if 'agent' in sdf.columns:
                    ag = sdf.groupby('agent').agg(maps=('match_id','nunique'), avg_acs=('acs','mean')).reset_index()
                    ag = ag.sort_values(['maps','avg_acs'], ascending=[False, False])
                    agents = ag.head(3).values.tolist()
                    if not ag.empty:
                        top_agent = str(ag.iloc[0]['agent'])
        except Exception:
            pass
        embed = discord.Embed(title=f"👤 Player: {p_name}", color=discord.Color.green())
        embed.add_field(name="Riot ID", value=f"`{r_id or 'N/A'}`", inline=True)
        embed.add_field(name="Rank", value=f"`{p_rank or 'Unranked'}`", inline=True)
        embed.add_field(name="Team", value=f"`{t_name or 'Free Agent'}`", inline=True)
        embed.add_field(name="Games", value=f"`{games}`", inline=True)
        embed.add_field(name="Avg ACS", value=f"`{round(avg_acs,1)}`", inline=True)
        embed.add_field(name="KD Ratio", value=f"`{round(kd,2)}`", inline=True)
        if top_agent and top_agent != 'N/A':
            try:
                ta_row = [r for r in agents if r[0] == top_agent]
                maps_played = int(ta_row[0][1]) if ta_row else 0
                ta_acs = float(ta_row[0][2]) if ta_row else 0.0
            except Exception:
                maps_played = 0; ta_acs = 0.0
            embed.add_field(name="Top Agent", value=f"`{top_agent}` — maps: `{maps_played}`, avg ACS: `{round(ta_acs,1)}`", inline=False)
        if agents:
            lines = []
            for row in agents:
                lines.append(f"{row[0]} — maps: {int(row[1])}, ACS: {round(float(row[2]),1)}")
            embed.add_field(name="Agent Summary", value="\n".join(lines), inline=False)
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
