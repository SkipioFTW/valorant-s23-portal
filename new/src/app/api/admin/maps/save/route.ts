import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';
import { supabaseServer } from '@/lib/supabaseServer';

function isAuthorized(req: NextRequest) {
  const cookie = req.cookies.get('admin_session')?.value;
  const token = process.env.ADMIN_TOKEN;
  if (!cookie || !token) return false;
  const [ts, sig] = cookie.split('.');
  const msg = `admin:${ts}`;
  const expected = crypto.createHmac('sha256', token).update(msg).digest('hex');
  const fresh = Math.abs(Date.now() - Number(ts)) < 12 * 60 * 60 * 1000;
  return expected === sig && fresh;
}

export async function POST(req: NextRequest) {
  if (!isAuthorized(req)) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  const body = await req.json();
  const { matchId, mapData, playerStats, meta } = body || {};
  if (!matchId || !mapData) return NextResponse.json({ error: 'bad request' }, { status: 400 });
  await Promise.all([
    supabaseServer.from('match_maps').delete().eq('match_id', matchId).eq('map_index', mapData.index),
    supabaseServer.from('match_stats_map').delete().eq('match_id', matchId).eq('map_index', mapData.index),
  ]);
  {
    const { error } = await supabaseServer.from('match_maps').insert({
      match_id: matchId,
      map_index: mapData.index,
      map_name: mapData.name,
      team1_rounds: mapData.t1_rounds,
      team2_rounds: mapData.t2_rounds,
      winner_id: mapData.winner_id,
      is_forfeit: mapData.is_forfeit ? 1 : 0,
    });
    if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  }
  if (Array.isArray(playerStats) && playerStats.length > 0) {
    const { error } = await supabaseServer.from('match_stats_map').insert(
      playerStats.map((s: any) => ({
        match_id: matchId,
        map_index: mapData.index,
        team_id: s.team_id,
        player_id: s.player_id,
        is_sub: s.is_sub ? 1 : 0,
        subbed_for_id: s.subbed_for_id,
        agent: s.agent,
        acs: s.acs,
        kills: s.kills,
        deaths: s.deaths,
        assists: s.assists,
      })),
    );
    if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  }
  const [{ data: allMaps }, { data: matchInfo }] = await Promise.all([
    supabaseServer.from('match_maps').select('winner_id').eq('match_id', matchId),
    supabaseServer.from('matches').select('team1_id, team2_id, week, playoff_round, bracket_pos, match_type').eq('id', matchId).single(),
  ]);
  if (allMaps && matchInfo) {
    const t1Wins = allMaps.filter((m: any) => m.winner_id === matchInfo.team1_id).length;
    const t2Wins = allMaps.filter((m: any) => m.winner_id === matchInfo.team2_id).length;
    const finalWinner = t1Wins > t2Wins ? matchInfo.team1_id : t2Wins > t1Wins ? matchInfo.team2_id : null;
    const payload: any = { score_t1: t1Wins, score_t2: t2Wins, maps_played: allMaps.length, winner_id: finalWinner, status: 'completed' };
    if (meta?.pendingId) {
      const { data: pend } = await supabaseServer.from('pending_matches').select('channel_id, submitter_id').eq('id', meta.pendingId).single();
      payload.reported = true;
      if (pend) {
        if (pend.channel_id !== undefined) payload.channel_id = pend.channel_id;
        if (pend.submitter_id !== undefined) payload.submitter_id = pend.submitter_id;
      }
      await supabaseServer.from('pending_matches').delete().eq('id', meta.pendingId);
    }
    const { error: totalsError } = await supabaseServer.from('matches').update(payload).eq('id', matchId);
    if (totalsError) return NextResponse.json({ error: totalsError.message }, { status: 400 });
    if (matchInfo.match_type === 'playoff' && payload.winner_id) {
      const winnerTeam = payload.winner_id as number;
      const round: number = matchInfo.playoff_round || 1;
      const pos: number = matchInfo.bracket_pos || 0;
      if (pos) {
        const { data: nextMatch } = await supabaseServer
          .from('matches')
          .select('*')
          .eq('match_type', 'playoff')
          .eq('playoff_round', round + 1)
          .eq('bracket_pos', pos)
          .limit(1);
        if (nextMatch && nextMatch.length > 0) {
          const nm = nextMatch[0];
          const updates: any = {};
          if (!nm.team1_id) updates.team1_id = winnerTeam;
          else if (!nm.team2_id) updates.team2_id = winnerTeam;
          if (updates.team1_id || updates.team2_id) {
            await supabaseServer.from('matches').update(updates).eq('id', nm.id);
          }
        } else {
          await supabaseServer.from('matches').insert({
            week: matchInfo.week || 0,
            group_name: 'Playoffs',
            team1_id: null,
            team2_id: winnerTeam,
            status: 'scheduled',
            format: 'BO3',
            maps_played: 0,
            match_type: 'playoff',
            playoff_round: round + 1,
            bracket_pos: pos,
            bracket_label: `R${round + 1} #${pos}`,
          } as any);
        }
      }
    }
  }
  return NextResponse.json({ ok: true });
}
