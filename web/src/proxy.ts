import { NextResponse, type NextRequest } from "next/server";

// Next 16 "Proxy" (formerly Middleware): an optimistic, cookie-presence check that sends visitors
// without a session to /login before a portal page renders. It never validates the session; the
// API does that on every /api/* call (and the client redirects to /login on any 401).
export function proxy(request: NextRequest) {
  const signedIn = request.cookies.has("pw_session");
  // The root goes straight into the portal: the dashboard if signed in, otherwise the login page.
  // (An expired cookie still lands on the dashboard; its first API call returns 401 and the client
  // sends the browser to /login.)
  if (request.nextUrl.pathname === "/") {
    const url = request.nextUrl.clone();
    url.pathname = signedIn ? "/dashboard" : "/login";
    url.search = "";
    return NextResponse.redirect(url);
  }
  if (signedIn) return NextResponse.next();
  const url = request.nextUrl.clone();
  const next = request.nextUrl.pathname + request.nextUrl.search;
  url.pathname = "/login";
  url.search = "";
  url.searchParams.set("next", next);
  return NextResponse.redirect(url);
}

export const config = {
  // The root and portal pages. /login, /api/*, static assets and diagrams are never matched.
  matcher: [
    "/",
    "/dashboard/:path*",
    "/candidates/:path*",
    "/job-orders/:path*",
    "/ask/:path*",
    "/approvals/:path*",
    "/admin/:path*",
    "/seed/:path*",
  ],
};
