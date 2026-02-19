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
  const { name, riot_id, uuid, rank, tracker_link, default_team_id } = body || {};
  if (!name) return NextResponse.json({ error: 'bad request' }, { status: 400 });
  const { error } = await supabaseServer.from('players').insert({
    name,
    riot_id: riot_id || null,
    uuid: uuid || null,
    rank: rank || 'Unranked',
    tracker_link: tracker_link || null,
    default_team_id: default_team_id || null,
  });
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ ok: true });
}
