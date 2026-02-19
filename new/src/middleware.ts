import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const buckets = new Map<string, { count: number; reset: number }>();
function allow(ip: string, key: string, limit: number, windowMs: number) {
  const k = `${ip}:${key}`;
  const now = Date.now();
  const b = buckets.get(k);
  if (!b || now > b.reset) {
    buckets.set(k, { count: 1, reset: now + windowMs });
    return true;
  }
  if (b.count < limit) {
    b.count += 1;
    return true;
  }
  return false;
}

export function middleware(req: NextRequest) {
  const ip = req.ip ?? req.headers.get('x-forwarded-for') ?? 'unknown';
  const path = req.nextUrl.pathname;

  if (path.startsWith('/api/admin/login')) {
    if (!allow(String(ip), 'admin-login', 5, 10 * 60 * 1000)) {
      return NextResponse.json({ error: 'rate limit' }, { status: 429 });
    }
  }
  if (path.startsWith('/api/github/')) {
    if (!allow(String(ip), 'github', 60, 60 * 1000)) {
      return NextResponse.json({ error: 'rate limit' }, { status: 429 });
    }
  }

  const rsp = NextResponse.next();
  rsp.headers.set('X-Frame-Options', 'DENY');
  rsp.headers.set('X-Content-Type-Options', 'nosniff');
  rsp.headers.set('Referrer-Policy', 'no-referrer');
  rsp.headers.set('Permissions-Policy', 'geolocation=(), microphone=(), camera=()');
  const csp = "default-src 'self'; img-src 'self' https: data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' https://api.github.com https://raw.githubusercontent.com " + (process.env.NEXT_PUBLIC_SUPABASE_URL || '');
  rsp.headers.set('Content-Security-Policy', csp);
  return rsp;
}

export const config = {
  matcher: ['/api/:path*'],
};
