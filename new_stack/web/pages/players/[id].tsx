import { GetServerSideProps } from "next"
import { supabaseServer } from "../../lib/supabaseClient"
import SectionHeader from "../../components/SectionHeader"
import StatCard from "../../components/StatCard"
type Player = { id: number; name: string; team_id: number | null }
type Props = {
  player: Player | null
  metrics: {
    games: number
    avg_acs: number
    kd_ratio: number
    total_kills: number
    total_deaths: number
    total_assists: number
    team_name: string
  }
}
export default function PlayerProfile({ player, metrics }: Props) {
  if (!player) return <main className="min-h-screen p-6">Player not found</main>
  return (
    <main className="min-h-screen p-6">
      <SectionHeader title="Player Profile" />
      <div className="card p-6 border border-primaryBlue/30">
        <div className="brand-title text-2xl text-primaryBlue">{player.name}</div>
        <div className="text-textDim">{metrics.team_name || "Free Agent"}</div>
      </div>
      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Games" value={metrics.games} accent="blue" />
        <StatCard label="Avg ACS" value={metrics.avg_acs.toFixed(1)} accent="blue" />
        <StatCard label="KD Ratio" value={metrics.kd_ratio.toFixed(2)} accent="red" />
      </div>
      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="Kills" value={metrics.total_kills} />
        <StatCard label="Deaths" value={metrics.total_deaths} />
        <StatCard label="Assists" value={metrics.total_assists} />
      </div>
    </main>
  )
}
export const getServerSideProps: GetServerSideProps<Props> = async (ctx) => {
  const id = Number(ctx.params?.id)
  const { data: players } = await supabaseServer.from("players").select("id,name,team_id").eq("id", id).limit(1)
  const player = (players && players[0]) || null
  if (!player) return { props: { player: null, metrics: { games: 0, avg_acs: 0, kd_ratio: 0, total_kills: 0, total_deaths: 0, total_assists: 0, team_name: "" } } }
  const { data: stats } = await supabaseServer
    .from("match_stats_map")
    .select("match_id,acs,kills,deaths,assists")
    .eq("player_id", id)
  const { data: matches } = await supabaseServer.from("matches").select("id,status")
  const mstatus = new Map<number, string>()
  ;(matches ?? []).forEach(m => mstatus.set(m.id, m.status))
  let games = 0
  let acsSum = 0
  let acsCnt = 0
  let tk = 0, td = 0, ta = 0
  const uniqueGames = new Set<number>()
  ;(stats ?? []).forEach(s => {
    const status = mstatus.get(s.match_id)
    const nz = (s.kills || 0) + (s.deaths || 0) + (s.assists || 0) > 0
    if (status === "completed" || nz) {
      uniqueGames.add(s.match_id)
      acsSum += s.acs || 0
      acsCnt += 1
      tk += s.kills || 0
      td += s.deaths || 0
      ta += s.assists || 0
    }
  })
  games = uniqueGames.size
  const avg_acs = acsCnt ? acsSum / acsCnt : 0
  const kd_ratio = td > 0 ? tk / td : tk
  const { data: team } = player.team_id ? await supabaseServer.from("teams").select("name").eq("id", player.team_id).limit(1) : { data: [] }
  const team_name = team && team[0] ? team[0].name : ""
  return { props: { player, metrics: { games, avg_acs, kd_ratio, total_kills: tk, total_deaths: td, total_assists: ta, team_name } } }
}
