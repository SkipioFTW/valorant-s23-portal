'use client';

import { useState, useEffect } from 'react';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, Legend, BarChart, Bar
} from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import { type PlayerStats, getPlayerStats } from '@/lib/data';

import PlayerSearch from './PlayerSearch';

const COLORS = ['#FF4655', '#3FD1FF', '#FFB800', '#00FF94', '#8E44AD', '#E67E22'];

interface Props {
    players: { id: number; name: string; riot_id: string }[];
    initialSelectedId?: number;
}

export default function PlayerAnalytics({ players, initialSelectedId }: Props) {
    const [selectedId, setSelectedId] = useState<number | null>(initialSelectedId ?? players[0]?.id ?? null);
    const [stats, setStats] = useState<PlayerStats | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (initialSelectedId) setSelectedId(initialSelectedId);
        if (selectedId) {
            setLoading(true);
            getPlayerStats(selectedId).then(data => {
                setStats(data);
                setLoading(false);
            });
        }
    }, [selectedId, initialSelectedId]);

    return (
        <div className="space-y-8">
            {/* Player Searcher */}
            <div className="flex justify-center">
                <PlayerSearch
                    players={players}
                    onSelect={setSelectedId}
                    currentId={selectedId}
                />
            </div>

            <AnimatePresence mode="wait">
                {loading ? (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="h-[400px] flex items-center justify-center"
                    >
                        <div className="w-8 h-8 border-4 border-val-red border-t-transparent rounded-full animate-spin" />
                    </motion.div>
                ) : stats ? (
                    <motion.div
                        key={stats.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className="space-y-8"
                    >
                        {/* Player Header Card */}
                        <div className="glass rounded-xl p-8 border border-white/5 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
                                <span className="font-display text-8xl font-black italic uppercase tracking-tighter">
                                    {stats.team}
                                </span>
                            </div>
                            <div className="relative z-10">
                                <div className="flex flex-col md:flex-row md:items-end gap-6">
                                    <div className="w-24 h-24 rounded-2xl bg-val-deep border-4 border-val-red flex items-center justify-center shadow-2xl overflow-hidden">
                                        <span className="font-display text-4xl font-black italic text-white uppercase">
                                            {stats.name[0]}
                                        </span>
                                    </div>
                                    <div className="flex-1">
                                        <h2 className="font-display text-4xl md:text-6xl font-black uppercase tracking-tighter leading-none mb-2">
                                            {stats.name}
                                        </h2>
                                        <div className="flex flex-wrap items-center gap-4 text-foreground/40 font-bold uppercase tracking-widest text-sm">
                                            <span className="text-val-red">{stats.riot_id}</span>
                                            <span className="w-1.5 h-1.5 rounded-full bg-white/20" />
                                            <span>Member of <span className="text-val-blue">{stats.team}</span></span>
                                        </div>
                                    </div>
                                    <div className="flex gap-4">
                                        <div className="text-right">
                                            <div className="text-[10px] font-black uppercase tracking-tighter text-foreground/40">Win Rate</div>
                                            <div className="text-3xl font-display font-black text-val-red">{stats.summary.winRate}%</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        {/* Agent/Map Win Rates */}
                        <div className="grid lg:grid-cols-2 gap-8">
                            <div className="glass rounded-xl p-6 border border-white/5">
                                <h3 className="font-display text-xl font-bold mb-6 uppercase tracking-wider">Agent Win Rates</h3>
                                <div className="h-[300px] w-full">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={stats.agentWinRates || []} layout="vertical" margin={{ left: 40 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                                            <XAxis type="number" domain={[0, 100]} stroke="#ffffff60" fontSize={12} />
                                            <YAxis dataKey="name" type="category" stroke="#ffffff60" fontSize={12} width={100} />
                                            <Tooltip contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} />
                                            <Legend />
                                            <Bar dataKey="wr" name="Win Rate (%)" fill="#3FD1FF" radius={[0, 4, 4, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                            <div className="glass rounded-xl p-6 border border-white/5">
                                <h3 className="font-display text-xl font-bold mb-6 uppercase tracking-wider">Map Win Rates</h3>
                                <div className="h-[300px] w-full">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={stats.mapWinRates || []} layout="vertical" margin={{ left: 40 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                                            <XAxis type="number" domain={[0, 100]} stroke="#ffffff60" fontSize={12} />
                                            <YAxis dataKey="name" type="category" stroke="#ffffff60" fontSize={12} width={100} />
                                            <Tooltip contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} />
                                            <Legend />
                                            <Bar dataKey="wr" name="Win Rate (%)" fill="#FF4655" radius={[0, 4, 4, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>

                        {/* Summary Cards */}
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                            <StatCard label="Avg ACS" value={stats.summary.avgAcs} color="text-val-red" />
                            <StatCard label="K/D Ratio" value={stats.summary.kd} color="text-val-blue" />
                            <StatCard label="Kills / Round" value={stats.summary.kpr} color="text-val-yellow" />
                            <StatCard label="Matches" value={stats.summary.matches} color="text-foreground" />
                            <StatCard label="Top Agent" value={stats.agents[0]?.name || 'N/A'} color="text-val-red" />
                        </div>

                        <div className="grid lg:grid-cols-2 gap-8">
                            {/* ACS Trend */}
                            <div className="glass rounded-xl p-6 border border-white/5">
                                <div className="flex items-center justify-between mb-6">
                                    <h3 className="font-display text-xl font-bold uppercase tracking-wider">Combat Score Trend</h3>
                                    <div className="text-xs font-bold text-foreground/40 italic">Progression by Week</div>
                                </div>
                                <div className="h-[300px] w-full">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={stats.performance}>
                                            <defs>
                                                <linearGradient id="colorAcs" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#FF4655" stopOpacity={0.3} />
                                                    <stop offset="95%" stopColor="#FF4655" stopOpacity={0} />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                                            <XAxis
                                                dataKey="week"
                                                stroke="#ffffff60"
                                                tickFormatter={(v) => `W${v}`}
                                                fontSize={12}
                                            />
                                            <YAxis stroke="#ffffff60" fontSize={12} />
                                            <Tooltip
                                                contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                                                itemStyle={{ color: '#fff' }}
                                            />
                                            <Area
                                                type="monotone"
                                                dataKey="acs"
                                                stroke="#FF4655"
                                                strokeWidth={3}
                                                fillOpacity={1}
                                                fill="url(#colorAcs)"
                                            />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            {/* KD Trend */}
                            <div className="glass rounded-xl p-6 border border-white/5">
                                <div className="flex items-center justify-between mb-6">
                                    <h3 className="font-display text-xl font-bold uppercase tracking-wider">K/D performance</h3>
                                    <div className="text-xs font-bold text-foreground/40 italic">Consistency Metric</div>
                                </div>
                                <div className="h-[300px] w-full">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={stats.performance}>
                                            <defs>
                                                <linearGradient id="colorKd" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#3FD1FF" stopOpacity={0.3} />
                                                    <stop offset="95%" stopColor="#3FD1FF" stopOpacity={0} />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                                            <XAxis
                                                dataKey="week"
                                                stroke="#ffffff60"
                                                tickFormatter={(v) => `W${v}`}
                                                fontSize={12}
                                            />
                                            <YAxis stroke="#ffffff60" fontSize={12} domain={[0, 'auto']} />
                                            <Tooltip
                                                contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                                                itemStyle={{ color: '#fff' }}
                                            />
                                            <Area
                                                type="monotone"
                                                dataKey="kd"
                                                stroke="#3FD1FF"
                                                strokeWidth={3}
                                                fillOpacity={1}
                                                fill="url(#colorKd)"
                                            />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>

                        <div className="grid lg:grid-cols-3 gap-8">
                            {/* Agent Pick Rate */}
                            <div className="glass rounded-xl p-6 border border-white/5">
                                <h3 className="font-display text-xl font-bold mb-6 uppercase tracking-wider">Agent Pick Rate</h3>
                                <div className="h-[300px] w-full">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie
                                                data={stats.agents}
                                                cx="50%"
                                                cy="50%"
                                                innerRadius={60}
                                                outerRadius={80}
                                                paddingAngle={5}
                                                dataKey="count"
                                            >
                                                {stats.agents.map((entry, index) => (
                                                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                                ))}
                                            </Pie>
                                            <Tooltip
                                                contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                                                itemStyle={{ color: '#fff' }}
                                            />
                                            <Legend />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            {/* Recent Matches Table */}
                            <div className="lg:col-span-2 glass rounded-xl border border-white/5 overflow-hidden">
                                <div className="p-6 border-b border-white/5">
                                    <h3 className="font-display text-xl font-bold uppercase tracking-wider">Recent Match Breakdown</h3>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left">
                                        <thead>
                                            <tr className="bg-white/5 text-xs font-bold uppercase tracking-widest text-foreground/40">
                                                <th className="px-6 py-4">Status</th>
                                                <th className="px-6 py-4">Opponent</th>
                                                <th className="px-6 py-4">Map</th>
                                                <th className="px-6 py-4 text-center">ACS</th>
                                                <th className="px-6 py-4 text-center">K/D/A</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-white/5">
                                            {stats.recentMatches.map((match, i) => (
                                                <tr key={i} className="hover:bg-white/[0.02] transition-colors group">
                                                    <td className="px-6 py-4">
                                                        <span className={`px-3 py-1 rounded text-[10px] font-black uppercase tracking-tighter ${match.result === 'win' ? 'bg-val-blue/20 text-val-blue' :
                                                            match.result === 'loss' ? 'bg-val-red/20 text-val-red' :
                                                                'bg-foreground/10 text-foreground/60'
                                                            }`}>
                                                            {match.result}
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4 font-bold text-sm">{match.opponent}</td>
                                                    <td className="px-6 py-4 text-foreground/60 text-sm italic">{match.map}</td>
                                                    <td className="px-6 py-4 text-center font-display font-bold text-val-blue">{match.acs}</td>
                                                    <td className="px-6 py-4 text-center text-sm font-medium">
                                                        {match.kills} / <span className="text-val-red">{match.deaths}</span> / {match.assists}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                ) : (
                    <div className="h-[400px] flex items-center justify-center text-foreground/40 italic">
                        No statistical data found for this player.
                    </div>
                )}
            </AnimatePresence>
        </div>
    );
}

function StatCard({ label, value, color }: { label: string, value: string | number, color: string }) {
    return (
        <div className="glass rounded-xl p-4 border border-white/5 flex flex-col justify-center">
            <div className="text-[10px] font-black uppercase tracking-tighter text-foreground/40 mb-1">{label}</div>
            <div className={`text-2xl font-display font-black tracking-tight ${color}`}>{value}</div>
        </div>
    );
}
