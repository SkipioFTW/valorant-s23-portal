import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
import tempfile
import re
import sys
import base64
import requests
import time
import functools
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GH_TOKEN = os.getenv("GH_TOKEN")
GH_OWNER = os.getenv("GH_OWNER") 
GH_REPO = os.getenv("GH_REPO") 
# GUILD_ID can be None for global commands
GUILD_ID = os.getenv("GUILD_ID", None) 
if GUILD_ID:
    GUILD_ID = int(GUILD_ID)

OWNER_ID = 781562217773662281  # User ID to report to

# Supabase / DB Init
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL") or os.getenv("DB_CONNECTION_STRING")

# Initialize Supabase Client
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL.strip('"'), SUPABASE_KEY.strip('"'))
        print("Supabase client initialized successfully!")
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")

# --- DATABASE CONNECTION POOLING ---

class UnifiedCursorWrapper:
    def __init__(self, cur):
        self.cur = cur
    
    def execute(self, sql, params=None):
        return self.cur.execute(sql, params)
        
    def __getattr__(self, name):
        return getattr(self.cur, name)
    
    def __iter__(self):
        return iter(self.cur)

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self.cur, "close"):
            self.cur.close()

class UnifiedDBWrapper:
    def __init__(self, conn):
        self.conn = conn
        
    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur
        
    def cursor(self):
        return UnifiedCursorWrapper(self.conn.cursor())
        
    def commit(self):
        self.conn.commit()
    def close(self):
        self.conn.close()
    def rollback(self):
        self.conn.rollback()
    def __getattr__(self, name):
        return getattr(self.conn, name)
    
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

# Global Connection Pool
pg_pool = None

def get_db_connection_pool():
    global pg_pool
    if pg_pool:
        return pg_pool
        
    db_url = SUPABASE_DB_URL
    if db_url:
        db_url_str = str(db_url).strip().strip('"').strip("'")
        if db_url_str.startswith("postgresql"):
            try:
                params = db_url_str
                if "sslmode" not in db_url_str:
                    params += "?sslmode=require" if "?" not in db_url_str else "&sslmode=require"
                
                # Min 1, Max 10 connections
                pg_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, params)
                print("Database connection pool created.")
                return pg_pool
            except Exception as e:
                print(f"Failed to create connection pool: {e}")
    return None

def get_conn():
    pool = get_db_connection_pool()
    if pool:
        try:
            conn = pool.getconn()
            wrapper = UnifiedDBWrapper(conn)
            
            # Monkey patch close to return to pool instead of closing
            original_close = wrapper.close
            def return_to_pool():
                try:
                    pool.putconn(conn)
                except Exception:
                    try:
                        conn.close()
                    except:
                        pass
            wrapper.close = return_to_pool
            wrapper.__exit__ = lambda exc_type, exc_val, exc_tb: return_to_pool()
            return wrapper
        except Exception as e:
            print(f"Error getting connection from pool: {e}")
    
    # Fallback to direct connection
    print("Fallback to direct connection")
    db_url = SUPABASE_DB_URL
    if db_url:
        try:
            conn = psycopg2.connect(db_url, sslmode='require', connect_timeout=10)
            return UnifiedDBWrapper(conn)
        except Exception as e:
            print(f"Direct connection failed: {e}")
            
    return None

# --- ASYNC HELPERS ---

async def run_in_executor(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args))

def fetch_standings_df(group):
    conn = get_conn()
    if not conn: return None
    try:
        query = """
        WITH team_matches AS (
            SELECT 
                team1_id as team_id,
                CASE WHEN COALESCE(mm.team1_rounds, m.score_t1) > COALESCE(mm.team2_rounds, m.score_t2) THEN 1 ELSE 0 END as win,
                CASE WHEN COALESCE(mm.team1_rounds, m.score_t1) < COALESCE(mm.team2_rounds, m.score_t2) THEN 1 ELSE 0 END as loss,
                CASE 
                    WHEN COALESCE(mm.team1_rounds, m.score_t1) > COALESCE(mm.team2_rounds, m.score_t2) THEN 15 
                    ELSE LEAST(COALESCE(mm.team1_rounds, m.score_t1), 12) 
                END as points,
                CASE 
                    WHEN COALESCE(mm.team2_rounds, m.score_t2) > COALESCE(mm.team1_rounds, m.score_t1) THEN 15 
                    ELSE LEAST(COALESCE(mm.team2_rounds, m.score_t2), 12) 
                END as points_against
            FROM matches m
            LEFT JOIN match_maps mm ON m.id = mm.match_id AND mm.map_index = 0
            WHERE m.status = 'completed' AND m.match_type = 'regular'

            UNION ALL

            SELECT 
                team2_id as team_id,
                CASE WHEN COALESCE(mm.team2_rounds, m.score_t2) > COALESCE(mm.team1_rounds, m.score_t1) THEN 1 ELSE 0 END as win,
                CASE WHEN COALESCE(mm.team2_rounds, m.score_t2) < COALESCE(mm.team1_rounds, m.score_t1) THEN 1 ELSE 0 END as loss,
                CASE 
                    WHEN COALESCE(mm.team2_rounds, m.score_t2) > COALESCE(mm.team1_rounds, m.score_t1) THEN 15 
                    ELSE LEAST(COALESCE(mm.team2_rounds, m.score_t2), 12) 
                END as points,
                CASE 
                    WHEN COALESCE(mm.team1_rounds, m.score_t1) > COALESCE(mm.team2_rounds, m.score_t2) THEN 15 
                    ELSE LEAST(COALESCE(mm.team1_rounds, m.score_t1), 12) 
                END as points_against
            FROM matches m
            LEFT JOIN match_maps mm ON m.id = mm.match_id AND mm.map_index = 0
            WHERE m.status = 'completed' AND m.match_type = 'regular'
        )
        SELECT 
            t.name,
            COALESCE(COUNT(tm.team_id), 0) as Played,
            COALESCE(SUM(tm.win), 0) as Wins,
            COALESCE(SUM(tm.loss), 0) as Losses,
            COALESCE(SUM(tm.points), 0) as Points,
            (COALESCE(SUM(tm.points), 0) - COALESCE(SUM(tm.points_against), 0)) as PD
        FROM teams t
        LEFT JOIN team_matches tm ON t.id = tm.team_id
        WHERE t.group_name ILIKE %s
        GROUP BY t.id
        ORDER BY Points DESC, PD DESC
        """
        # Use pandas with direct psycopg2 connection object (conn.conn)
        return pd.read_sql_query(query, conn.conn, params=(group,))
    except Exception as e:
        print(f"Standings error details: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        conn.close()

# --- BOT SETUP ---

intents = discord.Intents.default()
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"Synced commands to guild {GUILD_ID}")
        else:
            await self.tree.sync()
            print("Synced global commands")

bot = MyBot()

# --- HELPER FUNCTIONS ---

def is_admin_or_captain(interaction: discord.Interaction):
    # Check for specific roles or permissions
    allowed_roles = ["Admin", "Captain", "Moderator", "Owner"] 
    if isinstance(interaction.user, discord.Member):
        if any(role.name in allowed_roles for role in interaction.user.roles):
            return True
        if interaction.user.guild_permissions.administrator:
            return True
    return False

# --- SLASH COMMANDS ---

@bot.tree.command(name="match", description="Submit a match result")
@discord.app_commands.describe(
    team_a="Name of Team A", 
    team_b="Name of Team B", 
    group="Group Name (e.g. ALPHA)", 
    tracker_link="Tracker.gg Match URL"
)
async def match(interaction: discord.Interaction, team_a: str, team_b: str, group: str, tracker_link: str):
    await interaction.response.defer()
    
    if not is_admin_or_captain(interaction):
        await interaction.followup.send("❌ You do not have permission to submit matches.")
        return

    conn = get_conn()
    if not conn:
        await interaction.followup.send("❌ Error: Database connection failed.")
        return

    try:
        cursor = conn.cursor()
        # Insert into pending_matches
        # Using tracker_link as 'url'
        cursor.execute("""
            INSERT INTO pending_matches (team_a, team_b, group_name, url, submitted_by, status)
            VALUES (%s, %s, %s, %s, %s, 'new')
        """, (team_a, team_b, group, tracker_link, str(interaction.user)))
        conn.commit()
        
        # Formatted Reply
        embed = discord.Embed(title="✅ Match Submitted", color=discord.Color.green())
        embed.add_field(name="Matchup", value=f"{team_a} vs {team_b}", inline=False)
        embed.add_field(name="Group", value=group, inline=True)
        embed.add_field(name="Tracker Link", value=f"[Link]({tracker_link})", inline=True)
        embed.set_footer(text="Awaiting Admin Approval")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Database Error: {str(e)}")
    finally:
        conn.close()

@bot.tree.command(name="player", description="Register a new player")
@discord.app_commands.describe(
    riot_id="Riot ID (Name#TAG)", 
    rank="Current Rank",
    tracker_link="Tracker.gg Profile URL"
)
async def player(interaction: discord.Interaction, riot_id: str, rank: str, tracker_link: str):
    await interaction.response.defer()
    
    conn = get_conn()
    if not conn:
        await interaction.followup.send("❌ Error: Database connection failed.")
        return

    try:
        clean_rank = rank.strip()
        cursor = conn.cursor()
        
        # Insert into pending_players
        # We store submitted_by as usual, and also discord_handle (submitter's name)
        # tracker_link is stored in the new column
        discord_name = str(interaction.user.name) # Just the username
        
        cursor.execute("""
            INSERT INTO pending_players (riot_id, rank, tracker_link, submitted_by, status, discord_handle)
            VALUES (%s, %s, %s, %s, 'new', %s)
        """, (riot_id, clean_rank, tracker_link, str(interaction.user), discord_name))
        conn.commit()
        
        # Formatted Reply
        embed = discord.Embed(title="✅ Player Registration Submitted", color=discord.Color.blue())
        embed.add_field(name="Player", value=f"`{riot_id}`", inline=True)
        embed.add_field(name="Rank", value=f"`{clean_rank}`", inline=True)
        embed.add_field(name="Tracker", value=f"[Link]({tracker_link})", inline=False)
        embed.add_field(name="Discord Handle", value=f"@{discord_name}", inline=True)
        embed.set_footer(text="Pending Approval")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Database Error: {str(e)}")
    finally:
        conn.close()

@bot.tree.command(name="standings", description="View current group standings")
@discord.app_commands.describe(group="Group Name (e.g. ALPHA or BETA)")
async def standings(interaction: discord.Interaction, group: str):
    await interaction.response.defer()
    
    # Run blocking DB/Pandas call in executor
    df = await run_in_executor(fetch_standings_df, group)
    
    if df is None:
        await interaction.followup.send("❌ Error fetching standings.")
        return
        
    if df.empty:
        await interaction.followup.send(f"❌ No standings found for group `{group}`.")
        return

    msg = f"🏆 **Group {group.upper()} Standings**\n"
    msg += "```\nRank  Team                         P  W  L  Pts  PD\n"
    for i, row in enumerate(df.itertuples(), start=1):
        name = row.name
        msg += f"{i:>2}    {name[:26]:<26}  {row.Played:>2} {row.Wins:>2} {row.Losses:>2} {row.Points:>3} {row.PD:>3}\n"
    msg += "```"
    await interaction.followup.send(msg)

@bot.tree.command(name="leaderboard", description="Show top players by ACS")
@discord.app_commands.describe(min_games="Minimum games to include (default 0)")
async def leaderboard(interaction: discord.Interaction, min_games: int = 0):
    await interaction.response.defer()
    conn = get_conn()
    if not conn:
        await interaction.followup.send("❌ DB connection failed.")
        return
    try:
        query = """
            SELECT p.name,
                   p.riot_id,
                   t.tag as team,
                   COUNT(DISTINCT msm.match_id) as games,
                   AVG(msm.acs) as avg_acs,
                   SUM(msm.kills) as total_kills,
                   SUM(msm.deaths) as total_deaths
            FROM match_stats_map msm
            JOIN matches m ON msm.match_id = m.id
            JOIN players p ON msm.player_id = p.id
            LEFT JOIN teams t ON p.default_team_id = t.id
            WHERE m.status = 'completed'
            GROUP BY p.id, p.name, p.riot_id, t.tag
            HAVING COUNT(DISTINCT msm.match_id) >= %s
            ORDER BY avg_acs DESC
            LIMIT 10
        """
        cursor = conn.cursor()
        cursor.execute(query, (min_games,))
        rows = cursor.fetchall()
        
        if not rows:
            await interaction.followup.send("No data found.")
            return

        embed = discord.Embed(title="🏆 Leaderboard (ACS)", color=discord.Color.blue())
        for i, (name, riot_id, team, games, avg_acs, k, d) in enumerate(rows, start=1):
            d_val = d if d and d > 0 else 1
            kd = k / d_val if k else 0
            tag = f" ({riot_id})" if riot_id else ""
            embed.add_field(
                name=f"#{i} {name}{tag}", 
                value=f"Team: `{team or 'FA'}` | Games: `{games}` | ACS: `{round(avg_acs, 1)}` | KD: `{round(kd, 2)}`", 
                inline=False
            )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
    finally:
        conn.close()

@bot.tree.command(name="matches", description="Show upcoming matches")
async def matches(interaction: discord.Interaction):
    await interaction.response.defer()
    
    conn = get_conn()
    if not conn:
        await interaction.followup.send("❌ DB Error.")
        return
    
    try:
        cursor = conn.cursor()
        query = """
            SELECT m.week, t1.name, t2.name, m.status, m.match_type
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
            
        embed = discord.Embed(title="📅 Upcoming Matches", color=discord.Color.blue())
        for week, t1, t2, status, mtype in results:
            embed.add_field(name=f"Week {week} ({mtype})", value=f"**{t1}** vs **{t2}**\nStatus: `{status}`", inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
    finally:
        conn.close()

@bot.tree.command(name="player_info", description="Look up a player's stats")
@discord.app_commands.describe(name="Player name or Riot ID")
async def player_info(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    
    conn = get_conn()
    if not conn:
        await interaction.followup.send("❌ DB Error.")
        return
    
    try:
        cursor = conn.cursor()
        # Find player
        cursor.execute("""
            SELECT p.id, p.name, p.riot_id, p.rank, t.name as team_name
            FROM players p
            LEFT JOIN teams t ON p.default_team_id = t.id
            WHERE p.name ILIKE %s OR p.riot_id ILIKE %s
            LIMIT 1
        """, (name, name))
        row = cursor.fetchone()
        
        if not row:
            await interaction.followup.send(f"❌ Player `{name}` not found.")
            return
            
        pid, p_name, r_id, p_rank, t_name = row
        
        # Get Stats
        cursor.execute("""
            SELECT msm.acs, msm.kills, msm.deaths, msm.agent, msm.match_id
            FROM match_stats_map msm
            JOIN matches m ON msm.match_id = m.id
            WHERE msm.player_id = %s AND m.status = 'completed'
        """, (pid,))
        stats_rows = cursor.fetchall()
        
        games = 0; avg_acs = 0.0; kd = 0.0; top_agent = "N/A"
        
        if stats_rows:
            df = pd.DataFrame(stats_rows, columns=['acs', 'kills', 'deaths', 'agent', 'match_id'])
            games = df['match_id'].nunique()
            avg_acs = df['acs'].mean()
            k_sum = df['kills'].sum()
            d_sum = df['deaths'].sum()
            kd = k_sum / (d_sum if d_sum > 0 else 1)
            if 'agent' in df.columns:
                agent_counts = df['agent'].value_counts()
                top_agent = agent_counts.index[0] if not agent_counts.empty else "N/A"

        embed = discord.Embed(title=f"👤 Player: {p_name}", color=discord.Color.green())
        embed.add_field(name="Riot ID", value=f"`{r_id or 'N/A'}`", inline=True)
        embed.add_field(name="Rank", value=f"`{p_rank or 'Unranked'}`", inline=True)
        embed.add_field(name="Team", value=f"`{t_name or 'Free Agent'}`", inline=True)
        embed.add_field(name="Games", value=f"`{games}`", inline=True)
        embed.add_field(name="ACS", value=f"`{round(avg_acs,1)}`", inline=True)
        embed.add_field(name="KD", value=f"`{round(kd,2)}`", inline=True)
        embed.add_field(name="Agent", value=f"`{top_agent}`", inline=True)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
    finally:
        conn.close()

# --- CUSTOM REPLIES & REPORTING ---

@bot.tree.command(name="setreply", description="Set a custom reply (Admin Only)")
@discord.app_commands.describe(user_id="Discord User ID", message="Reply Message")
async def setreply(interaction: discord.Interaction, user_id: str, message: str):
    if not is_admin_or_captain(interaction):
        await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
        return
        
    conn = get_conn()
    if conn:
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS bot_replies (id SERIAL PRIMARY KEY, user_id TEXT UNIQUE, reply TEXT)")
            conn.commit()
            curr = conn.cursor()
            curr.execute("""
                INSERT INTO bot_replies (user_id, reply) VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET reply = EXCLUDED.reply
            """, (user_id, message))
            conn.commit()
            await interaction.response.send_message(f"✅ Reply set for user `{user_id}`.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
        finally:
            conn.close()
    else:
        await interaction.response.send_message("❌ DB Connection failed.", ephemeral=True)

@bot.tree.command(name="delreply", description="Delete a custom reply (Admin Only)")
async def delreply(interaction: discord.Interaction, user_id: str):
    if not is_admin_or_captain(interaction):
        await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
        return

    conn = get_conn()
    if conn:
        try:
            conn.execute("DELETE FROM bot_replies WHERE user_id = %s", (user_id,))
            conn.commit()
            await interaction.response.send_message(f"✅ Reply removed for user `{user_id}`.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
        finally:
            conn.close()
    else:
        await interaction.response.send_message("❌ DB Connection failed.", ephemeral=True)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Check for mentions
    if bot.user in message.mentions or (message.reference and message.reference.resolved and message.reference.resolved.author == bot.user):
        conn = get_conn()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("SELECT reply FROM bot_replies WHERE user_id=%s", (str(message.author.id),))
                row = cur.fetchone()
                
                if row and row[0]:
                    await message.reply(row[0]) # Reply to message
                    
                    if OWNER_ID:
                        try:
                            owner = await bot.fetch_user(OWNER_ID)
                            if owner:
                                await owner.send(f"🔔 **Reply Triggered!**\nUser: {message.author.name}\nMsg: {message.content}\nReply: {row[0]}")
                        except Exception as e:
                            print(f"Failed to report: {e}")
            except Exception as e:
                print(f"Reply error: {e}")
            finally:
                conn.close()

    await bot.process_commands(message)

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not set")
    else:
        bot.run(DISCORD_TOKEN)
