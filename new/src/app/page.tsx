import Navbar from "@/components/Navbar";
import Link from 'next/link';
import { getGlobalStats } from '@/lib/data';

export default async function Home() {
  const stats = await getGlobalStats();

  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />

      {/* Hero Section */}
      <section className="flex-1 flex flex-col items-center justify-center px-6 pt-32 pb-20 overflow-hidden relative">
        <div className="max-w-5xl w-full text-center relative z-10">
          <h1 className="font-display text-5xl md:text-8xl font-black tracking-tighter uppercase leading-[0.9] mb-6">
            <span className="block italic text-val-red opacity-80 mb-2 text-2xl md:text-4xl tracking-widest">
              Tournament Portal
            </span>
            <span className="block drop-shadow-[0_0_30px_rgba(255,70,85,0.3)]">
              Season 23
            </span>
            <span className="block text-val-blue drop-shadow-[0_0_30px_rgba(63,209,255,0.3)]">
              Leaderboards
            </span>
          </h1>

          <p className="max-w-2xl mx-auto text-foreground/60 text-lg md:text-xl mb-10 font-medium font-sans">
            Track your progress, analyze match statistics, and dominate the competition in the most advanced Valorant tournament portal.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link href="/standings" className="px-8 py-4 bg-val-red hover:bg-val-red/90 text-white font-bold uppercase tracking-widest rounded-sm transition-all duration-300 transform hover:scale-105 active:scale-95 shadow-[0_0_20px_rgba(255,70,85,0.4)]">
              View Standings
            </Link>
            <Link href="/matches" className="px-8 py-4 glass hover:bg-white/10 text-foreground font-bold uppercase tracking-widest rounded-sm transition-all duration-300 transform hover:scale-105 active:scale-95">
              Explore Matches
            </Link>
          </div>
        </div>

        {/* 3D Placeholder / Abstract Element */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80vw] h-[80vw] max-w-4xl max-h-4xl -z-10 opacity-20 pointer-events-none">
          <div className="w-full h-full animate-[spin_60s_linear_infinite] border-[1px] border-val-red/30 rounded-full flex items-center justify-center">
            <div className="w-[80%] h-[80%] animate-[spin_40s_linear_infinite_reverse] border-[1px] border-val-blue/20 rounded-full" />
          </div>
        </div>
      </section>

      {/* Stats Quick View Footer */}
      <footer className="w-full py-10 glass border-t border-white/5 relative z-20">
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8">
          {[
            { label: "Active Teams", value: stats.activeTeams.toString() },
            { label: "Matches Played", value: stats.matchesPlayed.toString() },
            { label: "Live Players", value: stats.livePlayers.toLocaleString() },
            { label: "Total Points", value: stats.totalPoints >= 1000 ? (stats.totalPoints / 1000).toFixed(1) + 'k' : stats.totalPoints.toString() },
          ].map((stat) => (
            <div key={stat.label} className="text-center group">
              <div className="font-display text-3xl md:text-4xl font-black text-val-red mb-1 group-hover:scale-110 transition-transform duration-300">
                {stat.value}
              </div>
              <div className="text-foreground/40 text-xs font-bold uppercase tracking-widest font-sans">
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      </footer>
    </div>
  );
}
