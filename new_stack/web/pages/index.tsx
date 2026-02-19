import Link from "next/link"
import { GetServerSideProps } from "next"
import { supabaseServer } from "../lib/supabaseClient"
import { listMatchAssets } from "../lib/githubAssets"
import SectionHeader from "../components/SectionHeader"
import StatCard from "../components/StatCard"
type Props = { stats: { teams: number; players: number; matchesAssets: number } }
export default function Home({ stats }: Props) {
  return (
    <main className="min-h-screen">
      <div className="card p-8 border border-primaryBlue/30">
        <h1 className="brand-title text-3xl text-primaryBlue">Valorant S23 Portal</h1>
        <div className="text-textDim mt-2">New stack app focusing on visitor features</div>
      </div>
      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Teams" value={stats.teams} accent="blue" />
        <StatCard label="Players" value={stats.players} accent="blue" />
        <StatCard label="GitHub Match JSON" value={stats.matchesAssets} accent="red" />
      </div>
      <SectionHeader title="Explore" />
      <div className="grid gap-3">
        <Link className="text-blue-600" href="/standings">Standings</Link>
        <Link className="text-blue-600" href="/matches">Matches</Link>
        <Link className="text-blue-600" href="/playoffs">Playoffs</Link>
        <Link className="text-blue-600" href="/leaderboard">Leaderboard</Link>
        <Link className="text-blue-600" href="/players">Players</Link>
        <Link className="text-blue-600" href="/teams">Teams</Link>
        <Link className="text-blue-600" href="/predict">Predictor</Link>
      </div>
    </main>
  )
}
export const getServerSideProps: GetServerSideProps<Props> = async () => {
  const { data: t } = await supabaseServer.from("teams").select("id", { count: "exact", head: true })
  const { data: p } = await supabaseServer.from("players").select("id", { count: "exact", head: true })
  let assetsCount = 0
  try {
    const assets = await listMatchAssets()
    assetsCount = assets.length
  } catch {
    assetsCount = 0
  }
  return { props: { stats: { teams: t?.length ?? 0, players: p?.length ?? 0, matchesAssets: assetsCount } } }
}
