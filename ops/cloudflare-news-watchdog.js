const API = "https://api.github.com";
const REPO = "abud3d/news";
const WORKFLOW = "update-news.yml";
const STALE_AFTER_MS = 25 * 60 * 1000;
const FAILURE_COOLDOWN_MS = 10 * 60 * 1000;

async function github(path, token, method = "GET", body) {
  const response = await fetch(API + path, {
    method,
    headers: {
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "SaudiAI-News-Watchdog",
      ...(token ? { "Authorization": "Bearer " + token } : {}),
      ...(body ? { "Content-Type": "application/json" } : {})
    },
    body: body ? JSON.stringify(body) : undefined
  });
  const raw = await response.text();
  if (!response.ok) throw new Error("GitHub API " + response.status + ": " + raw.slice(0, 300));
  return raw ? JSON.parse(raw) : {};
}

async function checkNews(env) {
  if (!env.GH_TOKEN) throw new Error("Missing Worker secret GH_TOKEN");
  const repo = env.GH_REPO || REPO;
  const workflow = env.GH_WORKFLOW || WORKFLOW;
  const runsPath = "/repos/" + repo + "/actions/workflows/" + workflow + "/runs?per_page=10";
  const data = await github(runsPath, env.GH_TOKEN);
  const runs = data.workflow_runs || [];
  const latest = runs[0];
  const now = Date.now();

  if (latest && ["queued", "in_progress", "waiting", "requested"].includes(latest.status)) {
    const age = now - Date.parse(latest.created_at);
    if (age < STALE_AFTER_MS) return { action: "none", reason: "workflow already active", run_id: latest.id };
    return { action: "alert", reason: "workflow has been active too long", run_id: latest.id };
  }

  if (latest) {
    const age = now - Date.parse(latest.updated_at || latest.created_at);
    if (latest.conclusion === "success" && age < STALE_AFTER_MS) {
      return { action: "none", reason: "recent successful update", run_id: latest.id };
    }
    if (latest.conclusion !== "success" && age < FAILURE_COOLDOWN_MS) {
      return { action: "none", reason: "failure cooldown", run_id: latest.id, conclusion: latest.conclusion };
    }
  }

  await github("/repos/" + repo + "/actions/workflows/" + workflow + "/dispatches",
    env.GH_TOKEN, "POST", { ref: "main" });
  return { action: "dispatched", reason: latest ? "latest run is stale or failed" : "no previous runs", previous_run_id: latest?.id || null };
}

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(checkNews(env).then(result => console.log(JSON.stringify(result))).catch(error => console.error("NEWS_WATCHDOG_ERROR", error.message)));
  },
  async fetch(request, env) {
    if (request.method !== "GET") return new Response("Method not allowed", { status: 405 });
    if (!env.WATCHDOG_KEY || request.headers.get("Authorization") !== "Bearer " + env.WATCHDOG_KEY) {
      return new Response("Unauthorized", { status: 401 });
    }
    try {
      const result = await checkNews(env);
      return Response.json(result, { headers: { "Cache-Control": "no-store" } });
    } catch (error) {
      return Response.json({ action: "error", message: error.message }, { status: 500 });
    }
  }
};
