'use client';

import { useState } from 'react';
import { LeaderboardPlayer } from '@/lib/data';
import LeaderboardPodium from './LeaderboardPodium';

export default function LeaderboardFilters({
    players,
}: {
    players: LeaderboardPlayer[];
}) {
    const [minGames, setMinGames] = useState(0);

    const filteredPlayers = players.filter((p) => p.matches_played >= minGames);
    const topThree = filteredPlayers.slice(0, 3);

    return (
        <div>
            {/* Podium Section */}
            <LeaderboardPodium topPlayers={topThree} />

            {/* Filter Controls */}
            <div className="mb-8 glass rounded-xl p-6 border border-white/5">
                <div className="flex flex-col md:flex-row md:items-center gap-4">
                    <label className="text-sm font-bold uppercase tracking-wider text-foreground/60">
                        Minimum Games:
                    </label>
                    <input
                        type="range"
                        min="0"
                        max="10"
                        value={minGames}
                        onChange={(e) => setMinGames(parseInt(e.target.value))}
                        className="flex-1 accent-val-red"
                    />
                    <span className="font-display text-xl font-bold text-val-red min-w-[3rem] text-center">
                        {minGames}
                    </span>
                </div>
                <div className="mt-2 text-xs text-foreground/40">
                    Showing {filteredPlayers.length} of {players.length} players
                </div>
            </div>

            {/* Desktop Table */}
            <div className="hidden md:block glass rounded-xl overflow-hidden border border-white/5">
                <table className="w-full">
                    <thead className="bg-val-deep/50 border-b border-white/10">
                        <tr>
                            <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-foreground/60">
                                Rank
                            </th>
                            <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-foreground/60">
                                Player
                            </th>
                            <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-foreground/60">
                                Team
                            </th>
                            <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-foreground/60">
                                Matches
                            </th>
                            <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-foreground/60">
                                Avg ACS
                            </th>
                            <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-foreground/60">
                                K
                            </th>
                            <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-foreground/60">
                                D
                            </th>
                            <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-foreground/60">
                                A
                            </th>
                            <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-foreground/60">
                                K/D
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {filteredPlayers.map((player, index) => (
                            <tr
                                key={player.id}
                                className="border-b border-white/5 hover:bg-white/5 transition-colors duration-200"
                            >
                                <td className="px-6 py-4">
                                    <div className="font-display text-xl font-bold text-val-blue">
                                        #{index + 1}
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    <div>
                                        <div className="font-bold text-foreground">{player.name}</div>
                                        <div className="text-xs text-foreground/40">{player.riot_id}</div>
                                    </div>
                                </td>
                                <td className="px-6 py-4 text-center">
                                    <span className="inline-block px-3 py-1 rounded-full bg-val-red/10 text-val-red text-xs font-bold uppercase tracking-wider">
                                        {player.team}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-center text-foreground/60">
                                    {player.matches_played}
                                </td>
                                <td className="px-6 py-4 text-center font-display text-lg font-black text-val-blue">
                                    {player.avg_acs}
                                </td>
                                <td className="px-6 py-4 text-center font-bold text-foreground">
                                    {player.total_kills}
                                </td>
                                <td className="px-6 py-4 text-center font-bold text-val-red/60">
                                    {player.total_deaths}
                                </td>
                                <td className="px-6 py-4 text-center font-bold text-foreground/60">
                                    {player.total_assists}
                                </td>
                                <td className={`px-6 py-4 text-center font-bold ${player.kd_ratio >= 1 ? 'text-val-blue' : 'text-val-red/60'}`}>
                                    {player.kd_ratio.toFixed(2)}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Mobile Cards */}
            <div className="md:hidden space-y-4">
                {filteredPlayers.map((player, index) => (
                    <div
                        key={player.id}
                        className="glass rounded-xl p-5 border border-white/5"
                    >
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-3">
                                <div className="font-display text-2xl font-bold text-val-blue">
                                    #{index + 1}
                                </div>
                                <div>
                                    <div className="font-bold text-foreground">{player.name}</div>
                                    <div className="text-xs text-foreground/40">{player.riot_id}</div>
                                </div>
                            </div>
                            <span className="inline-block px-3 py-1 rounded-full bg-val-red/10 text-val-red text-xs font-bold uppercase tracking-wider">
                                {player.team}
                            </span>
                        </div>

                        <div className="flex items-center justify-between mb-3">
                            <div className="text-xs text-foreground/40 uppercase">Avg ACS</div>
                            <div className="font-display text-2xl font-black text-val-blue">
                                {player.avg_acs}
                            </div>
                        </div>

                        <div className="grid grid-cols-4 gap-3 text-center">
                            <div>
                                <div className="text-xs text-foreground/40 uppercase mb-1">K</div>
                                <div className="font-bold text-foreground">{player.total_kills}</div>
                            </div>
                            <div>
                                <div className="text-xs text-foreground/40 uppercase mb-1">D</div>
                                <div className="font-bold text-val-red/60">{player.total_deaths}</div>
                            </div>
                            <div>
                                <div className="text-xs text-foreground/40 uppercase mb-1">A</div>
                                <div className="text-foreground/60">{player.total_assists}</div>
                            </div>
                            <div>
                                <div className="text-xs text-foreground/40 uppercase mb-1">K/D</div>
                                <div className={`font-bold ${player.kd_ratio >= 1 ? 'text-val-blue' : 'text-val-red/60'}`}>
                                    {player.kd_ratio.toFixed(2)}
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
