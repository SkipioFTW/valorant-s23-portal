import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

export async function POST(req: NextRequest) {
  try {
    const { username, password, token } = await req.json();
    const ENV_USER = process.env.ADMIN_USER;
    const ENV_PASS = process.env.ADMIN_PASSWORD;
    const ENV_TOKEN = process.env.ADMIN_TOKEN;
    if (!ENV_USER || !ENV_PASS || !ENV_TOKEN) {
      return NextResponse.json({ ok: false, error: "Server not configured" }, { status: 500 });
    }
    if (username !== ENV_USER || password !== ENV_PASS || token !== ENV_TOKEN) {
      return NextResponse.json({ ok: false }, { status: 401 });
    }
    const ts = Date.now().toString();
    const msg = `admin:${ts}`;
    const sig = crypto.createHmac("sha256", ENV_TOKEN).update(msg).digest("hex");
    const cookieValue = `${ts}.${sig}`;
    const res = NextResponse.json({ ok: true });
    res.cookies.set("admin_session", cookieValue, {
      httpOnly: true,
      sameSite: "strict",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 12,
    });
    return res;
  } catch {
    return NextResponse.json({ ok: false }, { status: 400 });
  }
}
