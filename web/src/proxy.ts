import { NextResponse, type NextRequest } from "next/server";

// Next 16 "Proxy" (formerly Middleware): an optimistic, cookie-presence check that sends visitors
// without a session to /login before a portal page renders. It never validates the session; the
// API does that on every /api/* call (and the client redirects to /login on any 401).
export function proxy(request: NextRequest) {
  if (request.cookies.has("pw_session")) return NextResponse.next();
  const url = request.nextUrl.clone();
  const next = request.nextUrl.pathname + request.nextUrl.search;
  url.pathname = "/login";
  url.search = "";
  url.searchParams.set("next", next);
  return NextResponse.redirect(url);
}

export const config = {
  // Portal pages only. /login, /, /api/*, static assets and diagrams are never matched.
  matcher: [
    "/dashboard/:path*",
    "/candidates/:path*",
    "/job-orders/:path*",
    "/ask/:path*",
    "/approvals/:path*",
    "/admin/:path*",
    "/seed/:path*",
  ],
};
