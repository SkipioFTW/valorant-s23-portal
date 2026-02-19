import Navbar from "@/components/Navbar";
import { getPlayoffMatches } from "@/lib/data";
import Image from "next/image";

export default async function PlayoffsPage() {
    const matches = await getPlayoffMatches();

    const rounds = [
        { id: 1, name: "Round of 24", slots: 8 },
        { id: 2, name: "Round of 16", slots: 8 },
        { id: 3, name: "Quarter-finals", slots: 4 },
        { id: 4, name: "Semi-finals", slots: 2 },
        { id: 5, name: "Grand Final", slots: 1 }
    ];

    const getMatchAt = (roundId: number, pos: number) => {
        return matches.find(m => m.playoff_round === roundId && m.bracket_pos === pos);
    };

    return (
        <div className="flex flex-col min-h-screen bg-background">
            <Navbar />

            <main className="flex-1 w-full px-6 py-32 overflow-x-auto">
                <header className="max-w-7xl mx-auto w-full mb-12">
                    <h1 className="font-display text-4xl md:text-6xl font-black italic text-val-red uppercase tracking-tighter mb-4 text-center">
                        Championship Brackets
                    </h1>
                    <p className="text-foreground/60 max-w-2xl mx-auto font-medium text-center">
                        The ultimate battle for glory. Track the progression of the top teams as they fight through the elimination rounds.
                    </p>
                </header>

                <div className="min-w-[1200px] flex justify-between gap-8 px-4">
                    {rounds.map((round) => (
                        <div key={round.id} className="flex-1 flex flex-col">
                            <h2 className="font-display text-lg font-black text-val-blue uppercase italic text-center mb-8 tracking-widest">
                                {round.name}
                            </h2>

                            <div className="flex-1 flex flex-col justify-around gap-4">
                                {Array.from({ length: round.slots }).map((_, idx) => {
                                    const pos = idx + 1;
                                    const match = getMatchAt(round.id, pos);

                                    return (
                                        <div
                                            key={`${round.id}-${pos}`}
                                            className={`relative group ${match ? 'opacity-100' : 'opacity-30'}`}
                                        >
                                            <div className="glass border-white/5 p-3 rounded-sm transition-all duration-300 group-hover:border-val-red/30 group-hover:bg-white/[0.05]">
                                                {/* Team 1 */}
                                                <div className="flex items-center justify-between mb-2">
                                                    <div className="flex items-center gap-3">
                                                        <div className="w-8 h-8 bg-white/5 rounded-sm p-1 relative">
                                                            {match?.team1.logo && (
                                                                <Image src={match.team1.logo} alt="" fill className="object-contain" />
                                                            )}
                                                        </div>
                                                        <span className={`text-xs font-black uppercase tracking-tight ${match?.winner_id === match?.team1.id ? 'text-val-blue' : 'text-foreground/60'}`}>
                                                            {match?.team1.name || "TBD"}
                                                        </span>
                                                    </div>
                                                    <span className="font-display font-black text-sm italic">
                                                        {match?.status === 'completed' ? match.team1.score : '-'}
                                                    </span>
                                                </div>

                                                {/* Divider */}
                                                <div className="h-px bg-white/5 mb-2" />

                                                {/* Team 2 */}
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-3">
                                                        <div className="w-8 h-8 bg-white/5 rounded-sm p-1 relative">
                                                            {match?.team2.logo && (
                                                                <Image src={match.team2.logo} alt="" fill className="object-contain" />
                                                            )}
                                                        </div>
                                                        <span className={`text-xs font-black uppercase tracking-tight ${match?.winner_id === match?.team2.id ? 'text-val-blue' : 'text-foreground/60'}`}>
                                                            {match?.team2.name || "TBD"}
                                                        </span>
                                                    </div>
                                                    <span className="font-display font-black text-sm italic">
                                                        {match?.status === 'completed' ? match.team2.score : '-'}
                                                    </span>
                                                </div>

                                                {/* Match Footer */}
                                                <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-between">
                                                    <span className="text-[8px] font-black uppercase tracking-widest text-foreground/20">
                                                        {match?.format || 'BO3'}
                                                    </span>
                                                    <span className={`text-[8px] font-black uppercase tracking-widest ${match?.status === 'live' ? 'text-val-red animate-pulse' : 'text-foreground/20'}`}>
                                                        {match?.status || 'SCHEDULED'}
                                                    </span>
                                                </div>
                                            </div>

                                            {/* Connector Lines (Simplistic Visual Guides) */}
                                            {round.id < 5 && (
                                                <div className="absolute -right-4 top-1/2 w-4 h-px bg-white/10" />
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    ))}
                </div>
            </main>
        </div>
    );
}
