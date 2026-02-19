'use client';

import { motion } from 'framer-motion';
import { LeaderboardPlayer } from '@/lib/data';

interface PodiumProps {
    topPlayers: LeaderboardPlayer[];
}

export default function LeaderboardPodium({ topPlayers }: PodiumProps) {
    // Podium order: [2nd, 1st, 3rd]
    const podiumOrder = [
        topPlayers[1], // 2nd
        topPlayers[0], // 1st
        topPlayers[2], // 3rd
    ];

    if (topPlayers.length === 0) return null;

    return (
        <div className="flex flex-col items-center justify-end mb-16 pt-20">
            <div className="flex items-end justify-center gap-4 md:gap-8 w-full max-w-4xl h-[300px] md:h-[400px]">
                {podiumOrder.map((player, index) => {
                    if (!player) return <div key={index} className="flex-1" />;

                    const isFirst = player === topPlayers[0];
                    const isSecond = player === topPlayers[1];
                    const isThird = player === topPlayers[2];

                    const height = isFirst ? 'h-full' : isSecond ? 'h-[75%]' : 'h-[60%]';
                    const color = isFirst ? 'from-val-red to-val-red/40' :
                        isSecond ? 'from-val-blue to-val-blue/40' :
                            'from-foreground/40 to-foreground/10';
                    const delay = isFirst ? 0 : isSecond ? 0.2 : 0.4;

                    return (
                        <motion.div
                            key={player.id}
                            initial={{ opacity: 0, y: 50 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.8, delay, ease: 'easeOut' }}
                            className={`flex flex-col items-center flex-1 h-full`}
                        >
                            {/* Avatar/Name */}
                            <div className="mb-4 text-center">
                                <motion.div
                                    initial={{ scale: 0 }}
                                    animate={{ scale: 1 }}
                                    transition={{ duration: 0.5, delay: delay + 0.5 }}
                                    className={`w-16 h-16 md:w-24 md:h-24 rounded-full bg-val-deep border-4 flex items-center justify-center mb-3 mx-auto shadow-2xl ${isFirst ? 'border-val-red shadow-val-red/20' :
                                            isSecond ? 'border-val-blue shadow-val-blue/20' :
                                                'border-white/20'
                                        }`}
                                >
                                    <span className="font-display text-2xl md:text-4xl font-black italic">
                                        {player.name[0]}
                                    </span>
                                </motion.div>
                                <div className="font-display font-black text-lg md:text-2xl uppercase tracking-tighter truncate max-w-[120px] md:max-w-none">
                                    {player.name}
                                </div>
                                <div className="text-xs md:text-sm font-bold text-foreground/40 uppercase tracking-widest">
                                    ACS {player.avg_acs}
                                </div>
                            </div>

                            {/* Podium Base */}
                            <motion.div
                                className={`w-full ${height} bg-gradient-to-b ${color} rounded-t-xl glass border-x border-t border-white/10 relative shadow-2xl flex items-center justify-center`}
                            >
                                <div className="absolute inset-0 bg-white/5 pointer-events-none" />
                                <span className="font-display text-4xl md:text-8xl font-black italic opacity-20 select-none">
                                    {isFirst ? '1' : isSecond ? '2' : '3'}
                                </span>

                                {isFirst && (
                                    <div className="absolute -top-12 left-1/2 -translate-x-1/2">
                                        <motion.div
                                            animate={{ y: [0, -10, 0], rotate: [0, 5, -5, 0] }}
                                            transition={{ duration: 4, repeat: Infinity }}
                                            className="text-val-red text-4xl"
                                        >
                                            👑
                                        </motion.div>
                                    </div>
                                )}
                            </motion.div>
                        </motion.div>
                    );
                })}
            </div>
        </div>
    );
}
