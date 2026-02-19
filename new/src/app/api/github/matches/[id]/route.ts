import { NextRequest, NextResponse } from "next/server";

const owner = process.env.GITHUB_OWNER || process.env.GH_OWNER || process.env.NEXT_PUBLIC_GITHUB_OWNER;
const repo = process.env.GITHUB_REPO || process.env.GH_REPO || process.env.NEXT_PUBLIC_GITHUB_REPO;
const branch = process.env.GITHUB_BRANCH || process.env.GH_BRANCH || "main";
const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;

export async function GET(req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await ctx.params;
    if (!id) return NextResponse.json({ error: "Missing id" }, { status: 400 });
    if (!owner || !repo) {
      return NextResponse.json({ error: "GitHub repo not configured" }, { status: 500 });
    }
    const path = `assets/matches/match_${id}.json`;
    const rawUrl = `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${path}`;
    const headers: Record<string, string> = {};
    if (token) {
      // Prefer GitHub API content for private repos
      const apiUrl = `https://api.github.com/repos/${owner}/${repo}/contents/${path}?ref=${branch}`;
      const apiHeaders: Record<string, string> = { "Accept": "application/vnd.github+json", "Authorization": `Bearer ${token}` };
      const r = await fetch(apiUrl, { headers: apiHeaders, cache: "no-store" });
      if (!r.ok) {
        const text = await r.text();
        return NextResponse.json({ error: text }, { status: r.status });
      }
      const content = await r.json();
      if (!content?.content) return NextResponse.json({ error: "No content" }, { status: 404 });
      const buff = Buffer.from(content.content, "base64").toString("utf-8");
      return new NextResponse(buff, { status: 200, headers: { "Content-Type": "application/json" } });
    } else {
      const r = await fetch(rawUrl, { headers, cache: "no-store" });
      if (!r.ok) {
        const text = await r.text();
        return NextResponse.json({ error: text }, { status: r.status });
      }
      const text = await r.text();
      return new NextResponse(text, { status: 200, headers: { "Content-Type": "application/json" } });
    }
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || "error" }, { status: 500 });
  }
}
