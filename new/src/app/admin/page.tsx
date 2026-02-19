"use client";
export const dynamic = 'force-dynamic';

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import {
    getPendingRequests,
    getAllMatches,
    updatePendingRequestStatus,
    getTeamsBasic,
    getPlayoffMatches,
    updateMatch,
    saveMapResults,
    parseTrackerJson
} from "@/lib/data";
import { clearMatchDetails } from "@/lib/data";
import { supabase } from "@/lib/supabase";
import type { PendingMatch, PendingPlayer, MatchEntry } from "@/lib/data";
import type { PlayoffMatch } from "@/lib/data";

export default function AdminPage() {
    const [activeTab, setActiveTab] = useState<'pending' | 'schedule' | 'playoffs' | 'editor' | 'players'>('pending');
    const [pending, setPending] = useState<{ matches: PendingMatch[], players: PendingPlayer[] }>({ matches: [], players: [] });
    const [matches, setMatches] = useState<MatchEntry[]>([]);
    const [playoffMatches, setPlayoffMatches] = useState<PlayoffMatch[]>([]);
    const [teams, setTeams] = useState<{ id: number, name: string, tag: string, group_name: string }[]>([]);
    const [loading, setLoading] = useState(true);
    const [authorized, setAuthorized] = useState(false);
    const [authLoading, setAuthLoading] = useState(true);
    const [form, setForm] = useState({ username: "", password: "", token: "" });
    const [authError, setAuthError] = useState<string | null>(null);

    useEffect(() => {
        fetch("/api/admin/me")
            .then(r => r.json())
            .then(d => {
                setAuthorized(Boolean(d.authorized));
                setAuthLoading(false);
            })
            .catch(() => setAuthLoading(false));
    }, []);

    useEffect(() => {
        const loadData = async () => {
            if (!authorized) {
                setLoading(false);
                return;
            }
            setLoading(true);
            const [p, m, t, pm] = await Promise.all([
                getPendingRequests(),
                getAllMatches(),
                getTeamsBasic(),
                getPlayoffMatches()
            ]);
            setPending(p);
            setMatches(m);
            setTeams(t);
            setPlayoffMatches(pm);
            setLoading(false);
        };
        loadData();
    }, [authorized]);

    const handleUpdatePending = async (type: 'match' | 'player', id: number, status: string) => {
        const success = await updatePendingRequestStatus(type, id, status);
        if (success) {
            setPending(prev => ({
                ...prev,
                [type === 'match' ? 'matches' : 'players']: prev[type === 'match' ? 'matches' : 'players'].filter(p => p.id !== id)
            }));
        }
    };

    if (!authorized) {
        return (
            <div className="flex flex-col min-h-screen bg-background text-foreground">
                <Navbar />
                <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-32">
                    <section className="glass p-12">
                        <h1 className="font-display text-3xl font-black italic text-val-red uppercase tracking-tighter mb-6 text-center">
                            Admin Login
                        </h1>
                        <div className="max-w-md mx-auto space-y-4">
                            <div>
                                <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Username</label>
                                <input
                                    value={form.username}
                                    onChange={e => setForm({ ...form, username: e.target.value })}
                                    className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm focus:border-val-blue outline-none transition-colors"
                                />
                            </div>
                            <div>
                                <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Password</label>
                                <input
                                    type="password"
                                    value={form.password}
                                    onChange={e => setForm({ ...form, password: e.target.value })}
                                    className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm focus:border-val-blue outline-none transition-colors"
                                />
                            </div>
                            <div>
                                <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Token</label>
                                <input
                                    value={form.token}
                                    onChange={e => setForm({ ...form, token: e.target.value })}
                                    className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm focus:border-val-blue outline-none transition-colors"
                                />
                            </div>
                            {authError && (
                                <div className="text-val-red text-xs font-bold uppercase tracking-widest">{authError}</div>
                            )}
                            <button
                                disabled={authLoading}
                                onClick={async () => {
                                    setAuthError(null);
                                    const res = await fetch("/api/admin/login", {
                                        method: "POST",
                                        headers: { "Content-Type": "application/json" },
                                        body: JSON.stringify(form)
                                    });
                                    if (res.ok) {
                                        setAuthorized(true);
                                    } else {
                                        setAuthError("Invalid credentials");
                                    }
                                }}
                                className="w-full py-3 bg-val-blue text-white font-display font-black uppercase tracking-widest text-xs rounded shadow-[0_0_20px_rgba(63,209,255,0.3)]"
                            >
                                {authLoading ? "Checking..." : "Login"}
                            </button>
                            <div className="text-[10px] font-black uppercase tracking-widest text-foreground/40 text-center">
                                Credentials are configured via environment variables
                            </div>
                        </div>
                    </section>
                </main>
            </div>
        );
    }

    return (
        <div className="flex flex-col min-h-screen bg-background text-foreground">
            <Navbar />

            <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-32">
                <header className="mb-12 flex items-center justify-between">
                    <div>
                        <h1 className="font-display text-4xl md:text-5xl font-black italic text-val-red uppercase tracking-tighter mb-2">
                            Admin Dashboard
                        </h1>
                        <p className="text-foreground/40 font-bold uppercase tracking-widest text-xs">
                            Control Center & Tournament Management
                        </p>
                    </div>

                    <div className="flex glass p-1 rounded-lg">
                        {(['pending', 'schedule', 'playoffs', 'editor', 'players'] as const).map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`px-6 py-2 rounded-md font-display text-xs font-black uppercase tracking-widest transition-all ${activeTab === tab
                                    ? 'bg-val-red text-white shadow-[0_0_15px_rgba(255,70,85,0.4)]'
                                    : 'text-foreground/40 hover:text-foreground/80'
                                    }`}
                            >
                                {tab}
                                {tab === 'pending' && (pending.matches.length + pending.players.length > 0) && (
                                    <span className="ml-2 px-1.5 py-0.5 bg-white text-val-red rounded-full text-[10px]">
                                        {pending.matches.length + pending.players.length}
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>
                </header>
                <section className="grid md:grid-cols-3 gap-6 mb-8">
                    <div className="custom-card glass p-6 text-center rounded">
                        <h4 className="text-val-blue mb-1">LIVE USERS</h4>
                        <div className="font-display text-3xl">{/* Placeholder: use global stats livePlayers */}</div>
                        <div className="text-foreground/40 text-xs">Currently on website</div>
                    </div>
                    <div className="custom-card glass p-6 text-center rounded">
                        <h4 className="text-green-400 mb-1">SYSTEM STATUS</h4>
                        <div className="font-display text-xl">ONLINE</div>
                        <div className="text-foreground/40 text-xs">All systems operational</div>
                    </div>
                    <div className="custom-card glass p-6 text-center rounded">
                        <h4 className="text-val-red mb-1">SESSION ROLE</h4>
                        <div className="font-display text-xl">ADMIN</div>
                        <div className="text-foreground/40 text-xs">Authorized Session</div>
                    </div>
                </section>

                {loading ? (
                    <div className="glass p-20 flex flex-col items-center justify-center animate-pulse">
                        <div className="w-12 h-12 border-4 border-val-red border-t-transparent rounded-full animate-spin mb-4" />
                        <span className="font-display text-val-red font-black uppercase tracking-widest">Loading Dashboard Data...</span>
                    </div>
                ) : (
                    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                        {activeTab === 'pending' && (
                            <section className="grid md:grid-cols-2 gap-8">
                                {/* Pending Matches */}
                                <div className="space-y-4">
                                    <h2 className="font-display text-xl font-black text-val-blue uppercase italic flex items-center gap-4">
                                        🤖 Bot Match Requests
                                        <div className="h-px flex-1 bg-white/5" />
                                    </h2>
                                    <div className="grid gap-3">
                                        {pending.matches.length > 0 ? pending.matches.map((m) => (
                                            <div key={m.id} className="glass p-4 group hover:border-val-red/30 transition-all">
                                                <div className="flex justify-between items-start mb-3">
                                                    <div>
                                                        <div className="font-display text-lg font-black uppercase tracking-tight">
                                                            {m.team_a} vs {m.team_b}
                                                        </div>
                                                        <div className="text-[10px] font-bold text-foreground/40 uppercase tracking-widest">
                                                            {m.group_name} • Submitted by {m.submitted_by}
                                                        </div>
                                                    </div>
                                                    <div className="flex gap-2">
                                                        <button
                                                            onClick={() => {
                                                                const cand = matches.filter(mm => mm.status === 'scheduled').find(mm => {
                                                                    const nm = (s: string) => s?.trim().toLowerCase();
                                                                    return (nm(mm.team1.name) === nm(m.team_a) && nm(mm.team2.name) === nm(m.team_b)) ||
                                                                           (nm(mm.team1.name) === nm(m.team_b) && nm(mm.team2.name) === nm(m.team_a));
                                                                });
                                                                if (cand) {
                                                            setActiveTab('editor');
                                                            // inform editor via localStorage
                                                                    try {
                                                                        window.localStorage.setItem('auto_selected_match_id', String(cand.id));
                                                                        window.localStorage.setItem('auto_selected_match_week', String(cand.week));
                                                                        window.localStorage.setItem('pending_match_db_id', String(m.id));
                                                                if (m.url) window.localStorage.setItem('auto_selected_match_url', m.url);
                                                                    } catch {}
                                                                } else {
                                                                    setActiveTab('editor');
                                                                }
                                                            }}
                                                            className="px-3 py-1 bg-white/10 hover:bg-white/20 text-foreground text-[10px] font-black uppercase tracking-widest rounded transition-all"
                                                        >
                                                            Process
                                                        </button>
                                                        <button
                                                            onClick={() => handleUpdatePending('match', m.id, 'accepted')}
                                                            className="px-3 py-1 bg-val-blue/20 hover:bg-val-blue text-val-blue hover:text-white text-[10px] font-black uppercase tracking-widest rounded transition-all"
                                                        >
                                                            Accept
                                                        </button>
                                                        <button
                                                            onClick={() => handleUpdatePending('match', m.id, 'rejected')}
                                                            className="px-3 py-1 bg-val-red/20 hover:bg-val-red text-val-red hover:text-white text-[10px] font-black uppercase tracking-widest rounded transition-all"
                                                        >
                                                            Reject
                                                        </button>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-4 text-[10px] text-foreground/30 font-medium">
                                                    <a href={m.url} target="_blank" className="hover:text-val-blue underline truncate">Tracker.gg Link</a>
                                                    <span>{new Date(m.timestamp).toLocaleString()}</span>
                                                </div>
                                            </div>
                                        )) : (
                                            <div className="glass p-8 text-center text-foreground/30 text-xs font-bold uppercase tracking-widest">
                                                No pending match requests
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Pending Players */}
                                <div className="space-y-4">
                                    <h2 className="font-display text-xl font-black text-val-blue uppercase italic flex items-center gap-4">
                                        🤖 Bot Player Requests
                                        <div className="h-px flex-1 bg-white/5" />
                                    </h2>
                                    <div className="grid gap-3">
                                        {pending.players.length > 0 ? pending.players.map((p) => (
                                            <div key={p.id} className="glass p-4 group hover:border-val-red/30 transition-all">
                                                <div className="flex justify-between items-start mb-3">
                                                    <div>
                                                        <div className="font-display text-lg font-black uppercase tracking-tight">
                                                            {p.riot_id}
                                                        </div>
                                                        <div className="text-[10px] font-bold text-foreground/40 uppercase tracking-widest">
                                                            Rank: {p.rank} • Discord: {p.discord_handle}
                                                        </div>
                                                    </div>
                                                    <div className="flex gap-2">
                                                        <button
                                                            onClick={() => handleUpdatePending('player', p.id, 'accepted')}
                                                            className="px-3 py-1 bg-val-blue/20 hover:bg-val-blue text-val-blue hover:text-white text-[10px] font-black uppercase tracking-widest rounded transition-all"
                                                        >
                                                            Accept
                                                        </button>
                                                        <button
                                                            onClick={() => handleUpdatePending('player', p.id, 'rejected')}
                                                            className="px-3 py-1 bg-val-red/20 hover:bg-val-red text-val-red hover:text-white text-[10px] font-black uppercase tracking-widest rounded transition-all"
                                                        >
                                                            Reject
                                                        </button>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-4 text-[10px] text-foreground/30 font-medium">
                                                    <a href={p.tracker_link} target="_blank" className="hover:text-val-blue underline truncate">Tracker.gg Profile</a>
                                                    <span>{new Date(p.timestamp).toLocaleString()}</span>
                                                </div>
                                            </div>
                                        )) : (
                                            <div className="glass p-8 text-center text-foreground/30 text-xs font-bold uppercase tracking-widest">
                                                No pending player requests
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </section>
                        )}

                        {activeTab === 'schedule' && (
                            <ScheduleManager teams={teams} onUpdate={() => {
                                getAllMatches().then(setMatches);
                            }} />
                        )}

                        {activeTab === 'playoffs' && (
                            <PlayoffBracketEditor
                                teams={teams}
                                matches={playoffMatches}
                                onUpdate={async () => {
                                    const pm = await getPlayoffMatches();
                                    setPlayoffMatches(pm);
                                }}
                            />
                        )}

                        {activeTab === 'editor' && (
                            <ScoreMapEditor />
                        )}
                        {activeTab === 'players' && (
                            <PlayersAdmin />
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}
/**
 * Schedule Manager Component
 */
function ScheduleManager({
    teams,
    onUpdate
}: {
    teams: { id: number, name: string, tag: string, group_name: string }[],
    onUpdate: () => void
}) {
    const [bulkText, setBulkText] = useState("");
    const [week, setWeek] = useState(1);
    const [group, setGroup] = useState("");
    const [t1Id, setT1Id] = useState<number>(0);
    const [t2Id, setT2Id] = useState<number>(0);
    const [processing, setProcessing] = useState(false);

    const handleBulkAdd = async () => {
        if (!bulkText.trim()) return;
        setProcessing(true);
        try {
            // Simple parser: Each line is "Team A vs Team B"
            const lines = bulkText.split('\n').filter(l => l.includes('vs'));
            const matchesToCreate = lines.map(line => {
                const [ta, tb] = line.split(/vs/i).map(s => s.trim());
                const teamA = teams.find(t => t.name.toLowerCase() === ta.toLowerCase() || t.tag.toLowerCase() === ta.toLowerCase());
                const teamB = teams.find(t => t.name.toLowerCase() === tb.toLowerCase() || t.tag.toLowerCase() === tb.toLowerCase());

                if (!teamA || !teamB) return null;

                return {
                    week,
                    group_name: group || teamA.group_name,
                    team1_id: teamA.id,
                    team2_id: teamB.id,
                    status: 'scheduled' as const,
                    format: 'BO1' as const,
                    maps_played: 0,
                    winner_id: null
                };
            }).filter(Boolean) as any[];

            if (matchesToCreate.length > 0) {
                const { bulkCreateMatches } = await import("@/lib/data");
                await bulkCreateMatches(matchesToCreate);
                setBulkText("");
                alert(`Successfully added ${matchesToCreate.length} matches!`);
                onUpdate();
            } else {
                alert("No valid matches found in text. Format should be 'Team A vs Team B' per line.");
            }
        } catch (err) {
            console.error(err);
        } finally {
            setProcessing(false);
        }
    };

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            <div className="grid md:grid-cols-2 gap-8">
                {/* Single Match Add */}
                <div className="glass p-8 space-y-6">
                    <h3 className="font-display text-xl font-black text-val-red uppercase italic">Quick Add Match</h3>
                    <div className="grid gap-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Week</label>
                                <input
                                    type="number"
                                    value={week}
                                    onChange={e => setWeek(parseInt(e.target.value))}
                                    className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm focus:border-val-red outline-none transition-colors"
                                />
                            </div>
                            <div>
                                <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Group (Optional)</label>
                                <input
                                    type="text"
                                    placeholder="e.g. ALPHA"
                                    value={group}
                                    onChange={e => setGroup(e.target.value.toUpperCase())}
                                    className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm focus:border-val-red outline-none transition-colors"
                                />
                            </div>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Team 1</label>
                                <select
                                    value={t1Id}
                                    onChange={e => setT1Id(parseInt(e.target.value))}
                                    className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm focus:border-val-red outline-none transition-colors appearance-none"
                                >
                                    <option value={0}>Select Team</option>
                                    {teams.map(t => <option key={t.id} value={t.id}>{t.name} [{t.tag}]</option>)}
                                </select>
                            </div>
                            <div className="text-center font-display font-black text-val-red/20 italic">VS</div>
                            <div>
                                <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Team 2</label>
                                <select
                                    value={t2Id}
                                    onChange={e => setT2Id(parseInt(e.target.value))}
                                    className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm focus:border-val-red outline-none transition-colors appearance-none"
                                >
                                    <option value={0}>Select Team</option>
                                    {teams.map(t => <option key={t.id} value={t.id}>{t.name} [{t.tag}]</option>)}
                                </select>
                            </div>
                        </div>

                        <button
                            disabled={!t1Id || !t2Id || processing}
                            onClick={async () => {
                                setProcessing(true);
                                const { createMatch } = await import("@/lib/data");
                                await createMatch({
                                    week,
                                    group_name: group || teams.find(t => t.id === t1Id)?.group_name || "N/A",
                                    team1_id: t1Id,
                                    team2_id: t2Id,
                                    status: 'scheduled',
                                    format: 'BO1',
                                    maps_played: 0,
                                    winner_id: null
                                });
                                setProcessing(false);
                                onUpdate();
                            }}
                            className="w-full py-3 bg-val-red text-white font-display font-black uppercase tracking-widest text-xs rounded shadow-[0_0_20px_rgba(255,70,85,0.3)] hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 disabled:scale-100"
                        >
                            {processing ? "Adding..." : "Add to Schedule"}
                        </button>
                    </div>
                </div>

                {/* Bulk Add */}
                <div className="glass p-8 space-y-6">
                    <div className="flex justify-between items-center">
                        <h3 className="font-display text-xl font-black text-val-blue uppercase italic">Bulk Add Matches</h3>
                        <span className="text-[10px] font-black text-foreground/20 uppercase tracking-widest">Parser Mode</span>
                    </div>
                    <p className="text-[10px] text-foreground/40 font-bold uppercase tracking-widest leading-relaxed">
                        Paste matches list below. Format: <span className="text-val-blue">TEAM Name vs OTHER Team</span>. One match per line.
                    </p>
                    <textarea
                        value={bulkText}
                        onChange={e => setBulkText(e.target.value)}
                        placeholder="Team A vs Team B&#10;Team C vs Team D"
                        className="w-full h-48 bg-white/5 border border-white/10 rounded p-4 text-sm font-mono focus:border-val-blue outline-none transition-colors resize-none"
                    />
                    <button
                        disabled={!bulkText.trim() || processing}
                        onClick={handleBulkAdd}
                        className="w-full py-3 bg-val-blue text-white font-display font-black uppercase tracking-widest text-xs rounded shadow-[0_0_20px_rgba(63,209,255,0.3)] hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 disabled:scale-100"
                    >
                        {processing ? "Parsing & Saving..." : "Bulk Save Schedule"}
                    </button>
                </div>
            </div>
        </div>
    );
}

/**
 * Playoff Bracket Editor Component
 */
function PlayoffBracketEditor({
    teams,
    matches,
    onUpdate
}: {
    teams: { id: number, name: string, tag: string, group_name: string }[],
    matches: PlayoffMatch[],
    onUpdate: () => void
}) {
    const [saving, setSaving] = useState(false);
    const [proposals, setProposals] = useState<Array<any>>([]);
    const [creatingR1, setCreatingR1] = useState(false);
    const [creatingR2, setCreatingR2] = useState(false);
    const [round2Byes, setRound2Byes] = useState<Array<number | null>>(Array.from({ length: 8 }, () => null));
    const [byeOptions, setByeOptions] = useState<Array<{ id: number, name: string, tag: string, group_name: string }>>([]);
    const [autoAdvance, setAutoAdvance] = useState(true);
    useEffect(() => {
        import('@/lib/data').then(({ getStandings }) => {
            getStandings().then(gs => {
                const opts: Array<{ id: number, name: string, tag: string, group_name: string }> = [];
                Array.from(gs.entries()).forEach(([group, rows]) => {
                    rows.slice(0, 2).forEach(r => {
                        opts.push({ id: r.id, name: r.name, tag: r.tag || '', group_name: group });
                    });
                });
                setByeOptions(opts);
            });
        });
        try {
            const av = window.localStorage.getItem('playoffs_auto_advance');
            if (av) setAutoAdvance(av === '1');
        } catch {}
    }, []);

    useEffect(() => {
        if (!autoAdvance) return;
        const id = setInterval(async () => {
            try {
                const { computeBracketAdvancements, applyBracketAdvancements } = await import('@/lib/data');
                const acts = await computeBracketAdvancements();
                if (acts.length > 0) {
                    await applyBracketAdvancements(acts);
                    onUpdate();
                }
            } catch {}
        }, 8000);
        return () => clearInterval(id);
    }, [autoAdvance, matches.length]);

    const rounds = [
        { id: 1, name: "Round of 24", slots: 8 },
        { id: 2, name: "Round of 16", slots: 8 },
        { id: 3, name: "Quarter-finals", slots: 4 },
        { id: 4, name: "Semi-finals", slots: 2 },
        { id: 5, name: "Grand Final", slots: 1 }
    ];

    const getMatchAt = (roundId: number, pos: number) =>
        matches.find(m => m.playoff_round === roundId && m.bracket_pos === pos);

    const handleAssign = async (matchId: number, which: 'team1_id' | 'team2_id', teamId: number) => {
        setSaving(true);
        try {
            await updateMatch(matchId, { [which]: teamId });
            onUpdate();
        } finally {
            setSaving(false);
        }
    };

    return (
        <section className="space-y-6">
            <h2 className="font-display text-xl font-black text-val-blue uppercase italic">
                Playoff Bracket Editor
            </h2>
            <div className="glass p-4 rounded border border-white/5">
                <div className="grid md:grid-cols-2 gap-4">
                    <div className="space-y-3">
                        <div className="text-[10px] font-black uppercase tracking-widest text-foreground/40">Round 1 (8 matches)</div>
                        <button
                            onClick={async () => {
                                setCreatingR1(true);
                                try {
                                    const existing = matches.filter(m => m.playoff_round === 1).length;
                                    const needed = Math.max(0, 8 - existing);
                                    if (needed > 0) {
                                        const payload = [];
                                        for (let i = existing + 1; i <= 8; i++) {
                                            payload.push({
                                                week: 0,
                                                group_name: 'Playoffs',
                                                team1_id: null,
                                                team2_id: null,
                                                status: 'scheduled',
                                                format: 'BO3',
                                                maps_played: 0,
                                                match_type: 'playoff',
                                                playoff_round: 1,
                                                bracket_pos: i,
                                                bracket_label: `R1 #${i}`
                                            });
                                        }
                                        await fetch('/api/admin/matches/bulk', {
                                            method: 'POST',
                                            headers: { 'Content-Type': 'application/json' },
                                            body: JSON.stringify(payload)
                                        } as any);
                                    }
                                    onUpdate();
                                } finally {
                                    setCreatingR1(false);
                                }
                            }}
                            className="px-4 py-2 bg-val-blue text-white rounded text-xs font-black uppercase tracking-widest disabled:opacity-50"
                            disabled={creatingR1}
                        >
                            {creatingR1 ? "Creating..." : "Create Round 1 Matches"}
                        </button>
                    </div>
                    <div className="space-y-3">
                        <div className="text-[10px] font-black uppercase tracking-widest text-foreground/40">Round 2 BYE Seeds (8 matches)</div>
                        <div className="grid grid-cols-2 gap-2">
                            {round2Byes.map((val, idx) => (
                                <select
                                    key={idx}
                                    value={val || 0}
                                    onChange={e => {
                                        const next = [...round2Byes]; next[idx] = parseInt(e.target.value) || null; setRound2Byes(next);
                                    }}
                                    className="bg-white/5 border border-white/10 rounded p-2 text-xs"
                                >
                                    <option value={0}>BYE Seed #{idx + 1}</option>
                                    {byeOptions.map(t => <option key={t.id} value={t.id}>{t.name} [{t.tag}] • {t.group_name}</option>)}
                                </select>
                            ))}
                        </div>
                        <button
                            onClick={async () => {
                                setCreatingR2(true);
                                try {
                                    for (let i = 1; i <= 8; i++) {
                                        const byeTeam = round2Byes[i - 1];
                                        const { data: existing } = await supabase
                                            .from('matches')
                                            .select('*')
                                            .eq('match_type', 'playoff')
                                            .eq('playoff_round', 2)
                                            .eq('bracket_pos', i)
                                            .limit(1);
                                        if (existing && existing.length > 0) {
                                            // update team1 with BYE if provided
                                            if (byeTeam) {
                                                await updateMatch(existing[0].id, { team1_id: byeTeam });
                                            }
                                        } else {
                                            await fetch('/api/admin/matches/create', {
                                                method: 'POST',
                                                headers: { 'Content-Type': 'application/json' },
                                                body: JSON.stringify({
                                                    week: 0,
                                                    group_name: 'Playoffs',
                                                    team1_id: byeTeam || null,
                                                    team2_id: null,
                                                    status: 'scheduled',
                                                    format: 'BO3',
                                                    maps_played: 0,
                                                    match_type: 'playoff',
                                                    playoff_round: 2,
                                                    bracket_pos: i,
                                                    bracket_label: `R2 #${i}`
                                                })
                                            } as any);
                                        }
                                    }
                                    onUpdate();
                                } finally {
                                    setCreatingR2(false);
                                }
                            }}
                            className="px-4 py-2 bg-val-red text-white rounded text-xs font-black uppercase tracking-widest disabled:opacity-50"
                            disabled={creatingR2}
                        >
                            {creatingR2 ? "Seeding..." : "Seed Round 2 BYEs"}
                        </button>
                    </div>
                </div>
            </div>
            <div className="min-w-[1000px] grid grid-cols-5 gap-6">
                {rounds.map((round) => (
                    <div key={round.id} className="space-y-4">
                        <div className="text-center font-display text-sm font-black uppercase tracking-widest text-foreground/60">
                            {round.name}
                        </div>
                        <div className="flex flex-col gap-3">
                            {Array.from({ length: round.slots }).map((_, idx) => {
                                const pos = idx + 1;
                                const match = getMatchAt(round.id, pos);
                                if (!match) {
                                    return (
                                        <div key={`${round.id}-${pos}`} className="glass p-4 border border-white/5 rounded">
                                            <div className="text-xs text-foreground/40 italic">Empty slot</div>
                                        </div>
                                    );
                                }
                                return (
                                    <div key={`${round.id}-${pos}`} className="glass p-4 border border-white/5 rounded space-y-3">
                                        <div className="text-[10px] font-black uppercase tracking-widest text-foreground/40">
                                            Match #{match.id}
                                        </div>
                                        <div className="grid grid-cols-2 gap-3 items-center">
                                            <div>
                                                <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-1">Team 1</label>
                                                <select
                                                    value={match.team1.id || 0}
                                                    onChange={e => handleAssign(match.id, 'team1_id', parseInt(e.target.value))}
                                                    className="w-full bg-white/5 border border-white/10 rounded p-2 text-xs focus:border-val-blue outline-none"
                                                >
                                                    <option value={0}>TBD</option>
                                                    {teams.map(t => <option key={t.id} value={t.id}>{t.name} [{t.tag}]</option>)}
                                                </select>
                                            </div>
                                            <div>
                                                <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-1">Team 2</label>
                                                <select
                                                    value={match.team2.id || 0}
                                                    onChange={e => handleAssign(match.id, 'team2_id', parseInt(e.target.value))}
                                                    className="w-full bg-white/5 border border-white/10 rounded p-2 text-xs focus:border-val-blue outline-none"
                                                >
                                                    <option value={0}>TBD</option>
                                                    {teams.map(t => <option key={t.id} value={t.id}>{t.name} [{t.tag}]</option>)}
                                                </select>
                                            </div>
                                        </div>
                                        <div className="flex items-center justify-between text-[10px] font-black uppercase tracking-widest text-foreground/40">
                                            <span>Format: {match.format}</span>
                                            <span>Status: {match.status}</span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                ))}
            </div>
            <div className="glass p-6 rounded border border-white/5 space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="font-display text-xl font-bold uppercase tracking-wider">Bracket Auto-Advancement</h3>
                    <div className="flex gap-3">
                        <button
                            onClick={async () => {
                                const { computeBracketAdvancements } = await import('@/lib/data');
                                const acts = await computeBracketAdvancements();
                                setProposals(acts);
                            }}
                            className="px-4 py-2 bg-white/10 text-foreground rounded text-xs font-black uppercase tracking-widest"
                        >
                            Scan Completed & Propose
                        </button>
                        <button
                            onClick={async () => {
                                if (proposals.length === 0) return;
                                const { applyBracketAdvancements } = await import('@/lib/data');
                                setSaving(true);
                                try {
                                    await applyBracketAdvancements(proposals);
                                    setProposals([]);
                                    onUpdate();
                                } finally {
                                    setSaving(false);
                                }
                            }}
                            className="px-4 py-2 bg-val-blue text-white rounded text-xs font-black uppercase tracking-widest disabled:opacity-50"
                            disabled={saving || proposals.length === 0}
                        >
                            Confirm & Apply
                        </button>
                        <label className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-foreground/60">
                            <input
                                type="checkbox"
                                checked={autoAdvance}
                                onChange={e => {
                                    const v = e.target.checked;
                                    setAutoAdvance(v);
                                    try { window.localStorage.setItem('playoffs_auto_advance', v ? '1' : '0'); } catch {}
                                }}
                            />
                            Auto-advance
                        </label>
                    </div>
                </div>
                {proposals.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead>
                                <tr className="bg-white/5 text-xs font-bold uppercase tracking-widest text-foreground/40">
                                    <th className="px-4 py-2">Target</th>
                                    <th className="px-4 py-2">Title</th>
                                    <th className="px-4 py-2">Reason</th>
                                    <th className="px-4 py-2">Action</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {proposals.map((p, idx) => (
                                    <tr key={idx}>
                                        <td className="px-4 py-2 text-xs">R{p.target_round} #{p.bracket_pos}</td>
                                        <td className="px-4 py-2 text-xs">{p.title}</td>
                                        <td className="px-4 py-2 text-xs text-foreground/60">{p.reason}</td>
                                        <td className="px-4 py-2 text-xs">{p.kind.toUpperCase()}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="text-[10px] font-black uppercase tracking-widest text-foreground/40">No proposals yet. Click Scan to compute.</div>
                )}
            </div>
            {saving && (
                <div className="text-[10px] font-black uppercase tracking-widest text-val-blue">Saving changes...</div>
            )}
        </section>
    );
}

/**
 * Unified Score & Map Editor with Tracker.gg JSON import
 */
function ScoreMapEditor() {
    const [matchId, setMatchId] = useState<number>(0);
    const [selectedWeek, setSelectedWeek] = useState<number>(1);
    const [format, setFormat] = useState<'BO1'|'BO3'|'BO5'>('BO3');
    const [forfeit, setForfeit] = useState(false);
    const [jsonText, setJsonText] = useState("");
    const [saving, setSaving] = useState(false);
    const [status, setStatus] = useState<string | null>(null);
    const [ghFiles, setGhFiles] = useState<{ name: string, path: string }[]>([]);
    const [ghId, setGhId] = useState<string>("");
    const [allMatches, setAllMatchesState] = useState<MatchEntry[]>([]);
    const [allPlayers, setAllPlayers] = useState<{ id: number; name: string; riot_id: string; default_team_id: number | null }[]>([]);
    const [pendingId, setPendingId] = useState<number | null>(null);
    const [mapIndex, setMapIndex] = useState(0);
    const [mapName, setMapName] = useState("Unknown");
    const [t1Rounds, setT1Rounds] = useState(0);
    const [t2Rounds, setT2Rounds] = useState(0);
    const [winnerId, setWinnerId] = useState<number | null>(null);
    const [team1Rows, setTeam1Rows] = useState<Array<{ player_id?: number; is_sub: boolean; subbed_for_id?: number; agent?: string; acs: number; kills: number; deaths: number; assists: number }>>([]);
    const [team2Rows, setTeam2Rows] = useState<Array<{ player_id?: number; is_sub: boolean; subbed_for_id?: number; agent?: string; acs: number; kills: number; deaths: number; assists: number }>>([]);
    const agentsList = ["Jett","Viper","Sage","Sova","Killjoy","Cypher","Omen","Brimstone","Raze","Reyna","Skye","Astra","Yoru","Neon","Harbor","Fade","Iso","Clove"];

    useEffect(() => {
        fetch("/api/github/matches")
            .then(r => r.json())
            .then(d => {
                if (d?.files) setGhFiles(d.files);
            })
            .catch(() => {});
        import("@/lib/data").then(({ getAllMatches }) => {
            getAllMatches().then(ms => setAllMatchesState(ms));
        });
        supabase.from('players').select('id, name, riot_id, default_team_id').then(({ data }) => {
            setAllPlayers((data as any[]) || []);
        });
        try {
            const mid = window.localStorage.getItem('auto_selected_match_id');
            const wk = window.localStorage.getItem('auto_selected_match_week');
            const url = window.localStorage.getItem('auto_selected_match_url');
            const pid = window.localStorage.getItem('pending_match_db_id');
            if (mid) setMatchId(parseInt(mid));
            if (wk) setSelectedWeek(parseInt(wk));
            if (url) {
                const m = url.match(/match\/([A-Za-z0-9\-]+)/);
                setGhId(m ? m[1] : url.replace(/[^A-Za-z0-9\-]/g,''));
            }
            if (pid) setPendingId(parseInt(pid));
        } catch {}
    }, []);

    const processJson = async () => {
        try {
            setSaving(true);
            setStatus(null);
            const parsed = JSON.parse(jsonText);
            const maps = parsed.maps || [];
            for (const m of maps) {
                const mapData = {
                    index: m.index ?? 0,
                    name: m.name ?? "Unknown",
                    t1_rounds: m.t1_rounds ?? 0,
                    t2_rounds: m.t2_rounds ?? 0,
                    winner_id: m.winner_id ?? null,
                    is_forfeit: Boolean(m.is_forfeit),
                };
                const playerStats = (m.players || []).map((p: any) => ({
                    team_id: p.team_id,
                    player_id: p.player_id,
                    is_sub: Boolean(p.is_sub),
                    subbed_for_id: p.subbed_for_id ?? null,
                    agent: p.agent ?? "Unknown",
                    acs: p.acs ?? 0,
                    kills: p.kills ?? 0,
                    deaths: p.deaths ?? 0,
                    assists: p.assists ?? 0,
                }));
                await saveMapResults(matchId, mapData, playerStats);
            }
            setStatus("Saved");
        } catch (e) {
            setStatus("Error");
        } finally {
            setSaving(false);
        }
    };

    const importFromGithub = async () => {
        if (!ghId) return;
        try {
            const cleaned = ghId.includes("tracker.gg")
                ? (ghId.match(/match\/([A-Za-z0-9\-]+)/)?.[1] || ghId)
                : ghId.replace(/[^A-Za-z0-9\-]/g, "");
            const r = await fetch(`/api/github/matches/resolve?mid=${encodeURIComponent(cleaned)}`);
            if (!r.ok) {
                const txt = await r.text();
                setStatus(`Error: ${txt}`);
                return;
            }
            const txt = await r.text();
            setJsonText(txt);
        } catch {
            setStatus("Error fetching from GitHub");
        }
    };

    const applyMatchData = async () => {
        try {
            const sel = allMatches.find(m => m.id === matchId);
            if (!sel) return;
            let json: any;
            if (jsonText && jsonText.trim()) {
                json = JSON.parse(jsonText);
            } else if (ghId) {
                const r = await fetch(`/api/github/matches/resolve?mid=${encodeURIComponent(ghId)}`);
                if (!r.ok) {
                    const txt = await r.text();
                    setStatus(`Error: ${txt}`);
                    return;
                }
                json = await r.json();
            } else {
                setStatus("Error: No match id provided");
                return;
            }
            const mapsArr = json?.maps || json?.data?.maps || [];
            if (Array.isArray(mapsArr)) {
                const len = mapsArr.length;
                if (len <= 1) setFormat('BO1');
                else if (len <= 3) setFormat('BO3');
                else setFormat('BO5');
            } else {
                setFormat('BO1');
            }
            const roster1Rids = allPlayers.filter(p => p.default_team_id === sel.team1.id).map(p => String(p.riot_id || "").trim().toLowerCase()).filter(Boolean);
            const roster2Rids = allPlayers.filter(p => p.default_team_id === sel.team2.id).map(p => String(p.riot_id || "").trim().toLowerCase()).filter(Boolean);
            const out = parseTrackerJson(json, sel.team1.id, sel.team2.id, roster1Rids, roster2Rids, mapIndex);
            setMapName(out.map_name);
            setT1Rounds(Math.round(out.t1_rounds));
            setT2Rounds(Math.round(out.t2_rounds));
            if (out.t1_rounds > out.t2_rounds) setWinnerId(sel.team1.id);
            else if (out.t2_rounds > out.t1_rounds) setWinnerId(sel.team2.id);
            const roster1 = allPlayers.filter(p => p.default_team_id === sel.team1.id);
            const roster2 = allPlayers.filter(p => p.default_team_id === sel.team2.id);
            const labToId = new Map(allPlayers.map(p => [String(p.riot_id || "").trim().toLowerCase(), p.id]));
            const suggestions = out.suggestions || {};
            const teamRows = (teamNum: 1 | 2, roster: typeof allPlayers) => {
                const rids = Object.keys(suggestions).filter(k => suggestions[k].team_num === teamNum);
                const rows: any[] = [];
                rids.forEach(rid => {
                    const s = suggestions[rid];
                    const pid = labToId.get(rid);
                    rows.push({ player_id: pid, is_sub: false, subbed_for_id: pid, agent: s.agent, acs: Math.round(s.acs || 0), kills: s.k, deaths: s.d, assists: s.a });
                });
                while (rows.length < 5) {
                    const p = roster[rows.length]?.id;
                    rows.push({ player_id: p, is_sub: false, subbed_for_id: p, agent: agentsList[0], acs: 0, kills: 0, deaths: 0, assists: 0 });
                }
                return rows.slice(0,5);
            };
            setTeam1Rows(teamRows(1, roster1));
            setTeam2Rows(teamRows(2, roster2));
        } catch {
            setStatus("Error");
        }
    };

    const saveForfeitMatch = async () => {
        if (!matchId) return;
        setSaving(true);
        try {
            await clearMatchDetails(matchId);
            const sel = allMatches.find(m => m.id === matchId);
            const s1 = forfeit ? 13 : 0;
            const s2 = forfeit ? 0 : 13;
            const winner_id = s1 > s2 ? sel?.team1.id : sel?.team2.id;
            await updateMatch(matchId, { score_t1: s1, score_t2: s2, winner_id, status: 'completed', format, maps_played: 0, is_forfeit: true as any });
            setStatus("Saved");
        } catch {
            setStatus("Error");
        } finally {
            setSaving(false);
        }
    };
    return (
        <section className="glass p-12 space-y-6">
            <h3 className="font-display text-2xl font-black text-val-red uppercase italic">Unified Score Editor</h3>
            <p className="text-foreground/40 text-sm font-medium">Enter map results, player stats, and import Tracker.gg JSON.</p>
            <div className="grid md:grid-cols-2 gap-8">
                <div className="space-y-4">
                    <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Week</label>
                    <select
                        value={selectedWeek}
                        onChange={e => setSelectedWeek(parseInt(e.target.value))}
                        className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm focus:border-val-red outline-none transition-colors"
                    >
                        {[1,2,3,4,5,6].map(w => <option key={w} value={w}>Week {w}</option>)}
                    </select>
                    <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Match</label>
                    <select
                        value={matchId}
                        onChange={e => setMatchId(parseInt(e.target.value))}
                        className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm focus:border-val-red outline-none transition-colors"
                    >
                        <option value={0}>Select match</option>
                        {allMatches.filter(m => m.week === selectedWeek).map(m => (
                            <option key={m.id} value={m.id}>
                                ID {m.id}: {m.team1.name} vs {m.team2.name} ({m.group_name})
                            </option>
                        ))}
                    </select>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Format</label>
                            <select
                                value={format}
                                onChange={e => setFormat(e.target.value as any)}
                                className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm focus:border-val-red outline-none transition-colors"
                            >
                                <option>BO1</option>
                                <option>BO3</option>
                                <option>BO5</option>
                            </select>
                        </div>
                        <div className="flex items-end">
                            <label className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-foreground/60">
                                <input type="checkbox" checked={forfeit} onChange={e => setForfeit(e.target.checked)} />
                                Match-level Forfeit
                            </label>
                        </div>
                    </div>
                    <div className="text-[10px] font-black uppercase tracking-widest text-foreground/60 bg-val-blue/10 rounded p-3">
                        Match details are managed per-map below. The total match score will be automatically updated.
                    </div>
                    {/* Combined input for tracker URL or ID */}
                    <div className="grid grid-cols-3 gap-2">
                        <div className="col-span-2">
                            <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Match URL or ID</label>
                            <input
                                value={ghId}
                                onChange={e => {
                                    const v = e.target.value;
                                    const m = v.match(/match\/([A-Za-z0-9\-]+)/);
                                    setGhId(m ? m[1] : v.replace(/[^A-Za-z0-9\-]/g,''));
                                }}
                                placeholder="https://tracker.gg/valorant/match/..."
                                className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm focus:border-val-blue outline-none transition-colors"
                            />
                        </div>
                        <div className="pt-6">
                            <button
                                onClick={async () => { await importFromGithub(); await applyMatchData(); }}
                                className="w-full py-2 bg-val-blue text-white font-black uppercase tracking-widest text-[10px] rounded"
                            >
                                Apply Match Data
                            </button>
                        </div>
                    </div>
                    <button
                        disabled={!matchId || !forfeit || saving}
                        onClick={saveForfeitMatch}
                        className="w-full py-3 bg-val-red text-white font-display font-black uppercase tracking-widest text-xs rounded"
                    >
                        {saving ? "Saving..." : "Save Forfeit Match"}
                    </button>
                    {status && (
                        <div className={`text-xs font-bold uppercase tracking-widest ${status === 'Saved' ? 'text-val-blue' : 'text-val-red'}`}>
                            {status}
                        </div>
                    )}
                </div>
                <div className="space-y-2">
                    <div className="text-[10px] font-black uppercase tracking-widest text-foreground/40">JSON schema</div>
                    <div className="text-xs text-foreground/60">
                        maps[].index • maps[].name • maps[].t1_rounds • maps[].t2_rounds • maps[].winner_id • maps[].is_forfeit • maps[].players[] with team_id, player_id, is_sub, subbed_for_id, agent, acs, kills, deaths, assists
                    </div>
                </div>
            </div>
            <div className="space-y-6">
                <h4 className="font-display text-xl font-bold uppercase tracking-wider">Per-Map Scoreboard</h4>
                <div className="grid grid-cols-4 gap-4">
                    <div>
                        <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Select Map</label>
                        <select value={mapIndex} onChange={e => setMapIndex(parseInt(e.target.value))} className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm">
                            {[0,1,2,3,4].map(i => <option key={i} value={i}>{i+1}</option>)}
                        </select>
                    </div>
                    <div>
                        <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Map Name</label>
                        <select value={mapName} onChange={e => setMapName(e.target.value)} className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm">
                            {["Unknown","Ascent","Bind","Breeze","Fracture","Haven","Icebox","Lotus","Pearl","Split","Sunset"].map(m => <option key={m} value={m}>{m}</option>)}
                        </select>
                    </div>
                    <div>
                        <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Team1 Rounds</label>
                        <input type="number" value={t1Rounds} onChange={e => setT1Rounds(parseInt(e.target.value))} className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm" />
                    </div>
                    <div>
                        <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Team2 Rounds</label>
                        <input type="number" value={t2Rounds} onChange={e => setT2Rounds(parseInt(e.target.value))} className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm" />
                    </div>
                </div>
                <div className="grid grid-cols-4 gap-4">
                    <div>
                        <label className="text-[10px] font-black uppercase tracking-widest text-foreground/40 block mb-2">Map Winner</label>
                        {(() => {
                            const sel = allMatches.find(m => m.id === matchId);
                            const options = [
                                { id: sel?.team1.id, name: sel?.team1.name },
                                { id: sel?.team2.id, name: sel?.team2.name }
                            ].filter(o => o.id);
                            return (
                                <select value={winnerId ?? 0} onChange={e => setWinnerId(parseInt(e.target.value))} className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm">
                                    <option value={0}>TBD</option>
                                    {options.map(o => <option key={o!.id!} value={o!.id!}>{o!.name!}</option>)}
                                </select>
                            );
                        })()}
                    </div>
                    <div className="flex items-end">
                        <label className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-foreground/60">
                            <input type="checkbox" checked={false} onChange={() => {}} />
                            Forfeit%s
                        </label>
                    </div>
                </div>
                <div className="space-y-10">
                    {[1,2].map(teamNum => {
                        const sel = allMatches.find(m => m.id === matchId);
                        const teamId = teamNum === 1 ? sel?.team1.id : sel?.team2.id;
                        const teamName = teamNum === 1 ? sel?.team1.name : sel?.team2.name;
                        const roster = allPlayers.filter(p => p.default_team_id === teamId);
                        const rosterOptions = roster.map(p => ({ id: p.id, label: `${p.name} (${p.riot_id || ''})` }));
                        const globalOptions = allPlayers.map(p => ({ id: p.id, label: `${p.name} (${p.riot_id || ''})` }));
                        const rows = teamNum === 1 ? team1Rows : team2Rows;
                        const setRows = teamNum === 1 ? setTeam1Rows : setTeam2Rows;
                        return (
                            <div key={teamNum} className="glass p-8 border border-white/5 rounded w-full">
                                <h5 className="font-display text-lg font-bold uppercase tracking-wider mb-4">{teamName} Scoreboard</h5>
                                <div className="space-y-3">
                                    <div className="grid grid-cols-9 gap-4 items-center text-[10px] font-black uppercase tracking-widest text-foreground/40">
                                        <div>Player</div>
                                        <div>Sub</div>
                                        <div>Subbing For</div>
                                        <div>Agent</div>
                                        <div>ACS</div>
                                        <div>K</div>
                                        <div>D</div>
                                        <div>A</div>
                                        <div>Conf</div>
                                    </div>
                                    {rows.map((row, idx) => (
                                        <div key={idx} className="grid grid-cols-9 gap-4 items-center">
                                            <select value={row.player_id || 0} onChange={e => {
                                                const v = parseInt(e.target.value);
                                                const next = [...rows];
                                                const selectedPlayer = allPlayers.find(p => p.id === v);
                                                const isOnTeam = !!selectedPlayer && selectedPlayer.default_team_id === teamId;
                                                // auto sub if not on this team
                                                let subFor = row.subbed_for_id;
                                                if (!isOnTeam) {
                                                    // pick first roster not already subbed_for
                                                    const used = new Set(next.map(r => r.subbed_for_id).filter(Boolean));
                                                    const firstAvailable = roster.find(r => !used.has(r.id))?.id || roster[0]?.id;
                                                    subFor = firstAvailable;
                                                } else {
                                                    subFor = v;
                                                }
                                                next[idx] = { ...row, player_id: v, subbed_for_id: subFor ?? undefined, is_sub: !isOnTeam };
                                                setRows(next);
                                            }} className="bg-white/5 text-white border border-white/10 rounded p-3 text-base">
                                                <option value={0}>Select</option>
                                                {globalOptions.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
                                            </select>
                                            <input type="checkbox" checked={row.is_sub} onChange={e => {
                                                const next = [...rows]; next[idx] = { ...row, is_sub: e.target.checked };
                                                setRows(next);
                                            }} />
                                            <select value={row.subbed_for_id || 0} onChange={e => {
                                                const v = parseInt(e.target.value);
                                                const next = [...rows]; next[idx] = { ...row, subbed_for_id: v };
                                                setRows(next);
                                            }} className="bg-white/5 text-white border border-white/10 rounded p-3 text-base">
                                                <option value={0}>Select</option>
                                                {rosterOptions.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
                                            </select>
                                            <select value={row.agent || ''} onChange={e => {
                                                const next = [...rows]; next[idx] = { ...row, agent: e.target.value };
                                                setRows(next);
                                            }} className="bg-white/5 text-white border border-white/10 rounded p-3 text-base">
                                                {agentsList.map(a => <option key={a} value={a}>{a}</option>)}
                                            </select>
                                            <input type="number" step={1} value={Math.round(row.acs)} onChange={e => { const next = [...rows]; next[idx] = { ...row, acs: parseInt(e.target.value) || 0 }; setRows(next); }} className="bg-white/5 border border-white/10 rounded p-3 text-base" />
                                            <input type="number" step={1} value={row.kills} onChange={e => { const next = [...rows]; next[idx] = { ...row, kills: parseInt(e.target.value) || 0 }; setRows(next); }} className="bg-white/5 border border-white/10 rounded p-3 text-base" />
                                            <input type="number" step={1} value={row.deaths} onChange={e => { const next = [...rows]; next[idx] = { ...row, deaths: parseInt(e.target.value) || 0 }; setRows(next); }} className="bg-white/5 border border-white/10 rounded p-3 text-base" />
                                            <input type="number" step={1} value={row.assists} onChange={e => { const next = [...rows]; next[idx] = { ...row, assists: parseInt(e.target.value) || 0 }; setRows(next); }} className="bg-white/5 border border-white/10 rounded p-3 text-base" />
                                            <div className="text-[10px] font-black uppercase tracking-widest text-foreground/40">Conf</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        );
                    })}
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={async () => {
                            if (!matchId) return;
                            setSaving(true);
                            try {
                                const sel = allMatches.find(m => m.id === matchId);
                                const wId = winnerId;
                                const payloadRows = [
                                    ...team1Rows.map(r => ({ team_id: sel?.team1.id as number, ...r })),
                                    ...team2Rows.map(r => ({ team_id: sel?.team2.id as number, ...r })),
                                ].filter(r => r.player_id);
                                await saveMapResults(matchId, {
                                    index: mapIndex,
                                    name: mapName,
                                    t1_rounds: t1Rounds,
                                    t2_rounds: t2Rounds,
                                    winner_id: wId || null,
                                    is_forfeit: false
                                }, payloadRows.map(r => ({
                                    team_id: r.team_id,
                                    player_id: r.player_id as number,
                                    is_sub: r.is_sub,
                                    subbed_for_id: r.subbed_for_id ?? null,
                                    agent: r.agent || "Unknown",
                                    acs: r.acs,
                                    kills: r.kills,
                                    deaths: r.deaths,
                                    assists: r.assists
                                })), { pendingId: pendingId || undefined, url: window.localStorage.getItem('auto_selected_match_url') || undefined });
                                setStatus("Saved");
                            } catch {
                                setStatus("Error");
                            } finally {
                                setSaving(false);
                            }
                        }}
                        className="px-4 py-2 bg-white/10 text-foreground rounded text-xs font-black uppercase tracking-widest"
                    >
                        Save Map Details & Scoreboard
                    </button>
                </div>
            </div>
        </section>
    );
}

/**
 * Players Admin: add/edit players and assign permanent subs
 */
function PlayersAdmin() {
    const [players, setPlayers] = useState<Array<{ id: number; name: string; riot_id: string; uuid?: string; rank?: string; tracker_link?: string; default_team_id?: number | null }>>([]);
    const [teams, setTeams] = useState<Array<{ id: number; name: string }>>([]);
    const [filter, setFilter] = useState("");
    const [form, setForm] = useState<{ name: string; riot_id: string; uuid: string; rank: string; tracker_link: string; team_id: number | null }>({ name: "", riot_id: "", uuid: "", rank: "Unranked", tracker_link: "", team_id: null });
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        supabase.from('teams').select('id, name').order('name').then(({ data }) => setTeams((data as any[]) || []));
        supabase.from('players').select('id, name, riot_id, uuid, rank, tracker_link, default_team_id').order('name').then(({ data }) => setPlayers((data as any[]) || []));
    }, []);

    const refresh = async () => {
        const { data } = await supabase.from('players').select('id, name, riot_id, rank, default_team_id').order('name');
        setPlayers((data as any[]) || []);
    };

    const addPlayer = async () => {
        if (!form.name.trim()) return;
        setSaving(true);
        try {
            await fetch('/api/admin/players/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: form.name.trim(),
                    riot_id: form.riot_id.trim() || null,
                    uuid: form.uuid.trim() || null,
                    rank: form.rank,
                    tracker_link: form.tracker_link.trim() || null,
                    default_team_id: form.team_id || null
                })
            } as any);
            setForm({ name: "", riot_id: "", uuid: "", rank: "Unranked", tracker_link: "", team_id: null });
            await refresh();
        } finally {
            setSaving(false);
        }
    };

    const assignPermSub = async (playerId: number, teamId: number | null) => {
        setSaving(true);
        try {
            await fetch('/api/admin/players/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: playerId, update: { default_team_id: teamId } })
            } as any);
            await refresh();
        } finally {
            setSaving(false);
        }
    };

    const filtered = players.filter(p => {
        const s = filter.toLowerCase();
        return !s || p.name.toLowerCase().includes(s) || (p.riot_id || "").toLowerCase().includes(s);
    });

    return (
        <section className="space-y-6">
            <h2 className="font-display text-xl font-black text-val-blue uppercase italic">Players Admin</h2>
            <div className="glass p-8 space-y-4">
                <h3 className="font-display text-lg font-black uppercase">Add Player</h3>
                <div className="grid md:grid-cols-2 gap-4">
                    <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Name (@discord)" className="bg-white/5 border border-white/10 rounded p-2 text-sm" />
                    <input value={form.riot_id} onChange={e => setForm({ ...form, riot_id: e.target.value })} placeholder="Riot ID" className="bg-white/5 border border-white/10 rounded p-2 text-sm" />
                    <input value={form.uuid} onChange={e => setForm({ ...form, uuid: e.target.value })} placeholder="UUID" className="bg-white/5 border border-white/10 rounded p-2 text-sm" />
                    <select value={form.rank} onChange={e => setForm({ ...form, rank: e.target.value })} className="bg-white/5 border border-white/10 rounded p-2 text-sm">
                        {["Unranked","Iron/Bronze","Silver","Gold","Platinum","Diamond","Ascendant","Immortal 1/2","Immortal 3/Radiant"].map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                    <input value={form.tracker_link} onChange={e => setForm({ ...form, tracker_link: e.target.value })} placeholder="Tracker Link" className="bg-white/5 border border-white/10 rounded p-2 text-sm" />
                    <select value={form.team_id || 0} onChange={e => setForm({ ...form, team_id: parseInt(e.target.value) || null })} className="bg-white/5 border border-white/10 rounded p-2 text-sm">
                        <option value={0}>No Team</option>
                        {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                </div>
                <button onClick={addPlayer} disabled={saving || !form.name.trim()} className="px-4 py-2 bg-val-blue text-white rounded text-xs font-black uppercase tracking-widest">
                    {saving ? "Saving..." : "Create Player"}
                </button>
            </div>

            <div className="glass p-8 space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="font-display text-lg font-black uppercase">Roster & Permanent Subs</h3>
                    <input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Search by name or Riot ID" className="bg-white/5 border border-white/10 rounded p-2 text-sm w-64" />
                </div>
                <div className="overflow-x-auto">
                    <table className="min-w-[1100px] w-full text-sm">
                        <thead>
                            <tr className="text-left text-foreground/60">
                                <th className="py-2">Name</th>
                                <th className="py-2">Riot ID</th>
                                <th className="py-2">UUID</th>
                                <th className="py-2">Rank</th>
                                <th className="py-2">Tracker Link</th>
                                <th className="py-2">Team</th>
                                <th className="py-2">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map(p => (
                                <tr key={p.id} className="border-t border-white/5">
                                    <td className="py-2">
                                        <input defaultValue={p.name} onBlur={e => fetch('/api/admin/players/update', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: p.id, update: { name: e.target.value } }) } as any)} className="bg-white/5 border border-white/10 rounded p-2 text-xs w-full" />
                                    </td>
                                    <td className="py-2">
                                        <input defaultValue={p.riot_id || ''} onBlur={e => fetch('/api/admin/players/update', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: p.id, update: { riot_id: e.target.value || null } }) } as any)} className="bg-white/5 border border-white/10 rounded p-2 text-xs w-full" />
                                    </td>
                                    <td className="py-2">
                                        <input defaultValue={p.uuid || ''} onBlur={e => fetch('/api/admin/players/update', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: p.id, update: { uuid: e.target.value || null } }) } as any)} className="bg-white/5 border border-white/10 rounded p-2 text-xs w-full" />
                                    </td>
                                    <td className="py-2">
                                        <select defaultValue={p.rank || 'Unranked'} onChange={e => fetch('/api/admin/players/update', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: p.id, update: { rank: e.target.value } }) } as any)} className="bg-white/5 border border-white/10 rounded p-2 text-xs w-full">
                                            {["Unranked","Iron/Bronze","Silver","Gold","Platinum","Diamond","Ascendant","Immortal 1/2","Immortal 3/Radiant"].map(r => <option key={r} value={r}>{r}</option>)}
                                        </select>
                                    </td>
                                    <td className="py-2">
                                        <input defaultValue={p.tracker_link || ''} onBlur={e => fetch('/api/admin/players/update', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: p.id, update: { tracker_link: e.target.value || null } }) } as any)} className="bg-white/5 border border-white/10 rounded p-2 text-xs w-full" />
                                    </td>
                                    <td className="py-2">
                                        <select defaultValue={p.default_team_id || 0} onChange={e => assignPermSub(p.id, parseInt(e.target.value) || null)} className="bg-white/5 border border-white/10 rounded p-2 text-xs w-full">
                                            <option value={0}>No Team</option>
                                            {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                                        </select>
                                    </td>
                                    <td className="py-2">
                                        <button onClick={async () => { await refresh(); }} className="px-3 py-1 bg-white/10 rounded text-[10px] font-black uppercase tracking-widest">Refresh</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>
    );
}
