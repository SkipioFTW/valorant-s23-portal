import { GetServerSideProps } from "next"
import Link from "next/link"
import { supabaseServer } from "../lib/supabaseClient"
import { listMatchAssets } from "../lib/githubAssets"
import SectionHeader from "../components/SectionHeader"
type Match = {
  id: number
  week: number | null
  group_name?: string | null
  team1_id: number
  team2_id: number
  score_t1?: number | null
  score_t2?: number | null
  status: string
  match_type: string
}
type Team = { id: number; name: string }
type Props = { matches: Match[]; teams: Team[]; assets: Array<{ name: string; download_url: string }> }
export default function Matches({ matches, teams, assets }: Props) {
  const tmap = new Map<number, string>()
  teams.forEach(t => tmap.set(t.id, t.name))
  const regs = matches.filter(m => (m.match_type || "").toLowerCase() === "regular")
  const upcoming = regs.filter(m => m.status !== "completed")
  const completed = regs.filter(m => m.status === "completed")
  return (
    <main className="min-h-screen p-6">
      <SectionHeader title="Regular Season Matches" />
      <section className="mt-6">
        <h2 className="brand-title text-xl text-primaryBlue">GitHub Assets</h2>
        <div className="mt-3 grid gap-2">
          {assets.map(a => (
            <a key={a.name} className="block card p-3 hover:border-primaryBlue" href={a.download_url} target="_blank" rel="noreferrer">
              {a.name}
            </a>
          ))}
          {assets.length === 0 && <div className="text-gray-500">No match JSON assets found</div>}
        </div>
      </section>
      <section className="mt-6">
        <h2 className="brand-title text-xl text-primaryBlue">Upcoming</h2>
        <div className="mt-3 grid gap-2">
          {upcoming.map(m => (
            <Link key={m.id} className="block card p-3 hover:border-primaryBlue" href={`/matches/${m.id}`}>
              <div className="font-semibold">
                {tmap.get(m.team1_id) || m.team1_id} vs {tmap.get(m.team2_id) || m.team2_id}
              </div>
              <div className="text-sm text-gray-600">Week {m.week ?? "?"} • Group {m.group_name ?? "?"}</div>
            </Link>
          ))}
          {upcoming.length === 0 && <div className="text-gray-500">No upcoming matches</div>}
        </div>
      </section>
      <section className="mt-8">
        <h2 className="brand-title text-xl text-primaryBlue">Completed</h2>
        <div className="mt-3 grid gap-2">
          {completed.map(m => (
            <Link key={m.id} className="block card p-3 hover:border-primaryBlue" href={`/matches/${m.id}`}>
              <div className="font-semibold">
                {tmap.get(m.team1_id) || m.team1_id} {m.score_t1 ?? 0} - {m.score_t2 ?? 0} {tmap.get(m.team2_id) || m.team2_id}
              </div>
              <div className="text-sm text-gray-600">Week {m.week ?? "?"} • Group {m.group_name ?? "?"}</div>
            </Link>
          ))}
          {completed.length === 0 && <div className="text-gray-500">No completed matches</div>}
        </div>
      </section>
    </main>
  )
}
export const getServerSideProps: GetServerSideProps<Props> = async () => {
  const { data: matches } = await supabaseServer
    .from("matches")
    .select("id,week,team1_id,team2_id,score_t1,score_t2,status,match_type")
  const { data: teams } = await supabaseServer.from("teams").select("id,name")
  let assets: Array<{ name: string; download_url: string }> = []
  try {
    assets = await listMatchAssets()
  } catch {
    assets = []
  }
  return { props: { matches: matches ?? [], teams: teams ?? [], assets } }
}
