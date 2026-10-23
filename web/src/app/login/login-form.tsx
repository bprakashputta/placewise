"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { CircleAlert, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** Only same-site paths are allowed as a post-login destination (no open redirects). */
// Only same-origin paths. Parse with URL so tricks like "/\\evil.com" or "/\t/evil.com" (which browsers
// resolve to another site) can't slip through string checks.
function safeNext(next: string | null): string {
  if (!next) return "/dashboard";
  try {
    const u = new URL(next, window.location.origin);
    if (u.origin !== window.location.origin || u.pathname.startsWith("/login")) return "/dashboard";
    return u.pathname + u.search + u.hash;
  } catch {
    return "/dashboard";
  }
}

const MESSAGES: Record<number, string> = {
  401: "Wrong username or password",
  429: "Too many attempts, wait a minute",
};

export function LoginForm() {
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: form.get("username"), password: form.get("password") }),
      });
      if (res.ok) {
        // Full navigation so the proxy and every page see the new session cookie.
        window.location.assign(safeNext(searchParams.get("next")));
        return;
      }
      setError(MESSAGES[res.status] ?? "Sign-in failed. Please try again.");
    } catch {
      setError("Can't reach the server. Please try again.");
    }
    setPending(false);
  }

  return (
    <Card className="shadow-md">
      <CardContent className="pt-1">
        {/* method="post": if the form is submitted before hydration, the password must not land in a GET URL. */}
        <form onSubmit={onSubmit} method="post" className="space-y-4" noValidate>
          {error && (
            <div
              role="alert"
              className="flex items-center gap-2 rounded-lg border border-danger/25 bg-danger-soft px-3 py-2 text-sm text-danger-strong"
            >
              <CircleAlert className="size-4 shrink-0" aria-hidden="true" />
              {error}
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              name="username"
              required
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              aria-invalid={error ? true : undefined}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              name="password"
              type="password"
              required
              autoComplete="current-password"
              aria-invalid={error ? true : undefined}
            />
          </div>
          <Button type="submit" size="lg" className="w-full" disabled={pending}>
            {pending && <Loader2 className="animate-spin" aria-hidden="true" />}
            {pending ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
