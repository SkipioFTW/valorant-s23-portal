import Navbar from '@/components/Navbar';
import PlayerAnalytics from '@/components/PlayerAnalytics';
import { getPlayers } from '@/lib/data';

export const revalidate = 900; // Revalidate every 15 minutes

export default async function PlayersPage({ searchParams }: { searchParams: { player_id?: string } }) {
    const players = await getPlayers();
    const initialId = searchParams?.player_id ? Number(searchParams.player_id) : undefined;

    return (
        <div className="min-h-screen">
            <Navbar />

            <main className="max-w-7xl mx-auto px-6 pt-32 pb-20">
                <div className="mb-12">
                    <h1 className="font-display text-4xl md:text-6xl font-black uppercase tracking-tighter mb-3 animate-slide-in">
                        Player <span className="text-val-red">Statistics</span>
                    </h1>
                    <p className="text-foreground/60 text-lg max-w-2xl">
                        Deep dive into individual performance metrics, agent masteries, and match-by-match analytics.
                    </p>
                </div>

                {players.length > 0 ? (
                    <PlayerAnalytics players={players} initialSelectedId={initialId} />
                ) : (
                    <div className="glass rounded-xl p-12 border border-white/5 text-center">
                        <div className="w-16 h-16 mx-auto mb-4 bg-white/5 rounded-full flex items-center justify-center">
                            <svg className="w-8 h-8 text-foreground/20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                        <h3 className="text-xl font-bold mb-2">No Player Data</h3>
                        <p className="text-foreground/60">We couldn't find any players in the database to analyze.</p>
                    </div>
                )}
            </main>
        </div>
    );
}
