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
        let res;
        try {
          res = await fetch(new URL(incoming.pathname + incoming.search, origin), {
            method: request.method,
            headers,
            body,
            redirect: "manual", // pass redirects back to the browser, rewritten to this address
          });
        } catch (e) {
          lastErr = `unreachable: ${e?.message ?? e}`;
          continue; // connection failed before reaching the app: safe to try the next tunnel
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
    return new Response("Placewise is reconnecting. Please refresh in a few seconds.", {
      status: 502,
      headers: { "retry-after": "5" },
    });
  },
};
