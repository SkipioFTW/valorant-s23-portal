export type Team = { id: number; name: string; group_name: string }
export type Match = {
  id: number
  team1_id: number
  team2_id: number
  match_type: string
  status: string
  week?: number | null
  format?: string | null
  score_t1?: number | null
  score_t2?: number | null
  maps_played?: number | null
  is_forfeit?: number | null
}
export type MapRow = { match_id: number; team1_rounds: number | null; team2_rounds: number | null }
export type StandingRow = {
  id: number
  name: string
  group_name: string
  played: number
  wins: number
  losses: number
  points: number
  pd: number
  remaining: number
  eliminated: boolean
}
export function computeStandings(teams: Team[], matches: Match[], maps: MapRow[]): StandingRow[] {
  const byTeam: Record<number, StandingRow> = {}
  teams.forEach(t => {
    byTeam[t.id] = {
      id: t.id,
      name: t.name,
      group_name: t.group_name,
      played: 0,
      wins: 0,
      losses: 0,
      points: 0,
      pd: 0,
      remaining: 0,
      eliminated: false
    }
  })
  const regs = matches.filter(m => (m.match_type || "").toLowerCase() === "regular")
  const roundAgg = new Map<number, { t1: number; t2: number }>()
  maps.forEach(row => {
    const cur = roundAgg.get(row.match_id) || { t1: 0, t2: 0 }
    cur.t1 += row.team1_rounds || 0
    cur.t2 += row.team2_rounds || 0
    roundAgg.set(row.match_id, cur)
  })
  regs.forEach(m => {
    const t1 = byTeam[m.team1_id]
    const t2 = byTeam[m.team2_id]
    if (!t1 || !t2) return
    const status = (m.status || "").toLowerCase()
    const agg = roundAgg.get(m.id) || { t1: 0, t2: 0 }
    const score_t1 = (agg.t1 || 0) > 0 ? agg.t1 : (m.score_t1 || 0)
    const score_t2 = (agg.t2 || 0) > 0 ? agg.t2 : (m.score_t2 || 0)
    const maps_played = m.maps_played || 0
    const is_forfeit = m.is_forfeit || 0
    const played = status === "completed" || (score_t1 + score_t2) > 0 || maps_played > 0 || is_forfeit === 1
    if (played) {
      t1.played += 1
      t2.played += 1
      const p1 = score_t1 > score_t2 ? 15 : Math.min(score_t1, 12)
      const p2 = score_t2 > score_t1 ? 15 : Math.min(score_t2, 12)
      t1.points += p1
      t2.points += p2
      t1.pd += (score_t1 - score_t2)
      t2.pd += (score_t2 - score_t1)
      if (score_t1 > score_t2) {
        t1.wins += 1
        t2.losses += 1
      } else if (score_t2 > score_t1) {
        t2.wins += 1
        t1.losses += 1
      }
    } else {
      t1.remaining += 1
      t2.remaining += 1
    }
  })
  const rows = Object.values(byTeam)
  const sorted = rows.sort((a, b) => {
    if (b.points !== a.points) return b.points - a.points
    return b.pd - a.pd
  })
  const sixth = sorted[5]?.points ?? 0
  sorted.forEach(r => {
    const maxGain = r.remaining * 15
    r.eliminated = r.points + maxGain < sixth
  })
  return sorted
}
