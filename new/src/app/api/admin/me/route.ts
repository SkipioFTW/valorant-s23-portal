import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

export async function GET(req: NextRequest) {
  const cookie = req.cookies.get("admin_session")?.value;
  const ENV_TOKEN = process.env.ADMIN_TOKEN;
  if (!cookie || !ENV_TOKEN) {
    return NextResponse.json({ authorized: false });
  }
  const [ts, sig] = cookie.split(".");
  if (!ts || !sig) {
    return NextResponse.json({ authorized: false });
  }
  const msg = `admin:${ts}`;
  const expected = crypto.createHmac("sha256", ENV_TOKEN).update(msg).digest("hex");
  const fresh = Math.abs(Date.now() - Number(ts)) < 12 * 60 * 60 * 1000;
  const ok = expected === sig && fresh;
  return NextResponse.json({ authorized: ok });
}
