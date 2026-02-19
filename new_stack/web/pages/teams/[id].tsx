import { GetServerSideProps } from "next"
import { supabaseServer } from "../../lib/supabaseClient"
import SectionHeader from "../../components/SectionHeader"
import StatCard from "../../components/StatCard"
type Team = { id: number; name: string; group_name: string | null }
type Player = { id: number; name: string; riot_id: string | null }
type Props = {
  team: Team | null
  metrics: { played: number; wins: number; losses: number; points: number; pd: number; avg_acs: number; kd_ratio: number }
  roster: Player[]
  recent: Array<{ id: number; opponent: string; score_t1: number; score_t2: number; status: string }>
}
export default function TeamDetail({ team, metrics, roster, recent }: Props) {
  if (!team) return <main className="min-h-screen p-6">Team not found</main>
  return (
    <main className="min-h-screen p-6">
      <SectionHeader title={team.name} subtitle={`Group ${team.group_name || "-"}`} />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Played" value={metrics.played} />
        <StatCard label="Wins" value={metrics.wins} accent="blue" />
        <StatCard label="Losses" value={metrics.losses} accent="red" />
        <StatCard label="Points" value={metrics.points} accent="blue" />
        <StatCard label="PD" value={metrics.pd} />
        <StatCard label="Avg ACS" value={metrics.avg_acs.toFixed(1)} />
      </div>
      <SectionHeader title="Roster" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {roster.map(p => (
          <div key={p.id} className="card p-3">
            <div className="font-semibold">{p.name}</div>
            <div className="text-sm text-textDim">{p.riot_id ? `(${p.riot_id})` : ""}</div>
          </div>
        ))}
        {roster.length === 0 && <div className="text-textDim">No players on roster</div>}
      </div>
      <SectionHeader title="Recent Matches" />
      <div className="card p-2 overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr>
              <th className="p-2 text-left text-textDim">Opponent</th>
              <th className="p-2 text-textDim">Score</th>
              <th className="p-2 text-textDim">Status</th>
            </tr>
          </thead>
          <tbody>
            {recent.map(m => (
              <tr key={m.id} className="border-b border-primaryBlue/10">
                <td className="p-2">{m.opponent}</td>
                <td className="p-2 text-center">{m.score_t1} - {m.score_t2}</td>
                <td className="p-2 text-center">{m.status}</td>
              </tr>
            ))}
            {recent.length === 0 && (
              <tr><td className="p-2" colSpan={3}>No recent matches</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  )
}
export const getServerSideProps: GetServerSideProps<Props> = async (ctx) => {
  const id = Number(ctx.params?.id)
  const { data: tarr } = await supabaseServer.from("teams").select("id,name,group_name").eq("id", id).limit(1)
  const team = (tarr && tarr[0]) || null
  if (!team) return { props: { team: null, metrics: { played: 0, wins: 0, losses: 0, points: 0, pd: 0, avg_acs: 0, kd_ratio: 0 }, roster: [], recent: [] } }
  const { data: matches } = await supabaseServer
    .from("matches")
    .select("id,team1_id,team2_id,score_t1,score_t2,status")
    .or(`team1_id.eq.${id},team2_id.eq.${id}`)
  let played = 0, wins = 0, losses = 0, points = 0, pd = 0
  ;(matches ?? []).forEach(m => {
    const ours = m.team1_id === id
    const s1 = m.score_t1 || 0
    const s2 = m.score_t2 || 0
    const my = ours ? s1 : s2
    const op = ours ? s2 : s1
    const completed = (m.status || "").toLowerCase() === "completed"
    const playedMask = completed || (s1 + s2) > 0
    if (playedMask) {
      played += 1
      const p = my > op ? 15 : Math.min(my, 12)
      points += p
      pd += (my - op)
      if (my > op) wins += 1
      else if (op > my) losses += 1
    }
  })
  const { data: roster } = await supabaseServer.from("players").select("id,name,riot_id").eq("default_team_id", id)
  const { data: stats } = await supabaseServer
    .from("match_stats_map")
    .select("team_id,acs,kills,deaths")
    .eq("team_id", id)
  let acsSum = 0, acsCnt = 0, ksum = 0, dsum = 0
  ;(stats ?? []).forEach(s => { acsSum += s.acs || 0; acsCnt += 1; ksum += s.kills || 0; dsum += s.deaths || 0 })
  const avg_acs = acsCnt ? acsSum / acsCnt : 0
  const kd_ratio = dsum > 0 ? ksum / dsum : ksum
  const oppNames = new Map<number, string>()
  const teamIds = new Set<number>(); (matches ?? []).forEach(m => { if (m.team1_id !== id) teamIds.add(m.team1_id); if (m.team2_id !== id) teamIds.add(m.team2_id) })
  const { data: others } = teamIds.size ? await supabaseServer.from("teams").select("id,name").in("id", Array.from(teamIds)) : { data: [] }
  ;(others ?? []).forEach(t => oppNames.set(t.id, t.name))
  const recent = (matches ?? []).slice(-5).map(m => {
    const ours = m.team1_id === id
    const oppId = ours ? m.team2_id : m.team1_id
    return { id: m.id, opponent: oppNames.get(oppId) || String(oppId), score_t1: m.score_t1 || 0, score_t2: m.score_t2 || 0, status: m.status || "" }
  })
  return { props: { team, metrics: { played, wins, losses, points, pd, avg_acs, kd_ratio }, roster: roster ?? [], recent } }
}
