import { GetServerSideProps } from "next"
import { useMemo, useState } from "react"
import { supabaseServer } from "../lib/supabaseClient"
import { computeStandings, Team, Match } from "../utils/standings"
type Props = { teams: Team[]; matches: Match[] }
export default function Predict({ teams, matches }: Props) {
  const [t1, setT1] = useState<number | null>(null)
  const [t2, setT2] = useState<number | null>(null)
  const standings = useMemo(() => computeStandings(teams, matches), [teams, matches])
  const rankMap = useMemo(() => {
    const m = new Map<number, { points: number; pd: number }>()
    standings.forEach(r => m.set(r.id, { points: r.points, pd: r.pd }))
    return m
  }, [standings])
  let pct = null as null | number
  if (t1 && t2 && t1 !== t2) {
    const a = rankMap.get(t1) || { points: 0, pd: 0 }
    const b = rankMap.get(t2) || { points: 0, pd: 0 }
    const diff = (a.points - b.points) + (a.pd - b.pd)
    const prob = 1 / (1 + Math.exp(-diff / 20))
    pct = prob * 100
  }
  return (
    <main className="min-h-screen p-6">
      <h1 className="text-2xl font-semibold">Match Predictor</h1>
      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block mb-1">Team 1</label>
          <select className="border p-2 w-full" value={t1 ?? ""} onChange={e => setT1(Number(e.target.value || 0) || null)}>
            <option value="">Select</option>
            {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block mb-1">Team 2</label>
          <select className="border p-2 w-full" value={t2 ?? ""} onChange={e => setT2(Number(e.target.value || 0) || null)}>
            <option value="">Select</option>
            {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
      </div>
      <div className="mt-6">
        {pct === null && <div className="text-gray-600">Select two different teams.</div>}
        {pct !== null && (
          <div className="text-lg">
            Win probability for Team 1: <span className="font-semibold">{pct.toFixed(1)}%</span>
          </div>
        )}
      </div>
    </main>
  )
}
export const getServerSideProps: GetServerSideProps<Props> = async () => {
  const { data: teams } = await supabaseServer.from("teams").select("id,name,group_name")
  const { data: matches } = await supabaseServer
    .from("matches")
    .select("id,group_name,t1_id,t2_id,t1_rounds,t2_rounds,status,match_type")
  return { props: { teams: (teams ?? []) as Team[], matches: (matches ?? []) as Match[] } }
}
