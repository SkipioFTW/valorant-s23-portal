import { GetServerSideProps } from "next"
import { useState } from "react"
import { supabaseServer } from "../lib/supabaseClient"
import SectionHeader from "../components/SectionHeader"
type Row = {
  player_id: number
  player_name: string
  riot_id?: string | null
  team_name: string
  games: number
  acs: number
  kd: number
  k: number
  d: number
  a: number
}
type Props = { rows: Row[] }
export default function Leaderboard({ rows }: Props) {
  const [minGames, setMinGames] = useState(0)
  const filtered = rows.filter(r => r.games >= minGames)
  return (
    <main className="min-h-screen p-6">
      <SectionHeader title="Leaderboard" subtitle="Min games filter and ACS/KD" />
      <div className="mt-4">
        <label className="mr-2">Minimum Games</label>
        <input
          type="number"
          className="card border border-primaryBlue/30 p-1 w-24"
          value={minGames}
          onChange={e => setMinGames(parseInt(e.target.value || "0"))}
        />
      </div>
      <div className="mt-4 overflow-x-auto card">
        <table className="min-w-full">
          <thead>
            <tr>
              <th className="p-2 text-left text-textDim">Player (Riot ID)</th>
              <th className="p-2 text-left text-textDim">Team</th>
              <th className="p-2 text-textDim">Games</th>
              <th className="p-2 text-textDim">ACS</th>
              <th className="p-2 text-textDim">K/D</th>
              <th className="p-2 text-textDim">K</th>
              <th className="p-2 text-textDim">D</th>
              <th className="p-2 text-textDim">A</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(r => (
              <tr key={r.player_id} className="border-b border-primaryBlue/10">
                <td className="p-2">{r.player_name}{r.riot_id ? ` (${r.riot_id})` : ""}</td>
                <td className="p-2">{r.team_name}</td>
                <td className="p-2 text-center">{r.games}</td>
                <td className="p-2 text-center">{r.acs.toFixed(1)}</td>
                <td className="p-2 text-center">{r.kd.toFixed(2)}</td>
                <td className="p-2 text-center">{r.k}</td>
                <td className="p-2 text-center">{r.d}</td>
                <td className="p-2 text-center">{r.a}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  )
}
export const getServerSideProps: GetServerSideProps<Props> = async () => {
  const { data: stats } = await supabaseServer
    .from("match_stats_map")
    .select("player_id,acs,kills,deaths,assists,match_id")
  const { data: matches } = await supabaseServer
    .from("matches")
    .select("id,status")
  const { data: players } = await supabaseServer
    .from("players")
    .select("id,name,team_id,riot_id")
  const { data: teams } = await supabaseServer
    .from("teams")
    .select("id,name")
  const mstatus = new Map<number, string>()
  ;(matches ?? []).forEach(m => mstatus.set(m.id, m.status))
  const agg = new Map<number, { games: Set<number>; acs: number[]; k: number; d: number; a: number }>()
  ;(stats ?? []).forEach(s => {
    const status = mstatus.get(s.match_id)
    const nz = (s.kills || 0) + (s.deaths || 0) + (s.assists || 0) > 0
    if (status === "completed" || nz) {
      const cur = agg.get(s.player_id) || { games: new Set<number>(), acs: [], k: 0, d: 0, a: 0 }
      cur.games.add(s.match_id)
      cur.acs.push(s.acs || 0)
      cur.k += s.kills || 0
      cur.d += s.deaths || 0
      cur.a += s.assists || 0
      agg.set(s.player_id, cur)
    }
  })
  const pmap = new Map<number, { name: string; team_id: number; riot_id?: string | null }>()
  ;(players ?? []).forEach(p => pmap.set(p.id, { name: p.name, team_id: p.team_id, riot_id: p.riot_id }))
  const tmap = new Map<number, string>()
  ;(teams ?? []).forEach(t => tmap.set(t.id, t.name))
  const rows: Row[] = Array.from(agg.entries()).map(([pid, v]) => {
    const p = pmap.get(pid)
    const tn = p ? tmap.get(p.team_id) || "" : ""
    const acs = v.acs.length ? v.acs.reduce((a, b) => a + b, 0) / v.acs.length : 0
    const kd = v.d > 0 ? v.k / v.d : v.k
    return {
      player_id: pid,
      player_name: p?.name || String(pid),
      riot_id: p?.riot_id || null,
      team_name: tn,
      games: v.games.size,
      acs,
      kd,
      k: v.k,
      d: v.d,
      a: v.a
    }
  })
  rows.sort((a, b) => b.acs - a.acs)
  return { props: { rows } }
}
