import Navbar from '@/components/Navbar';
import SubstitutionView from '@/components/SubstitutionView';
import { getSubstitutionAnalytics } from '@/lib/data';

export const revalidate = 900; // Revalidate every 15 minutes

export default async function SubstitutionsPage() {
    const analytics = await getSubstitutionAnalytics();

    return (
        <div className="min-h-screen">
            <Navbar />

            <main className="max-w-7xl mx-auto px-6 pt-32 pb-20">
                <div className="mb-12">
                    <h1 className="font-display text-4xl md:text-6xl font-black uppercase tracking-tighter mb-3 animate-slide-in">
                        Substitution <span className="text-val-yellow">Analytics</span>
                    </h1>
                    <p className="text-foreground/60 text-lg max-w-2xl">
                        Identify the impact of substitutes on team performance, win rates, and individual contributions across the league.
                    </p>
                </div>

                {analytics.teamStats.length > 0 ? (
                    <SubstitutionView data={analytics} />
                ) : (
                    <div className="glass rounded-xl p-12 border border-white/5 text-center">
                        <div className="w-16 h-16 mx-auto mb-4 bg-white/5 rounded-full flex items-center justify-center">
                            <svg className="w-8 h-8 text-foreground/20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                        <h3 className="text-xl font-bold mb-2">No Substitution Data</h3>
                        <p className="text-foreground/60">We couldn't find any substitution records in the database.</p>
                    </div>
                )}
            </main>
        </div>
    );
}
