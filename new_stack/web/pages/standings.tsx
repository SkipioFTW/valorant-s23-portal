import { GetServerSideProps } from "next"
import { useState } from "react"
import { supabaseServer } from "../lib/supabaseClient"
import { computeStandings, Team, Match, StandingRow, MapRow } from "../utils/standings"
import SectionHeader from "../components/SectionHeader"
type Props = { groups: Record<string, StandingRow[]> }
export default function Standings({ groups }: Props) {
  const gnames = Object.keys(groups)
  const [active, setActive] = useState(gnames[0])
  const rows = groups[active] || []
  return (
    <main className="min-h-screen p-6">
      <SectionHeader title="League Standings" />
      <div className="flex gap-4 text-sm">
        {gnames.map(g => (
          <button
            key={g}
            className={`brand-title ${active === g ? "text-primaryRed" : "text-textDim"}`}
            onClick={() => setActive(g)}
          >
            Group {g}
          </button>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-4 text-xs">
        <div className="flex items-center gap-2"><span className="inline-block w-3 h-3 bg-primaryBlue rounded-sm"></span> Round 1 BYE</div>
        <div className="flex items-center gap-2"><span className="inline-block w-3 h-3 bg-primaryBlue/60 rounded-sm"></span> Round of 24</div>
        <div className="flex items-center gap-2"><span className="inline-block w-3 h-3 bg-primaryRed rounded-sm"></span> Eliminated</div>
      </div>
      <div className="mt-3 overflow-x-auto card">
        <table className="min-w-full">
          <thead>
            <tr>
              <th className="p-2 text-left text-textDim">Team</th>
              <th className="p-2 text-textDim">W</th>
              <th className="p-2 text-textDim">L</th>
              <th className="p-2 text-textDim">PD</th>
              <th className="p-2 text-textDim">PTS</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, idx) => {
              let border = ""
              if (idx < 2) border = "border-l-4 border-primaryBlue"
              else if (idx >= 2 && idx <= 5) border = "border-l-4 border-primaryBlue/60"
              else if (r.eliminated) border = "border-l-4 border-primaryRed"
              return (
                <tr key={r.id} className={`border-b border-primaryBlue/10 ${border}`}>
                  <td className="p-2">{r.name}</td>
                  <td className="p-2 text-center">{r.wins}</td>
                  <td className="p-2 text-center">{r.losses}</td>
                  <td className="p-2 text-center">{r.pd}</td>
                  <td className="p-2 text-center">{r.points}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
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
  const tlist = (teams ?? []) as Team[]
  const mlist = (matches ?? []) as Match[]
  const maplist = (maps ?? []) as MapRow[]
  const rows = computeStandings(tlist, mlist, maplist)
  const groups: Record<string, StandingRow[]> = {}
  rows.forEach(r => {
    const k = r.group_name || "A"
    if (!groups[k]) groups[k] = []
    groups[k].push(r)
  })
  return { props: { groups } }
}
