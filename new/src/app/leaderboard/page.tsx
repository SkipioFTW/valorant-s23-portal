import { getLeaderboard } from '@/lib/data';
import Navbar from '@/components/Navbar';
import LeaderboardFilters from '@/components/LeaderboardFilters';

export const revalidate = 900; // Revalidate every 15 minutes

export default async function LeaderboardPage() {
    const leaderboard = await getLeaderboard();

    return (
        <div className="min-h-screen">
            <Navbar />

            <main className="max-w-7xl mx-auto px-6 pt-32 pb-20">
                <div className="mb-12">
                    <h1 className="font-display text-4xl md:text-6xl font-black uppercase tracking-tighter mb-3">
                        Player <span className="text-val-blue">Leaderboard</span>
                    </h1>
                    <p className="text-foreground/60 text-lg">
                        Top performers ranked by Average Combat Score
                    </p>
                </div>

                <LeaderboardFilters players={leaderboard} />
            </main>
        </div>
    );
}
