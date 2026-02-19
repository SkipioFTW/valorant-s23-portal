import { NextResponse } from "next/server";

const owner = process.env.GITHUB_OWNER || process.env.GH_OWNER || process.env.NEXT_PUBLIC_GITHUB_OWNER;
const repo = process.env.GITHUB_REPO || process.env.GH_REPO || process.env.NEXT_PUBLIC_GITHUB_REPO;
const branch = process.env.GITHUB_BRANCH || process.env.GH_BRANCH || "main";
const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;

export async function GET() {
  try {
    if (!owner || !repo) {
      return NextResponse.json({ error: "GitHub repo not configured" }, { status: 500 });
    }
    const apiUrl = `https://api.github.com/repos/${owner}/${repo}/contents/assets/matches?ref=${branch}`;
    const headers: Record<string, string> = { "Accept": "application/vnd.github+json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(apiUrl, { headers, cache: "no-store" });
    if (!res.ok) {
      const text = await res.text();
      return NextResponse.json({ error: text }, { status: res.status });
    }
    const files = await res.json();
    const jsonFiles = (files || [])
      .filter((f: any) => f.type === "file" && f.name.endsWith(".json"))
      .map((f: any) => ({ name: f.name, path: f.path, sha: f.sha, size: f.size }));
    return NextResponse.json({ files: jsonFiles });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || "error" }, { status: 500 });
  }
}
