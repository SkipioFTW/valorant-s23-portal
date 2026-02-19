import Navbar from "@/components/Navbar";
import { getAllMatches } from "@/lib/data";
import Image from "next/image";

export default async function MatchesPage() {
    const matches = await getAllMatches();

    return (
        <div className="flex flex-col min-h-screen bg-background">
            <Navbar />

            <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-32">
                <header className="mb-12">
                    <h1 className="font-display text-4xl md:text-6xl font-black italic text-val-red uppercase tracking-tighter mb-4">
                        Match Ledger
                    </h1>
                    <p className="text-foreground/60 max-w-2xl font-medium">
                        Complete record of all tournament matches, including scheduled, live, and completed results.
                    </p>
                </header>

                <div className="space-y-8">
                    {/* Groups by Week */}
                    {Object.entries(
                        matches.reduce((acc, match) => {
                            if (!acc[match.week]) acc[match.week] = [];
                            acc[match.week].push(match);
                            return acc;
                        }, {} as Record<number, typeof matches>)
                    ).sort(([a], [b]) => Number(b) - Number(a)).map(([week, weekMatches]) => (
                        <div key={week} className="space-y-4">
                            <div className="flex items-center gap-4">
                                <h2 className="font-display text-2xl font-black text-val-blue uppercase italic">
                                    Week {week}
                                </h2>
                                <div className="h-px flex-1 bg-white/5" />
                            </div>

                            <div className="grid gap-4">
                                {weekMatches.map((match) => (
                                    <div
                                        key={match.id}
                                        className="glass group hover:border-val-red/30 transition-all duration-300 overflow-hidden relative"
                                    >
                                        <div className="flex flex-col md:flex-row items-center gap-6 p-6">
                                            {/* Group Badge */}
                                            <div className="absolute top-0 right-0 px-4 py-1 bg-val-red/10 text-val-red text-[10px] font-black uppercase tracking-[0.2em] rounded-bl-lg border-l border-b border-val-red/20">
                                                {match.group_name}
                                            </div>

                                            {/* Team 1 */}
                                            <div className={`flex-1 flex items-center justify-end gap-6 ${match.winner_id === match.team1.id ? 'opacity-100' : 'opacity-60'}`}>
                                                <div className="text-right">
                                                    <div className="font-display text-xl font-black uppercase tracking-tight">
                                                        {match.team1.name}
                                                    </div>
                                                    <div className="text-[10px] font-bold text-foreground/40 uppercase tracking-widest">
                                                        [{match.team1.tag}]
                                                    </div>
                                                </div>
                                                <div className="relative w-16 h-16 flex-shrink-0 bg-white/5 rounded-sm p-2 group-hover:scale-105 transition-transform duration-300">
                                                    {match.team1.logo ? (
                                                        <Image
                                                            src={match.team1.logo}
                                                            alt={match.team1.name}
                                                            fill
                                                            className="object-contain p-2"
                                                        />
                                                    ) : (
                                                        <div className="w-full h-full flex items-center justify-center font-display text-2xl font-black text-val-red">
                                                            {match.team1.tag}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Score / VS Center */}
                                            <div className="flex flex-col items-center justify-center min-w-[120px] py-4 bg-white/5 rounded-lg border border-white/5">
                                                {match.status === 'completed' ? (
                                                    <div className="flex items-center gap-4 font-display text-4xl font-black italic">
                                                        <span className={match.winner_id === match.team1.id ? 'text-val-blue' : 'text-foreground/40'}>
                                                            {match.team1.score}
                                                        </span>
                                                        <span className="text-foreground/20 text-xl">-</span>
                                                        <span className={match.winner_id === match.team2.id ? 'text-val-blue' : 'text-foreground/40'}>
                                                            {match.team2.score}
                                                        </span>
                                                    </div>
                                                ) : (
                                                    <div className="font-display text-2xl font-black italic text-val-red animate-pulse">
                                                        VS
                                                    </div>
                                                )}
                                                <div className="mt-2 text-[10px] font-black uppercase tracking-[3px] text-foreground/30">
                                                    {match.format}
                                                </div>
                                            </div>

                                            {/* Team 2 */}
                                            <div className={`flex-1 flex items-center gap-6 ${match.winner_id === match.team2.id ? 'opacity-100' : 'opacity-60'}`}>
                                                <div className="relative w-16 h-16 flex-shrink-0 bg-white/5 rounded-sm p-2 group-hover:scale-105 transition-transform duration-300">
                                                    {match.team2.logo ? (
                                                        <Image
                                                            src={match.team2.logo}
                                                            alt={match.team2.name}
                                                            fill
                                                            className="object-contain p-2"
                                                        />
                                                    ) : (
                                                        <div className="w-full h-full flex items-center justify-center font-display text-2xl font-black text-val-red">
                                                            {match.team2.tag}
                                                        </div>
                                                    )}
                                                </div>
                                                <div>
                                                    <div className="font-display text-xl font-black uppercase tracking-tight">
                                                        {match.team2.name}
                                                    </div>
                                                    <div className="text-[10px] font-bold text-foreground/40 uppercase tracking-widest">
                                                        [{match.team2.tag}]
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Map Info Bar */}
                                        <div className="px-6 py-2 bg-white/[0.02] border-t border-white/5 flex items-center justify-between">
                                            <div className="text-[10px] font-bold text-foreground/40 uppercase tracking-widest flex items-center gap-4">
                                                <span className={`w-2 h-2 rounded-full ${match.status === 'completed' ? 'bg-val-blue' : 'bg-val-red animate-pulse'}`} />
                                                {match.status}
                                            </div>
                                            {match.maps_played > 0 && (
                                                <div className="text-[10px] font-bold text-foreground/40 uppercase tracking-widest">
                                                    {match.maps_played} Map{match.maps_played > 1 ? 's' : ''} Played
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}

                    {matches.length === 0 && (
                        <div className="glass p-20 text-center">
                            <h3 className="font-display text-2xl font-black italic text-val-red uppercase mb-4">
                                No matches found
                            </h3>
                            <p className="text-foreground/40">The match ledger is currently empty. Check back later for upcoming fixtures.</p>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
