import { GetServerSideProps } from "next"
import { useMemo, useState } from "react"
import { supabaseServer } from "../lib/supabaseClient"
import Link from "next/link"
type Player = { id: number; name: string; team_id: number }
type Team = { id: number; name: string }
type Props = { players: Player[]; teams: Team[] }
export default function Players({ players, teams }: Props) {
  const [q, setQ] = useState("")
  const tmap = useMemo(() => {
    const m = new Map<number, string>()
    teams.forEach(t => m.set(t.id, t.name))
    return m
  }, [teams])
  const filtered = players.filter(p => p.name.toLowerCase().includes(q.toLowerCase()))
  return (
    <main className="min-h-screen p-6">
      <h1 className="text-2xl font-semibold">Players</h1>
      <input
        className="mt-4 border p-2 w-full max-w-md"
        placeholder="Search..."
        value={q}
        onChange={e => setQ(e.target.value)}
      />
      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map(p => (
          <Link key={p.id} href={`/players/${p.id}`} className="card p-3">
            <div className="font-semibold">{p.name}</div>
            <div className="text-sm text-textDim">{(p as any).riot_id ? `(${(p as any).riot_id})` : ""}</div>
            <div className="text-sm text-textDim">{tmap.get(p.team_id) || "Free Agent"}</div>
          </Link>
        ))}
      </div>
    </main>
  )
}
export const getServerSideProps: GetServerSideProps<Props> = async () => {
  const { data: players } = await supabaseServer.from("players").select("id,name,team_id,riot_id")
  const { data: teams } = await supabaseServer.from("teams").select("id,name")
  return { props: { players: players ?? [], teams: teams ?? [] } }
}
