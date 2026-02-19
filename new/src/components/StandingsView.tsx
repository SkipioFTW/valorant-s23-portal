'use client';

import { useState } from 'react';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';

interface TeamStanding {
    id: number;
    name: string;
    tag: string;
    logo_display: string | null;
    Wins: number;
    Losses: number;
    Played: number;
    Points: number;
    'Points Against': number;
    PD: number;
}

interface Props {
    groupedStandings: Map<string, TeamStanding[]>;
}

const TOTAL_WEEKS = 6;

export default function StandingsView({ groupedStandings }: Props) {
    const groups = Array.from(groupedStandings.entries());
    const [selectedGroup, setSelectedGroup] = useState<string>(groups[0]?.[0] || 'Group A');

    const getQualificationStatus = (rank: number, team: TeamStanding) => {
        const matchesLeft = TOTAL_WEEKS - team.Played;
        const maxPossiblePoints = team.Points + (matchesLeft * 15); // Best case: win all remaining

        // Get the current standings for this group
        const currentGroupStandings = groupedStandings.get(selectedGroup) || [];

        // Check if mathematically eliminated (can't reach 6th place)
        if (rank > 6) {
            const sixthPlacePoints = currentGroupStandings[5]?.Points || 0;
            if (maxPossiblePoints < sixthPlacePoints) {
                return 'eliminated';
            }
        }

        // Top 2: BYE to playoffs
        if (rank <= 2) return 'bye';

        // 3-6: Round of 24
        if (rank >= 3 && rank <= 6) return 'r24';

        return 'none';
    };

    const getRowClassName = (status: string) => {
        switch (status) {
            case 'bye':
                return 'border-l-4 border-green-500 bg-green-500/5';
            case 'r24':
                return 'border-l-4 border-val-blue bg-val-blue/5';
            case 'eliminated':
                return 'border-l-4 border-val-red bg-val-red/5';
            default:
                return '';
        }
    };

    const currentStandings = groupedStandings.get(selectedGroup) || [];

    return (
        <div>
            {/* Group Tabs */}
            <div className="mb-8 flex flex-wrap gap-3">
                {groups.map(([groupName]) => (
                    <button
                        key={groupName}
                        onClick={() => setSelectedGroup(groupName)}
                        className={`px-6 py-3 rounded-lg font-display font-bold uppercase tracking-wider transition-all duration-300 ${selectedGroup === groupName
                                ? 'bg-val-red text-white shadow-[0_0_20px_rgba(255,70,85,0.4)]'
                                : 'glass hover:bg-white/10 text-foreground/60 hover:text-foreground'
                            }`}
                    >
                        {groupName}
                    </button>
                ))}
            </div>

            {/* Legend */}
            <div className="mb-6 flex flex-wrap gap-4 text-sm">
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-green-500 rounded"></div>
                    <span className="text-foreground/60">Top 2: BYE Round</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-val-blue rounded"></div>
                    <span className="text-foreground/60">3rd-6th: Round of 24</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-val-red rounded"></div>
                    <span className="text-foreground/60">Mathematically Eliminated</span>
                </div>
            </div>

            {/* Desktop Table */}
            <AnimatePresence mode="wait">
                <motion.div
                    key={selectedGroup}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    transition={{ duration: 0.3 }}
                    className="hidden md:block glass rounded-xl overflow-hidden border border-white/5"
                >
                    <table className="w-full">
                        <thead className="bg-val-deep/50 border-b border-white/10">
                            <tr>
                                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-foreground/60">
                                    Rank
                                </th>
                                <th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-foreground/60">
                                    Team
                                </th>
                                <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-foreground/60">
                                    W
                                </th>
                                <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-foreground/60">
                                    L
                                </th>
                                <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-foreground/60">
                                    Played
                                </th>
                                <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-foreground/60">
                                    Points
                                </th>
                                <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-foreground/60">
                                    PA
                                </th>
                                <th className="px-6 py-4 text-center text-xs font-bold uppercase tracking-widest text-foreground/60">
                                    PD
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {currentStandings.map((team, index) => {
                                const rank = index + 1;
                                const status = getQualificationStatus(rank, team);
                                return (
                                    <tr
                                        key={team.id}
                                        className={`border-b border-white/5 hover:bg-white/5 transition-colors duration-200 ${getRowClassName(status)}`}
                                    >
                                        <td className="px-6 py-4">
                                            <div className="font-display text-xl font-bold text-val-red">
                                                #{rank}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                {team.logo_display && (
                                                    <div className="relative w-10 h-10 rounded-lg overflow-hidden bg-val-deep/50">
                                                        <Image
                                                            src={team.logo_display}
                                                            alt={team.name}
                                                            fill
                                                            className="object-contain"
                                                            unoptimized
                                                        />
                                                    </div>
                                                )}
                                                <div>
                                                    <div className="font-bold text-foreground">{team.name}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-center font-bold text-val-blue">
                                            {team.Wins}
                                        </td>
                                        <td className="px-6 py-4 text-center font-bold text-val-red/60">
                                            {team.Losses}
                                        </td>
                                        <td className="px-6 py-4 text-center text-foreground/60">
                                            {team.Played}
                                        </td>
                                        <td className="px-6 py-4 text-center font-display text-lg font-black text-val-red">
                                            {team.Points}
                                        </td>
                                        <td className="px-6 py-4 text-center text-foreground/60">
                                            {team['Points Against']}
                                        </td>
                                        <td className={`px-6 py-4 text-center font-bold ${team.PD >= 0 ? 'text-val-blue' : 'text-val-red/60'}`}>
                                            {team.PD > 0 ? '+' : ''}{team.PD}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </motion.div>
            </AnimatePresence>

            {/* Mobile Cards */}
            <AnimatePresence mode="wait">
                <motion.div
                    key={selectedGroup}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    transition={{ duration: 0.3 }}
                    className="md:hidden space-y-4"
                >
                    {currentStandings.map((team, index) => {
                        const rank = index + 1;
                        const status = getQualificationStatus(rank, team);
                        return (
                            <div
                                key={team.id}
                                className={`glass rounded-xl p-5 border border-white/5 ${getRowClassName(status)}`}
                            >
                                <div className="flex items-center justify-between mb-4">
                                    <div className="flex items-center gap-3">
                                        <div className="font-display text-2xl font-bold text-val-red">
                                            #{rank}
                                        </div>
                                        {team.logo_display && (
                                            <div className="relative w-12 h-12 rounded-lg overflow-hidden bg-val-deep/50">
                                                <Image
                                                    src={team.logo_display}
                                                    alt={team.name}
                                                    fill
                                                    className="object-contain"
                                                    unoptimized
                                                />
                                            </div>
                                        )}
                                        <div>
                                            <div className="font-bold text-foreground">{team.name}</div>
                                        </div>
                                    </div>
                                    <div className="font-display text-2xl font-black text-val-red">
                                        {team.Points}
                                    </div>
                                </div>

                                <div className="grid grid-cols-4 gap-3 text-center">
                                    <div>
                                        <div className="text-xs text-foreground/40 uppercase mb-1">W</div>
                                        <div className="font-bold text-val-blue">{team.Wins}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-foreground/40 uppercase mb-1">L</div>
                                        <div className="font-bold text-val-red/60">{team.Losses}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-foreground/40 uppercase mb-1">PA</div>
                                        <div className="text-foreground/60">{team['Points Against']}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-foreground/40 uppercase mb-1">PD</div>
                                        <div className={`font-bold ${team.PD >= 0 ? 'text-val-blue' : 'text-val-red/60'}`}>
                                            {team.PD > 0 ? '+' : ''}{team.PD}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </motion.div>
            </AnimatePresence>
        </div>
    );
}
