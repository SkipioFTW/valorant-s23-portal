import discord
from discord.ext import commands, tasks
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
    def __init__(self, conn, close_callback=None):
        self.conn = conn
        self.close_callback = close_callback
        
    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur
        
    def cursor(self):
        return UnifiedCursorWrapper(self.conn.cursor())
        
    def commit(self):
        self.conn.commit()
    def close(self):
        if self.close_callback:
            self.close_callback()
        else:
            self.conn.close()
    def rollback(self):
        self.conn.rollback()
    def __getattr__(self, name):
        return getattr(self.conn, name)
    
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

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
            
            # Verify connection
            if conn.closed:
                try: pool.putconn(conn, close=True)
                except: pass
                conn = pool.getconn()
            
            # Ping
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            except:
                try: pool.putconn(conn, close=True)
                except: pass
                conn = pool.getconn()

            def return_to_pool():
                try:
                    pool.putconn(conn)
                except Exception:
                    try:
                        conn.close()
                    except:
                        pass
            
            return UnifiedDBWrapper(conn, close_callback=return_to_pool)
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
            -- Team 1 perspective
            SELECT
                m.team1_id as team_id,
                CASE 
                    WHEN m.winner_id = m.team1_id THEN 1
                    WHEN m.winner_id = m.team2_id THEN 0
                    WHEN COALESCE(mm.team1_rounds, 0) > COALESCE(mm.team2_rounds, 0) THEN 1
                    ELSE 0
                END as win,
                CASE 
                    WHEN m.winner_id = m.team2_id THEN 1
                    WHEN m.winner_id = m.team1_id THEN 0
                    WHEN COALESCE(mm.team2_rounds, 0) > COALESCE(mm.team1_rounds, 0) THEN 1
                    ELSE 0
                END as loss,
                CASE
                    WHEN m.winner_id = m.team1_id THEN 15
                    WHEN m.winner_id = m.team2_id THEN 
                        CASE WHEN m.is_forfeit = 1 THEN 0 ELSE LEAST(COALESCE(mm.team1_rounds, 0), 12) END
                    WHEN COALESCE(mm.team1_rounds, 0) > COALESCE(mm.team2_rounds, 0) THEN 15
                    ELSE LEAST(COALESCE(mm.team1_rounds, 0), 12)
                END as points,
                CASE
                    WHEN m.winner_id = m.team2_id THEN 15
                    WHEN m.winner_id = m.team1_id THEN 
                        CASE WHEN m.is_forfeit = 1 THEN 0 ELSE LEAST(COALESCE(mm.team2_rounds, 0), 12) END
                    WHEN COALESCE(mm.team2_rounds, 0) > COALESCE(mm.team1_rounds, 0) THEN 15
                    ELSE LEAST(COALESCE(mm.team2_rounds, 0), 12)
                END as points_against
            FROM public.matches m
            LEFT JOIN public.match_maps mm ON m.id = mm.match_id AND mm.map_index = 0
            WHERE m.status = 'completed' AND m.match_type = 'regular'
            
            UNION ALL
            
            -- Team 2 perspective
            SELECT
                m.team2_id as team_id,
                CASE 
                    WHEN m.winner_id = m.team2_id THEN 1
                    WHEN m.winner_id = m.team1_id THEN 0
                    WHEN COALESCE(mm.team2_rounds, 0) > COALESCE(mm.team1_rounds, 0) THEN 1
                    ELSE 0
                END as win,
                CASE 
                    WHEN m.winner_id = m.team1_id THEN 1
                    WHEN m.winner_id = m.team2_id THEN 0
                    WHEN COALESCE(mm.team1_rounds, 0) > COALESCE(mm.team2_rounds, 0) THEN 1
                    ELSE 0
                END as loss,
                CASE
                    WHEN m.winner_id = m.team2_id THEN 15
                    WHEN m.winner_id = m.team1_id THEN 
                        CASE WHEN m.is_forfeit = 1 THEN 0 ELSE LEAST(COALESCE(mm.team2_rounds, 0), 12) END
                    WHEN COALESCE(mm.team2_rounds, 0) > COALESCE(mm.team1_rounds, 0) THEN 15
                    ELSE LEAST(COALESCE(mm.team2_rounds, 0), 12)
                END as points,
                CASE
                    WHEN m.winner_id = m.team1_id THEN 15
                    WHEN m.winner_id = m.team2_id THEN 
                        CASE WHEN m.is_forfeit = 1 THEN 0 ELSE LEAST(COALESCE(mm.team1_rounds, 0), 12) END
                    WHEN COALESCE(mm.team1_rounds, 0) > COALESCE(mm.team2_rounds, 0) THEN 15
                    ELSE LEAST(COALESCE(mm.team1_rounds, 0), 12)
                END as points_against
            FROM public.matches m
            LEFT JOIN public.match_maps mm ON m.id = mm.match_id AND mm.map_index = 0
            WHERE m.status = 'completed' AND m.match_type = 'regular'
        )
        SELECT
            t.name,
            t.tag,
            COALESCE(COUNT(tm.team_id), 0) as Played,
            COALESCE(SUM(tm.win), 0) as Wins,
            COALESCE(SUM(tm.loss), 0) as Losses,
            COALESCE(SUM(tm.points), 0) as Points,
            (COALESCE(SUM(tm.points), 0) - COALESCE(SUM(tm.points_against), 0)) as PD
        FROM public.teams t
        LEFT JOIN team_matches tm ON t.id = tm.team_id
        WHERE t.group_name ILIKE %s
        GROUP BY t.id, t.name, t.tag
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
        
        # 1. VALIDATE TEAMS
        def _get_team_id(name_or_tag):
            cursor.execute("SELECT id FROM teams WHERE name ILIKE %s OR tag ILIKE %s LIMIT 1", (name_or_tag, name_or_tag))
            row = cursor.fetchone()
            return row[0] if row else None
            
        t1_id = _get_team_id(team_a)
        t2_id = _get_team_id(team_b)
        
        if not t1_id:
            await interaction.followup.send(f"❌ Team `{team_a}` not found in database.")
            return
        if not t2_id:
            await interaction.followup.send(f"❌ Team `{team_b}` not found in database.")
            return
            
        # 2. VALIDATE SCHEDULED MATCH
        cursor.execute("""
            SELECT id FROM matches 
            WHERE status = 'scheduled' 
            AND group_name ILIKE %s 
            AND ((team1_id = %s AND team2_id = %s) OR (team1_id = %s AND team2_id = %s))
            LIMIT 1
        """, (group, t1_id, t2_id, t2_id, t1_id))
        match_row = cursor.fetchone()
        
        if not match_row:
            await interaction.followup.send(f"❌ No scheduled match found for `{team_a}` vs `{team_b}` in group `{group}`.")
            return

        # 3. INSERT INTO PENDING
        cursor.execute("""
            INSERT INTO pending_matches (team_a, team_b, group_name, url, submitted_by, status, channel_id, submitter_id)
            VALUES (%s, %s, %s, %s, %s, 'new', %s, %s)
        """, (team_a, team_b, group, tracker_link, str(interaction.user), str(interaction.channel_id), str(interaction.user.id)))
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
    tracker_link="Tracker.gg Profile URL",
    discord_handle="Discord handle of the player"
)
async def player(interaction: discord.Interaction, riot_id: str, rank: str, tracker_link: str, discord_handle: str):
    await interaction.response.defer()
    
    conn = get_conn()
    if not conn:
        await interaction.followup.send("❌ Error: Database connection failed.")
        return

    try:
        clean_rank = rank.strip()
        cursor = conn.cursor()
        
        # Insert into pending_players
        # Use provided discord_handle and store metadata for notifications
        cursor.execute("""
            INSERT INTO pending_players (riot_id, rank, tracker_link, submitted_by, status, discord_handle, channel_id, submitter_id)
            VALUES (%s, %s, %s, %s, 'new', %s, %s, %s)
        """, (riot_id, clean_rank, tracker_link, str(interaction.user), discord_handle, str(interaction.channel_id), str(interaction.user.id)))
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
        msg += f"{i:>2}    {name[:26]:<26}  {row.played:>2} {row.wins:>2} {row.losses:>2} {row.points:>3} {row.pd:>3}\n"
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
                   p.uuid,
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
            GROUP BY p.id, p.name, p.riot_id, p.uuid, t.tag
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
        for i, (name, riot_id, uuid, team, games, avg_acs, k, d) in enumerate(rows, start=1):
            d_val = d if d and d > 0 else 1
            kd = k / d_val if k else 0
            tag = f" ({riot_id})" if riot_id else ""
            display_name = f"<@{uuid}>" if uuid else f"{name}{tag}"
            embed.add_field(
                name=f"#{i} {name}", 
                value=f"User: {display_name}\nTeam: `{team or 'FA'}` | Games: `{games}` | ACS: `{round(avg_acs, 1)}` | KD: `{round(kd, 2)}`", 
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

@bot.tree.command(name="player_info", description="Look up a player's detailed stats and history")
@discord.app_commands.describe(name="Player name, Riot ID or @mention")
async def player_info(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    
    conn = get_conn()
    if not conn:
        await interaction.followup.send("❌ DB Error.")
        return
    
    try:
        # Check if input is a mention <@123...>
        mention_match = re.match(r"^<@!?(\d+)>$", name.strip())

        cursor = conn.cursor()
        # 1. Find player and team info
        if mention_match:
            uuid = mention_match.group(1)
            cursor.execute("""
                SELECT p.id, p.name, p.riot_id, p.rank, p.uuid, t.name as team_name, t.tag as team_tag, t.logo_path
                FROM players p
                LEFT JOIN teams t ON p.default_team_id = t.id
                WHERE p.uuid = %s
                LIMIT 1
            """, (uuid,))
        else:
            cursor.execute("""
                SELECT p.id, p.name, p.riot_id, p.rank, p.uuid, t.name as team_name, t.tag as team_tag, t.logo_path
                FROM players p
                LEFT JOIN teams t ON p.default_team_id = t.id
                WHERE p.name ILIKE %s OR p.riot_id ILIKE %s
                LIMIT 1
            """, (name, name))
        row = cursor.fetchone()
        
        if not row:
            await interaction.followup.send(f"❌ Player `{name}` not found.")
            return
            
        pid, p_name, r_id, p_rank, p_uuid, t_name, t_tag, t_logo = row
        
        # ... (Stats queries remain same) ...
        # 2. Get Aggregate Stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_maps,
                AVG(msm.acs) as avg_acs,
                SUM(msm.kills) as total_k,
                SUM(msm.deaths) as total_d,
                SUM(msm.assists) as total_a
            FROM match_stats_map msm
            JOIN matches m ON msm.match_id = m.id
            WHERE msm.player_id = %s AND m.status = 'completed'
        """, (pid,))
        agg = cursor.fetchone()
        
        maps_played = agg[0] or 0
        avg_acs = agg[1] or 0
        total_k = agg[2] or 0
        total_d = agg[3] or 0
        total_a = agg[4] or 0
        kd = total_k / (total_d if total_d > 0 else 1)
        
        # 3. Get Top 3 Agents
        cursor.execute("""
            SELECT agent, COUNT(*) as count, AVG(acs) as agent_acs
            FROM match_stats_map msm
            JOIN matches m ON msm.match_id = m.id
            WHERE msm.player_id = %s AND m.status = 'completed' AND agent IS NOT NULL
            GROUP BY agent
            ORDER BY count DESC, agent_acs DESC
            LIMIT 3
        """, (pid,))
        agents = cursor.fetchall()
        
        # 4. Get Recent 3 Matches
        cursor.execute("""
            SELECT m.id, m.week, t1.tag, t2.tag, msm.acs, msm.kills, msm.deaths, msm.assists, msm.agent
            FROM match_stats_map msm
            JOIN matches m ON msm.match_id = m.id
            JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            WHERE msm.player_id = %s AND m.status = 'completed'
            ORDER BY m.id DESC
            LIMIT 3
        """, (pid,))
        history = cursor.fetchall()

        # Build Embed
        embed = discord.Embed(title=f"👤 {p_name}", color=discord.Color.green())
        desc = ""
        if t_name:
            desc += f"**Team:** {t_name} [{t_tag}]"
        else:
            desc += "*Free Agent*"
        
        if p_uuid:
            desc += f"\n**User:** <@{p_uuid}>"
        
        embed.description = desc

        # Header Info
        embed.add_field(name="Riot ID", value=f"`{r_id or 'N/A'}`", inline=True)
        embed.add_field(name="Rank", value=f"`{p_rank or 'Unranked'}`", inline=True)
        embed.add_field(name="Maps", value=f"`{maps_played}`", inline=True)

        # Main Stats
        stats_val = (
            f"**AVG ACS:** `{round(avg_acs, 1)}`\n"
            f"**K/D Ratio:** `{round(kd, 2)}`\n"
            f"**Assists:** `{total_a}`"
        )
        embed.add_field(name="📊 Lifetime Stats", value=stats_val, inline=False)

        # Agent Pool
        if agents:
            agent_list = []
            for a_name, a_count, a_acs in agents:
                agent_list.append(f"• **{a_name}**: {a_count} maps ({round(a_acs)} ACS)")
            embed.add_field(name="🎭 Top Agents", value="\n".join(agent_list), inline=True)
        
        # Recent History
        if history:
            hist_list = []
            for mid, week, tag1, tag2, h_acs, h_k, h_d, h_a, h_agent in history:
                hist_list.append(f"W{week}: `{tag1}` vs `{tag2}` | **{h_acs}** ACS as {h_agent} ({h_k}/{h_d}/{h_a})")
            embed.add_field(name="🎮 Recent Matches", value="\n".join(hist_list), inline=False)

        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

@bot.tree.command(name="team_info", description="Look up a team's roster, map stats, and history")
@discord.app_commands.describe(name="Team name or Tag")
async def team_info(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    
    conn = get_conn()
    if not conn:
        await interaction.followup.send("❌ DB Error.")
        return
    
    try:
        cursor = conn.cursor()
        # 1. Find team
        cursor.execute("""
            SELECT id, name, tag, group_name, logo_path
            FROM teams
            WHERE name ILIKE %s OR tag ILIKE %s
            LIMIT 1
        """, (name, name))
        row = cursor.fetchone()
        
        if not row:
            await interaction.followup.send(f"❌ Team `{name}` not found.")
            return
            
        tid, t_name, t_tag, t_group, t_logo = row
        
        # 2. Get Roster
        cursor.execute("""
            SELECT name, riot_id, rank, uuid
            FROM players
            WHERE default_team_id = %s
            ORDER BY name ASC
        """, (tid,))
        roster = cursor.fetchall()
        
        # ... (Map stats and history queries remain same) ...
        # 3. Get Map Winrates
        cursor.execute("""
            SELECT map_name, 
                   COUNT(*) as played,
                   SUM(CASE WHEN winner_id = %s THEN 1 ELSE 0 END) as wins
            FROM match_maps
            WHERE (match_id IN (SELECT id FROM matches WHERE team1_id = %s OR team2_id = %s))
              AND (winner_id IS NOT NULL)
            GROUP BY map_name
            ORDER BY played DESC
        """, (tid, tid, tid))
        maps = cursor.fetchall()
        
        # 4. Get Team Avg ACS
        cursor.execute("""
            SELECT AVG(acs)
            FROM match_stats_map
            WHERE team_id = %s
        """, (tid,))
        avg_acs = cursor.fetchone()[0] or 0
        
        # 5. Get Recent 3 Match Results
        cursor.execute("""
            SELECT m.id, m.week, t1.tag, t2.tag, m.score_t1, m.score_t2, m.winner_id
            FROM matches m
            JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            WHERE (m.team1_id = %s OR m.team2_id = %s) AND m.status = 'completed'
            ORDER BY m.id DESC
            LIMIT 3
        """, (tid, tid))
        history = cursor.fetchall()

        # Build Embed
        embed = discord.Embed(title=f"🛡️ Team: {t_name}", color=discord.Color.blue())
        embed.description = f"**Tag:** `{t_tag}` | **Group:** `{t_group}`"

        # Roster
        if roster:
            roster_list = []
            for pname, rid, prank, puuid in roster:
                p_disp = f"<@{puuid}>" if puuid else pname
                roster_list.append(f"• {p_disp} (`{rid or '?'}`)")
            embed.add_field(name="👥 Roster", value="\n".join(roster_list), inline=False)
        else:
            embed.add_field(name="👥 Roster", value="*No players found*", inline=False)

        # Map Stats
        if maps:
            map_list = []
            for mname, mplayed, mwins in maps:
                wr = (mwins / mplayed) * 100
                map_list.append(f"• **{mname}**: {round(wr)}% ({mwins}-{mplayed - mwins})")
            embed.add_field(name="🗺️ Map Records", value="\n".join(map_list), inline=True)
        
        embed.add_field(name="📊 Team Avg ACS", value=f"`{round(avg_acs)}`", inline=True)

        # Recent History
        if history:
            hist_list = []
            for mid, week, tag1, tag2, s1, s2, wid in history:
                result = "W" if wid == tid else ("L" if wid is not None else "D")
                hist_list.append(f"W{week}: `{tag1}` {s1}-{s2} `{tag2}` (**{result}**)")
            embed.add_field(name="🏁 Recent Results", value="\n".join(hist_list), inline=False)

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

# --- NOTIFICATION ENGINE ---

@tasks.loop(seconds=60)
async def notification_loop():
    """
    Background task to poll for new match results and player registration updates.
    """
    conn = get_conn()
    if not conn: return
    
    try:
        cursor = conn.cursor()
        
        # 1. CHECK MATCH REPORTS
        cursor.execute("""
            SELECT m.id, m.team1_id, m.team2_id, m.score_t1, m.score_t2, m.winner_id, m.channel_id, 
                   t1.name as t1_name, t2.name as t2_name
            FROM matches m
            JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            WHERE m.status = 'completed' AND m.reported = false
        """)
        matches_to_report = cursor.fetchall()
        
        for m_id, t1_id, t2_id, s1, s2, wid, chan_id, t1_name, t2_name in matches_to_report:
            channel = None
            if chan_id:
                try: channel = bot.get_channel(int(chan_id)) or await bot.fetch_channel(int(chan_id))
                except: pass
            
            if not channel: continue # Skip if no channel
            
            # Match Summary Embed
            winner_name = t1_name if wid == t1_id else (t2_name if wid == t2_id else "Draw")
            embed = discord.Embed(title=f"🏆 Match Result: {t1_name} vs {t2_name}", color=discord.Color.gold())
            embed.add_field(name="Score", value=f"**{t1_name} {s1} - {s2} {t2_name}**", inline=False)
            embed.add_field(name="Winner", value=f"⭐ {winner_name}", inline=True)
            
            # Add Map details if available
            cursor.execute("SELECT map_name, team1_rounds, team2_rounds FROM match_maps WHERE match_id = %s ORDER BY map_index", (m_id,))
            maps = cursor.fetchall()
            if maps:
                map_str = "\n".join([f"• {mn}: {r1}-{r2}" for mn, r1, r2 in maps])
                embed.add_field(name="Maps", value=map_str, inline=False)
            
            await channel.send(embed=embed)
            
            # Simplified scoreboard reporting (Top performers)
            cursor.execute("""
                SELECT p.name, s.acs, s.kills, s.deaths, s.assists, t.name as team_name
                FROM match_stats_map s
                JOIN players p ON s.player_id = p.id
                JOIN teams t ON s.team_id = t.id
                WHERE s.match_id = %s
                ORDER BY t.id
            """, (m_id,))#s.acs DESC LIMIT 5
            top_players = cursor.fetchall()
            if top_players:
                sb_embed = discord.Embed(title="📊 Match Performances", color=discord.Color.blue())
                rows = []
                for name, acs, k, d, a, tname in top_players:
                    rows.append(f"**{name}** ({tname}): {acs} ACS | {k}/{d}/{a}")
                sb_embed.description = "\n".join(rows)
                await channel.send(embed=sb_embed)
            
            # Mark as reported
            cursor.execute("UPDATE matches SET reported = true WHERE id = %s", (m_id,))
            conn.commit()

        # 2. CHECK PLAYER NOTIFICATIONS
        cursor.execute("""
            SELECT id, riot_id, discord_handle, status, channel_id, submitter_id
            FROM pending_players
            WHERE status IN ('accepted', 'rejected') AND notified = false
        """)
        players_to_notify = cursor.fetchall()
        
        for p_id, rid, handle, status, chan_id, sub_id in players_to_notify:
            # Channel Notification
            channel = None
            if chan_id:
                try: channel = bot.get_channel(int(chan_id)) or await bot.fetch_channel(int(chan_id))
                except: pass
            
            msg = f"✅ Registration for `{rid}` (`{handle}`) has been **approved**!" if status == 'accepted' else f"❌ Registration for `{rid}` (`{handle}`) has been **rejected**."
            if channel:
                await channel.send(msg)
            
            # DM Submitter
            if sub_id:
                try:
                    user = bot.get_user(int(sub_id)) or await bot.fetch_user(int(sub_id))
                    if user:
                        await user.send(f"Hello Captain! {msg}")
                except: pass
            
            # Mark as notified
            cursor.execute("UPDATE pending_players SET notified = true WHERE id = %s", (p_id,))
            conn.commit()
            
    except Exception as e:
        print(f"Notification loop error: {e}")
    finally:
        conn.close()

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')
    if not notification_loop.is_running():
        notification_loop.start()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not set")
    else:
        bot.run(DISCORD_TOKEN)
