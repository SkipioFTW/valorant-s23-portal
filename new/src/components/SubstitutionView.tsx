'use client';

import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    Legend, Cell, PieChart, Pie
} from 'recharts';
import { motion } from 'framer-motion';
import { type SubstitutionAnalytics } from '@/lib/data';

interface Props {
    data: SubstitutionAnalytics;
}

const COLORS = ['#FF4655', '#3FD1FF', '#FFB800', '#00FF94', '#8E44AD'];

export default function SubstitutionView({ data }: Props) {
    return (
        <div className="space-y-12">
            {/* Top Stats Overview */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="glass rounded-xl p-6 border border-white/5"
                >
                    <div className="text-xs font-bold text-foreground/40 uppercase tracking-widest mb-2">Total Substitutions</div>
                    <div className="text-5xl font-display font-black text-val-red">
                        {data.logs.length}
                    </div>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 }}
                    className="glass rounded-xl p-6 border border-white/5"
                >
                    <div className="text-xs font-bold text-foreground/40 uppercase tracking-widest mb-2">Most Impactful Team</div>
                    <div className="text-2xl font-display font-black text-val-blue uppercase">
                        {data.teamStats[0]?.teamName || 'N/A'}
                    </div>
                    <div className="text-xs text-foreground/60 italic mt-1">
                        {data.teamStats[0]?.subCount || 0} subs used
                    </div>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.2 }}
                    className="glass rounded-xl p-6 border border-white/5"
                >
                    <div className="text-xs font-bold text-foreground/40 uppercase tracking-widest mb-2">Top Substitute</div>
                    <div className="text-2xl font-display font-black text-val-yellow uppercase">
                        {data.topSubs[0]?.name || 'N/A'}
                    </div>
                    <div className="text-xs text-foreground/60 italic mt-1">
                        Avg ACS: {data.topSubs[0]?.avgAcs || 0}
                    </div>
                </motion.div>
            </div>

            <div className="grid lg:grid-cols-2 gap-8">
                {/* Win Rate Impact Chart */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="glass rounded-xl p-8 border border-white/5"
                >
                    <h3 className="font-display text-2xl font-bold mb-8 uppercase tracking-wider">Win Rate Impact Analysis</h3>
                    <div className="h-[400px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={data.teamStats} layout="vertical" margin={{ left: 40, right: 40 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" horizontal={false} />
                                <XAxis type="number" domain={[0, 100]} hide />
                                <YAxis
                                    dataKey="teamName"
                                    type="category"
                                    stroke="#ffffff60"
                                    fontSize={10}
                                    width={100}
                                    tick={{ fill: '#ffffff60', fontWeight: 'bold' }}
                                />
                                <Tooltip
                                    cursor={{ fill: 'rgba(255,b,b,0.05)' }}
                                    contentStyle={{ backgroundColor: '#111', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                                />
                                <Legend verticalAlign="top" height={36} />
                                <Bar dataKey="winRateWithSub" name="WR with Sub" fill="#FF4655" radius={[0, 4, 4, 0]} barSize={12} />
                                <Bar dataKey="winRateWithoutSub" name="WR without Sub" fill="#3FD1FF" radius={[0, 4, 4, 0]} barSize={12} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </motion.div>

                {/* Sub Success Leaderboard */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="glass rounded-xl p-8 border border-white/5"
                >
                    <h3 className="font-display text-2xl font-bold mb-8 uppercase tracking-wider">Top Substitute Performers</h3>
                    <div className="space-y-6">
                        {data.topSubs.slice(0, 5).map((sub, i) => (
                            <div key={i} className="flex items-center gap-4 group">
                                <div className="font-display text-2xl font-black text-foreground/20 italic group-hover:text-val-red transition-colors">
                                    0{i + 1}
                                </div>
                                <div className="flex-1">
                                    <div className="flex items-center justify-between mb-1">
                                        <div className="font-bold text-lg">{sub.name}</div>
                                        <div className="font-display font-black text-val-blue italic">{sub.avgAcs} ACS</div>
                                    </div>
                                    <div className="flex items-center justify-between text-xs font-bold uppercase tracking-widest text-foreground/40">
                                        <div>{sub.team}</div>
                                        <div>{sub.matches} Appearances</div>
                                    </div>
                                    <div className="mt-2 h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                                        <motion.div
                                            initial={{ width: 0 }}
                                            animate={{ width: `${(sub.avgAcs / 400) * 100}%` }}
                                            className="h-full bg-gradient-to-r from-val-red to-val-yellow"
                                        />
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </motion.div>
            </div>

            {/* Detailed Substitution Log */}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="glass rounded-xl border border-white/5 overflow-hidden"
            >
                <div className="p-8 border-b border-white/5 flex items-center justify-between">
                    <div>
                        <h3 className="font-display text-2xl font-bold uppercase tracking-wider">Historical Substitution Log</h3>
                        <p className="text-foreground/40 text-sm mt-1">Detailed record of player appearances and match outcomes</p>
                    </div>
                    <div className="bg-val-red/10 text-val-red px-4 py-1 rounded text-xs font-bold uppercase tracking-widest">
                        {data.logs.length} Entries
                    </div>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="bg-white/5 text-[10px] font-black uppercase tracking-[0.2em] text-foreground/40">
                                <th className="px-8 py-5">Week</th>
                                <th className="px-8 py-5">Substitute Player</th>
                                <th className="px-8 py-5">Representing Team</th>
                                <th className="px-8 py-5">Against</th>
                                <th className="px-8 py-5 text-center">ACS</th>
                                <th className="px-8 py-5 text-center">Outcome</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                            {data.logs.map((log, i) => (
                                <tr key={i} className="hover:bg-white/[0.02] transition-colors group">
                                    <td className="px-8 py-5 font-display text-lg font-black text-foreground/20 italic group-hover:text-val-red">
                                        W{log.week}
                                    </td>
                                    <td className="px-8 py-5">
                                        <div className="font-bold text-foreground">{log.playerName}</div>
                                    </td>
                                    <td className="px-8 py-5">
                                        <span className="text-val-blue font-bold uppercase tracking-widest text-xs">{log.teamName}</span>
                                    </td>
                                    <td className="px-8 py-5">
                                        <span className="text-foreground/40 text-sm italic">{log.opponentName}</span>
                                    </td>
                                    <td className="px-8 py-5 text-center font-display font-bold text-lg">
                                        {log.acs}
                                    </td>
                                    <td className="px-8 py-5 text-center">
                                        <span className={`px-4 py-1 rounded text-[10px] font-black uppercase tracking-[0.1em] ${log.result === 'win' ? 'bg-green-500/10 text-green-500 border border-green-500/20' :
                                                'bg-val-red/10 text-val-red border border-val-red/20'
                                            }`}>
                                            {log.result}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </motion.div>
        </div>
    );
}
