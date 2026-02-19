import { NextRequest, NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";

const owner = process.env.GITHUB_OWNER || process.env.GH_OWNER || process.env.NEXT_PUBLIC_GITHUB_OWNER;
const repo = process.env.GITHUB_REPO || process.env.GH_REPO || process.env.NEXT_PUBLIC_GITHUB_REPO;
const branch = process.env.GITHUB_BRANCH || process.env.GH_BRANCH || "main";
const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;

export async function GET(req: NextRequest) {
  try {
    const mid = new URL(req.url).searchParams.get("mid") || "";
    if (!mid) return NextResponse.json({ error: "Missing mid" }, { status: 400 });
    const id = mid.replace(/[^A-Za-z0-9\-]/g, "");
    const rel = path.join("assets", "matches", `match_${id}.json`);
    const localPath = path.join(process.cwd(), rel);
    let content: string | null = null;
    try {
      const buff = await fs.readFile(localPath, "utf-8");
      content = buff;
    } catch {}
    if (!content) {
      if (!owner || !repo) return NextResponse.json({ error: "GitHub repo not configured" }, { status: 500 });
      if (token) {
        const apiUrl = `https://api.github.com/repos/${owner}/${repo}/contents/${rel}?ref=${branch}`;
        const r = await fetch(apiUrl, { headers: { "Accept": "application/vnd.github+json", "Authorization": `Bearer ${token}` }, cache: "no-store" });
        if (r.ok) {
          const j = await r.json();
          if (j?.content) content = Buffer.from(j.content, "base64").toString("utf-8");
        }
      }
      if (!content) {
        const rawUrl = `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${rel}`;
        const r = await fetch(rawUrl, { cache: "no-store" });
        if (r.ok) {
          content = await r.text();
        }
      }
    }
    if (!content) return NextResponse.json({ error: "Not Found" }, { status: 404 });
    return new NextResponse(content, { status: 200, headers: { "Content-Type": "application/json" } });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || "error" }, { status: 500 });
  }
}
