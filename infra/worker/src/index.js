// Placewise public address on workers.dev: forwards every request to the Cloudflare quick tunnels
// that serve the app from the Docker stack, so the link reads placewise.<subdomain>.workers.dev.
//
// Reliability: a quick tunnel holds a single connection to Cloudflare, and when Cloudflare resets it
// the tunnel returns 530 for a few seconds. So we run two independent tunnels (TUNNEL_ORIGINS,
// comma-separated, set at deploy time) and fail over between them, with a short second round of
// retries. A visitor sees a slightly slower page instead of an error.
const RETRY_ALWAYS = new Set([530]); // tunnel not connected: the request never reached the app
const RETRY_IDEMPOTENT = new Set([502, 503, 504, 520, 521, 522, 523, 524]);
const IDEMPOTENT = new Set(["GET", "HEAD", "OPTIONS"]);
const ROUNDS = 3;
const FAST_FAIL_MS = 1000; // a connection failure this quick can't have delivered the request
const ROUND_PAUSE_MS = [0, 1500, 4000];

export default {
  async fetch(request, env) {
    const started = Date.now();
    const origins = (env.TUNNEL_ORIGINS || env.TUNNEL_ORIGIN || "")
      .split(",").map((s) => s.trim()).filter(Boolean);
    const log = (status, note, extra = {}) =>
      // One structured line per request. Never cookies, auth headers, query values or bodies.
      console.log(JSON.stringify({
        method: request.method,
        path: new URL(request.url).pathname,
        status,
        ms: Date.now() - started,
        country: request.cf?.country,
        note,
        ...extra,
      }));
    if (!origins.length) {
      log(503, "no tunnel configured");
      return new Response("Placewise is not connected right now.", { status: 503 });
    }
    const incoming = new URL(request.url);
    const headers = new Headers(request.headers);
    headers.set("x-forwarded-host", incoming.host);
    headers.set("x-forwarded-proto", "https");

    // Buffer the body once so a request can be retried on the other tunnel (uploads are small resumes).
    const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();
    const idempotent = IDEMPOTENT.has(request.method);

    let lastErr = "";
    let attempts = 0;
    for (let round = 0; round < ROUNDS; round++) {
      if (ROUND_PAUSE_MS[round]) await new Promise((r) => setTimeout(r, ROUND_PAUSE_MS[round]));
      for (const origin of origins) {
        attempts++;
        // Every route gets our shared secret and the visitor's IP. The direct route needs the secret to get
        // past Caddy; on the tunnel routes Cloudflare may replace CF-Connecting-IP with the Worker's own
        // address, so the api trusts x-placewise-client-ip when the secret matches (login rate limit).
        let h = headers;
        if (env.ORIGIN_SECRET) {
          h = new Headers(headers);
          h.set("x-placewise-origin", env.ORIGIN_SECRET);
          h.set("x-placewise-client-ip", request.headers.get("cf-connecting-ip") || "");
        }
        let res;
        const tried = Date.now();
        try {
          res = await fetch(new URL(incoming.pathname + incoming.search, origin), {
            method: request.method,
            headers: h,
            body,
            redirect: "manual", // pass redirects back to the browser, rewritten to this address
          });
        } catch (e) {
          lastErr = `unreachable: ${e?.message ?? e}`;
          // An exception doesn't always prove the app never got the request, so a POST (match run, approval)
          // moves on to the next route only if the attempt failed fast: a refused connection or TLS failure
          // (e.g. Caddy down) fails in milliseconds, before any request could reach the app. A slow failure
          // might have reached the app, so it isn't repeated.
          if (idempotent || Date.now() - tried < FAST_FAIL_MS) continue;
          log(502, `not retried (${request.method}): ${lastErr}`, { attempts });
          return new Response(JSON.stringify({ detail: "Placewise couldn't be reached. Please try again." }), {
            status: 502, headers: { "content-type": "application/json", "cache-control": "no-store" },
          });
        }
        const retryable = RETRY_ALWAYS.has(res.status) || (idempotent && RETRY_IDEMPOTENT.has(res.status));
        if (retryable) {
          lastErr = `status ${res.status}`;
          continue;
        }
        const out = new Response(res.body, res);
        const loc = out.headers.get("location");
        if (loc && loc.startsWith(origin)) out.headers.set("location", loc.replace(origin, incoming.origin));
        log(res.status, res.status >= 500 ? "app error" : attempts > 1 ? "recovered" : undefined,
          attempts > 1 ? { attempts, tunnel: origins.indexOf(origin) } : {});
        return out;
      }
    }
    log(502, `all tunnels failed: ${lastErr}`, { attempts });
    const wantsPage = request.method === "GET" && (request.headers.get("accept") || "").includes("text/html");
    if (wantsPage) {
      // A page that waits for the app to come back and reloads itself, so nobody has to press refresh.
      return new Response(RECONNECT_PAGE, {
        status: 503,
        headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "retry-after": "5" },
      });
    }
    return new Response(JSON.stringify({ detail: "Placewise is reconnecting. Please retry in a few seconds." }), {
      status: 503,
      headers: { "content-type": "application/json", "cache-control": "no-store", "retry-after": "5" },
    });
  },
};

const RECONNECT_PAGE = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Placewise · Reconnecting</title>
<style>
  :root { --bg:#f8fafc; --card:#fff; --fg:#0f172a; --muted:#64748b; --accent:#4f46e5; --ring:#e2e8f0; }
  @media (prefers-color-scheme: dark) { :root { --bg:#0b1020; --card:#111827; --fg:#e5e7eb; --muted:#94a3b8; --accent:#818cf8; --ring:#1f2937; } }
  * { box-sizing:border-box } html,body { height:100% }
  body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
         display:grid; place-items:center; padding:16px; }
  .card { background:var(--card); border:1px solid var(--ring); border-radius:14px; padding:32px 28px; max-width:420px; width:100%; text-align:center; }
  .brand { font-weight:700; letter-spacing:-.01em; font-size:18px; margin-bottom:20px }
  .spin { width:34px; height:34px; border-radius:50%; border:3px solid var(--ring); border-top-color:var(--accent);
          margin:0 auto 18px; animation:s 0.9s linear infinite }
  @keyframes s { to { transform:rotate(360deg) } }
  h1 { font-size:17px; margin:0 0 6px } p { margin:0; color:var(--muted) } small { display:block; margin-top:16px; color:var(--muted) }
</style></head>
<body><main class="card">
  <div class="brand">Placewise</div>
  <div class="spin" aria-hidden="true"></div>
  <h1>Reconnecting…</h1>
  <p>The connection dropped for a moment. This page will reload by itself as soon as Placewise is back. You'll stay signed in.</p>
  <small id="st">Checking…</small>
</main>
<script>
  const st = document.getElementById("st"); let n = 0;
  async function check() {
    n++;
    try {
      const r = await fetch("/api/health", { cache: "no-store" });
      if (r.ok) { st.textContent = "Back online. Reloading…"; location.reload(); return; }
    } catch (e) {}
    st.textContent = "Still reconnecting (check " + n + ")";
    setTimeout(check, 3000);
  }
  setTimeout(check, 2000);
</script>
<noscript><meta http-equiv="refresh" content="8"></noscript>
</body></html>`;
