import { GetServerSideProps } from "next"
import { supabaseServer } from "../../lib/supabaseClient"
type Match = {
  id: number
  group_name: string | null
  week: number | null
  team1_id: number
  team2_id: number
  score_t1: number | null
  score_t2: number | null
  status: string
}
type Team = { id: number; name: string }
type MapRow = { map_name: string; team1_rounds: number | null; team2_rounds: number | null }
type Props = { match: Match | null; t1: Team | null; t2: Team | null; maps: MapRow[] }
export default function MatchSummary({ match, t1, t2, maps }: Props) {
  if (!match) return <main className="min-h-screen p-6">Match not found</main>
  return (
    <main className="min-h-screen p-6">
      <h1 className="text-2xl font-semibold">Match Summary</h1>
      <div className="mt-4 border rounded p-4">
        <div className="text-lg font-semibold">
          {t1?.name || match.team1_id} {match.score_t1 ?? 0} - {match.score_t2 ?? 0} {t2?.name || match.team2_id}
        </div>
        <div className="text-sm text-gray-600">Week {match.week ?? "?"} • Group {match.group_name ?? "?"}</div>
        <div className="mt-4">
          <h2 className="text-xl font-semibold">Maps</h2>
          <div className="mt-2 grid gap-2">
            {maps.map((m, i) => (
              <div key={i} className="border rounded p-3">
                <div className="font-semibold">{m.map_name}</div>
                <div className="text-sm text-gray-700">
                  {(t1?.name || match.team1_id)} {m.team1_rounds ?? 0} - {m.team2_rounds ?? 0} {(t2?.name || match.team2_id)}
                </div>
              </div>
            ))}
            {maps.length === 0 && <div className="text-gray-500">No maps recorded</div>}
          </div>
        </div>
      </div>
    </main>
  )
}
export const getServerSideProps: GetServerSideProps<Props> = async (ctx) => {
  const id = Number(ctx.params?.id)
  if (!id) return { props: { match: null, t1: null, t2: null, maps: [] } }
  const { data: matchArr } = await supabaseServer
    .from("matches")
    .select("id,group_name,week,team1_id,team2_id,score_t1,score_t2,status")
    .eq("id", id)
    .limit(1)
  const match = (matchArr && matchArr[0]) || null
  if (!match) return { props: { match: null, t1: null, t2: null, maps: [] } }
  const { data: teams } = await supabaseServer
    .from("teams")
    .select("id,name")
    .in("id", [match.team1_id, match.team2_id])
  const t1 = teams?.find(t => t.id === match.team1_id) || null
  const t2 = teams?.find(t => t.id === match.team2_id) || null
  const { data: maps } = await supabaseServer
    .from("match_maps")
    .select("map_name,team1_rounds,team2_rounds")
    .eq("match_id", id)
  return { props: { match, t1, t2, maps: (maps ?? []) as MapRow[] } }
}
