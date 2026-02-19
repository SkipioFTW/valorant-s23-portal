import { GetServerSideProps } from "next"
import { supabaseServer } from "../lib/supabaseClient"
import SectionHeader from "../components/SectionHeader"
type PMatch = {
  id: number
  playoff_round: number
  bracket_label: string | null
  t1_id: number
  t2_id: number
  t1_rounds: number | null
  t2_rounds: number | null
}
type Team = { id: number; name: string }
type Props = { rounds: Record<number, PMatch[]>; teams: Team[] }
export default function Playoffs({ rounds, teams }: Props) {
  const tmap = new Map<number, string>()
  teams.forEach(t => tmap.set(t.id, t.name))
  const keys = Object.keys(rounds).map(n => Number(n)).sort((a,b) => a - b)
  return (
    <main className="min-h-screen p-6">
      <SectionHeader title="Playoffs Bracket" />
      <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {keys.map(r => (
          <section key={r} className="card p-3">
            <h2 className="brand-title text-xl text-primaryRed">Round {r}</h2>
            <div className="mt-2 grid gap-2">
              {rounds[r].map(m => (
                <div key={m.id} className="card p-2">
                  <div className="text-sm text-textDim">{m.bracket_label || ""}</div>
                  <div className="font-semibold">
                    {tmap.get(m.t1_id) || m.t1_id} {m.t1_rounds ?? 0} - {m.t2_rounds ?? 0} {tmap.get(m.t2_id) || m.t2_id}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </main>
  )
}
export const getServerSideProps: GetServerSideProps<Props> = async () => {
  const { data: pmatches } = await supabaseServer
    .from("matches")
    .select("id,playoff_round,bracket_label,t1_id,t2_id,t1_rounds,t2_rounds")
    .eq("match_type", "playoff")
  const { data: teams } = await supabaseServer.from("teams").select("id,name")
  const rounds: Record<number, PMatch[]> = {}
  ;(pmatches ?? []).forEach(m => {
    const r = m.playoff_round || 1
    if (!rounds[r]) rounds[r] = []
    rounds[r].push(m as PMatch)
  })
  return { props: { rounds, teams: teams ?? [] } }
}
