import { GetServerSideProps } from "next"
import { supabaseServer } from "../lib/supabaseClient"
import SectionHeader from "../components/SectionHeader"
type Row = { week: number | null; player_name: string; team_name: string }
type Props = { total: number; topTeam: string; rows: Row[] }
export default function Substitutions({ total, topTeam, rows }: Props) {
  return (
    <main className="min-h-screen p-6">
      <SectionHeader title="Substitutions Log" subtitle="Summary and detailed entries" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-4">
          <div className="text-xs text-textDim">Total Subs</div>
          <div className="brand-title text-2xl">{total}</div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-textDim">Most Active Team</div>
          <div className="brand-title text-2xl">{topTeam || "N/A"}</div>
        </div>
      </div>
      <div className="mt-6 card p-2 overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr>
              <th className="p-2 text-left text-textDim">Player</th>
              <th className="p-2 text-left text-textDim">Team</th>
              <th className="p-2 text-textDim">Week</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-primaryBlue/10">
                <td className="p-2">{r.player_name}</td>
                <td className="p-2">{r.team_name}</td>
                <td className="p-2 text-center">{r.week ?? "-"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td className="p-2" colSpan={3}>No substitutions recorded</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  )
}
export const getServerSideProps: GetServerSideProps<Props> = async () => {
  const { data: subs } = await supabaseServer
    .from("match_stats_map")
    .select("match_id,team_id,player_id,is_sub")
    .eq("is_sub", 1)
  const { data: players } = await supabaseServer.from("players").select("id,name")
  const { data: teams } = await supabaseServer.from("teams").select("id,name")
  const { data: matches } = await supabaseServer.from("matches").select("id,week")
  const pmap = new Map<number, string>(); (players ?? []).forEach(p => pmap.set(p.id, p.name))
  const tmap = new Map<number, string>(); (teams ?? []).forEach(t => tmap.set(t.id, t.name))
  const wmap = new Map<number, number | null>(); (matches ?? []).forEach(m => wmap.set(m.id, m.week))
  const rows: Row[] = (subs ?? []).map(s => ({
    week: wmap.get(s.match_id) ?? null,
    player_name: pmap.get(s.player_id) || String(s.player_id),
    team_name: tmap.get(s.team_id) || ""
  }))
  const tcount = new Map<string, number>()
  rows.forEach(r => tcount.set(r.team_name, (tcount.get(r.team_name) || 0) + 1))
  let topTeam = ""; let max = 0
  tcount.forEach((v, k) => { if (v > max) { max = v; topTeam = k } })
  return { props: { total: rows.length, topTeam, rows } }
}
