import { GetServerSideProps } from "next"
import { supabaseServer } from "../lib/supabaseClient"
import Link from "next/link"
import { computeStandings, Team as TTeam, Match as TMatch, MapRow } from "../utils/standings"
type Team = { id: number; name: string; group_name: string }
type Props = { teams: Team[]; metrics: Record<number, { points: number; pd: number }> }
export default function Teams({ teams, metrics }: Props) {
  return (
    <main className="min-h-screen p-6">
      <h1 className="text-2xl font-semibold">Teams</h1>
      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {teams.map(t => (
          <Link key={t.id} href={`/teams/${t.id}`} className="card p-3">
            <div className="font-semibold">{t.name}</div>
            <div className="text-sm text-textDim">Group {t.group_name}</div>
            <div className="text-sm">Pts {metrics[t.id]?.points ?? 0} • PD {metrics[t.id]?.pd ?? 0}</div>
          </Link>
        ))}
      </div>
    </main>
  )
}
export const getServerSideProps: GetServerSideProps<Props> = async () => {
  const { data: teams } = await supabaseServer.from("teams").select("id,name,group_name")
  const { data: matches } = await supabaseServer
    .from("matches")
    .select("id,team1_id,team2_id,match_type,status,week,format,score_t1,score_t2,maps_played,is_forfeit")
  const ids = (matches ?? []).map(m => m.id)
  const { data: maps } = ids.length
    ? await supabaseServer.from("match_maps").select("match_id,team1_rounds,team2_rounds").in("match_id", ids)
    : { data: [] }
  const rows = computeStandings((teams ?? []) as TTeam[], (matches ?? []) as TMatch[], (maps ?? []) as MapRow[])
  const metrics: Record<number, { points: number; pd: number }> = {}
  rows.forEach(r => { metrics[r.id] = { points: r.points, pd: r.pd } })
  return { props: { teams: teams ?? [], metrics } }
}
