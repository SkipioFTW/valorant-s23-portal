import { GetServerSideProps } from "next"
import { useMemo, useState } from "react"
import Link from "next/link"
import { supabaseServer } from "../lib/supabaseClient"
import SectionHeader from "../components/SectionHeader"
type Player = { id: number; name: string; riot_id: string | null; team_id: number | null }
type Team = { id: number; name: string; group_name: string | null }
type Props = { players: Player[]; teams: Team[] }
export default function Search({ players, teams }: Props) {
  const [q, setQ] = useState("")
  const filteredPlayers = useMemo(() => {
    const qq = q.toLowerCase()
    return players.filter(p =>
      (p.name || "").toLowerCase().includes(qq) ||
      (p.riot_id || "").toLowerCase().includes(qq)
    ).slice(0, 20)
  }, [q, players])
  const filteredTeams = useMemo(() => {
    const qq = q.toLowerCase()
    return teams.filter(t =>
      (t.name || "").toLowerCase().includes(qq) ||
      (t.group_name || "").toLowerCase().includes(qq)
    ).slice(0, 20)
  }, [q, teams])
  return (
    <main className="min-h-screen p-6">
      <SectionHeader title="Search" subtitle="Find players and teams quickly" />
      <input className="card border border-primaryBlue/30 p-2 w-full max-w-xl" placeholder="Type a player name, Riot ID, or team name..." value={q} onChange={e => setQ(e.target.value)} />
      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
        <section>
          <h3 className="brand-title text-xl text-primaryBlue">Players</h3>
          <div className="mt-2 grid gap-2">
            {filteredPlayers.map(p => (
              <Link key={p.id} href={`/players/${p.id}`} className="card p-3">
                <div className="font-semibold">{p.name}{p.riot_id ? ` (${p.riot_id})` : ""}</div>
              </Link>
            ))}
            {filteredPlayers.length === 0 && <div className="text-textDim">No players match</div>}
          </div>
        </section>
        <section>
          <h3 className="brand-title text-xl text-primaryRed">Teams</h3>
          <div className="mt-2 grid gap-2">
            {filteredTeams.map(t => (
              <Link key={t.id} href={`/teams/${t.id}`} className="card p-3">
                <div className="font-semibold">{t.name}</div>
                <div className="text-sm text-textDim">Group {t.group_name || "-"}</div>
              </Link>
            ))}
            {filteredTeams.length === 0 && <div className="text-textDim">No teams match</div>}
          </div>
        </section>
      </div>
    </main>
  )
}
export const getServerSideProps: GetServerSideProps<Props> = async () => {
  const { data: players } = await supabaseServer.from("players").select("id,name,riot_id,team_id")
  const { data: teams } = await supabaseServer.from("teams").select("id,name,group_name")
  return { props: { players: players ?? [], teams: teams ?? [] } }
}
