import { GetServerSideProps } from "next"
import { supabaseServer } from "../lib/supabaseClient"
import SectionHeader from "../components/SectionHeader"
type TeamAgg = { team_name: string; subs: number }
type WeekAgg = { week: number; subs: number }
type Props = { teamAgg: TeamAgg[]; weekAgg: WeekAgg[] }
export default function Stats({ teamAgg, weekAgg }: Props) {
  return (
    <main className="min-h-screen p-6">
      <SectionHeader title="Stats" subtitle="Substitutions aggregates" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card p-4">
          <div className="brand-title text-xl text-primaryBlue">Subs by Team</div>
          <div className="mt-2 overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr>
                  <th className="p-2 text-left text-textDim">Team</th>
                  <th className="p-2 text-textDim">Subs</th>
                </tr>
              </thead>
              <tbody>
                {teamAgg.map((r, i) => (
                  <tr key={i} className="border-b border-primaryBlue/10">
                    <td className="p-2">{r.team_name}</td>
                    <td className="p-2 text-center">{r.subs}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="card p-4">
          <div className="brand-title text-xl text-primaryRed">Subs per Week</div>
          <div className="mt-2 overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr>
                  <th className="p-2 text-left text-textDim">Week</th>
                  <th className="p-2 text-textDim">Subs</th>
                </tr>
              </thead>
              <tbody>
                {weekAgg.map((r, i) => (
                  <tr key={i} className="border-b border-primaryBlue/10">
                    <td className="p-2">{r.week}</td>
                    <td className="p-2 text-center">{r.subs}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  )
}
export const getServerSideProps: GetServerSideProps<Props> = async () => {
  const { data: subs } = await supabaseServer
    .from("match_stats_map")
    .select("match_id,team_id,is_sub")
    .eq("is_sub", 1)
  const { data: teams } = await supabaseServer.from("teams").select("id,name")
  const { data: matches } = await supabaseServer.from("matches").select("id,week")
  const tmap = new Map<number, string>(); (teams ?? []).forEach(t => tmap.set(t.id, t.name))
  const wmap = new Map<number, number>(); (matches ?? []).forEach(m => wmap.set(m.id, m.week || 0))
  const teamAggMap = new Map<string, number>()
  const weekAggMap = new Map<number, number>()
  ;(subs ?? []).forEach(s => {
    const tn = tmap.get(s.team_id) || ""
    const wk = wmap.get(s.match_id) || 0
    teamAggMap.set(tn, (teamAggMap.get(tn) || 0) + 1)
    weekAggMap.set(wk, (weekAggMap.get(wk) || 0) + 1)
  })
  const teamAgg: TeamAgg[] = Array.from(teamAggMap.entries()).map(([team_name, subs]) => ({ team_name, subs })).sort((a,b) => b.subs - a.subs)
  const weekAgg: WeekAgg[] = Array.from(weekAggMap.entries()).map(([week, subs]) => ({ week, subs })).sort((a,b) => a.week - b.week)
  return { props: { teamAgg, weekAgg } }
}
