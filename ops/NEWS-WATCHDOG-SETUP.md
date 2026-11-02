# Independent news watchdog

The GitHub schedule remains the primary updater. This Cloudflare Worker is an independent recovery trigger: every five minutes it checks the latest run of `Update cached news`. If the latest run is older than 25 minutes or failed outside the 10-minute cooldown, it calls GitHub's `workflow_dispatch` endpoint. It does not fetch news itself and does not change the 15-minute source-fetch interval.

## One-time setup

1. Open Cloudflare Dashboard → Workers & Pages → Create → Worker.
2. Name it `saudi-news-watchdog`.
3. Replace the starter code with the complete contents of `ops/cloudflare-news-watchdog.js`, then Deploy.
4. Open the Worker Settings → Variables and Secrets:
   - Add secret `GH_TOKEN`: a GitHub fine-grained personal access token limited to this repository, with **Actions: Read and write** permission.
   - Add secret `WATCHDOG_KEY`: generate a long random value. It protects the optional manual HTTP check endpoint.
   - Optional variable `GH_REPO`: `abud3d/news`.
   - Optional variable `GH_WORKFLOW`: `update-news.yml`.
5. Open Triggers → Cron Triggers → Add Cron Trigger and set `*/5 * * * *` (every five minutes).
6. Save. Check Worker → Logs after the next scheduled trigger. Normal outcomes are `recent successful update` or `dispatched`.

## Manual check

The Worker HTTP endpoint is protected. Call it only with the secret header:

```http
GET https://<your-worker-subdomain>.workers.dev/
Authorization: Bearer <WATCHDOG_KEY>
```

A `dispatched` response means the watchdog asked GitHub to start the existing workflow. It does not mean the run or Pages deployment has completed yet.

## Safety and operating notes

- Never commit either secret to this repository.
- Do not use a broad personal token. Limit it to `abud3d/news` and Actions read/write.
- The Worker avoids dispatching while a recent run is queued or running.
- If a run remains active for more than 25 minutes, the Worker reports an alert rather than starting a duplicate run.
- GitHub Actions concurrency remains enabled to prevent overlapping cache writes.
- The Worker is not active until it is deployed in the Cloudflare account and the two secrets plus Cron Trigger are configured.
