import Link from "next/link"
import { useRouter } from "next/router"
import { PropsWithChildren } from "react"
export default function Layout({ children }: PropsWithChildren) {
  const r = useRouter()
  return (
    <div className="min-h-screen">
      <header className="border-b border-primaryBlue/20 bg-bgDark">
        <div className="mx-auto max-w-6xl p-4 flex items-center justify-between">
          <Link href="/" className="brand-title text-xl text-primaryBlue">VALORANT S23 • PORTAL</Link>
          <nav className="flex gap-4 text-sm">
            <Link href="/standings" className="text-primaryBlue">Standings</Link>
            <Link href="/matches" className="text-primaryBlue">Matches</Link>
            <Link href="/playoffs" className="text-primaryBlue">Playoffs</Link>
            <Link href="/stats" className="text-primaryBlue">Stats</Link>
            <Link href="/substitutions" className="text-primaryBlue">Substitutions</Link>
            <Link href="/leaderboard" className="text-primaryBlue">Leaderboard</Link>
            <Link href="/players" className="text-primaryBlue">Players</Link>
            <Link href="/teams" className="text-primaryBlue">Teams</Link>
            <Link href="/predict" className="text-primaryBlue">Predictor</Link>
            <Link href="/search" className="text-primaryRed">Search</Link>
          </nav>
          <button className="card px-3 py-1 rounded border border-primaryRed text-primaryRed" onClick={() => r.back()}>Back</button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl p-6">{children}</main>
      <footer className="border-t border-primaryBlue/20 text-sm text-textDim">
        <div className="mx-auto max-w-6xl p-4">© S23 Portal · New Stack</div>
      </footer>
    </div>
  )
}
