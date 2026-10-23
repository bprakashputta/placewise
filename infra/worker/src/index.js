// Placewise public address on workers.dev: forwards every request to the Cloudflare quick tunnel
// that serves the app from the Docker stack, so the link reads placewise.<subdomain>.workers.dev.
// TUNNEL_ORIGIN (e.g. https://abc-def.trycloudflare.com) is set at deploy time; when the tunnel
// restarts, redeploy with the new origin and the public address stays the same.
export default {
  async fetch(request, env) {
    const started = Date.now();
    const origin = env.TUNNEL_ORIGIN;
    const log = (status, note) =>
      // One structured line per request. Never cookies, auth headers, query values or bodies.
      console.log(JSON.stringify({
        method: request.method,
        path: new URL(request.url).pathname,
        status,
        ms: Date.now() - started,
        country: request.cf?.country,
        note,
      }));
    if (!origin) {
      log(503, "no tunnel configured");
      return new Response("Placewise is not connected right now.", { status: 503 });
    }
    const incoming = new URL(request.url);
    const target = new URL(incoming.pathname + incoming.search, origin);

    const headers = new Headers(request.headers);
    headers.set("x-forwarded-host", incoming.host);
    headers.set("x-forwarded-proto", "https");

    let res;
    try {
      res = await fetch(target, {
        method: request.method,
        headers,
        body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
        redirect: "manual", // pass redirects back to the browser, rewritten to this address
      });
    } catch (e) {
      log(502, `tunnel unreachable: ${e?.message ?? e}`);
      return new Response("Placewise is temporarily unavailable. Please try again in a minute.", { status: 502 });
    }

    const out = new Response(res.body, res);
    const loc = out.headers.get("location");
    if (loc && loc.startsWith(origin)) out.headers.set("location", loc.replace(origin, incoming.origin));
    log(res.status, res.status >= 500 ? "app error" : undefined);
    return out;
  },
};
