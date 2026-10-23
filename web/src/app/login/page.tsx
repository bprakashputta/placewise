import type { Metadata } from "next";
import { Suspense } from "react";
import { FileSearch, ShieldCheck, UserCheck } from "lucide-react";
import { LogoMark, Wordmark } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Sign in" };

const PROOF_POINTS = [
  { icon: FileSearch, title: "Every claim cited to the resume", body: "Each requirement links to the exact line it came from." },
  { icon: ShieldCheck, title: "Licenses checked by code", body: "Required licenses are hard database filters, not an AI guess." },
  { icon: UserCheck, title: "Human approval before anything is sent", body: "Submittals and outreach wait for a recruiter's OK." },
];

function BrandPanel() {
  return (
    <section
      aria-label="About Placewise"
      className="relative hidden overflow-hidden bg-[oklch(0.22_0.09_274)] text-white lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16"
    >
      {/* Mesh: layered radial glows over a deep indigo base, plus a faint grid. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage: [
            "radial-gradient(60% 50% at 15% 10%, oklch(0.55 0.22 290 / 0.75) 0%, transparent 70%)",
            "radial-gradient(50% 45% at 90% 25%, oklch(0.6 0.16 230 / 0.45) 0%, transparent 70%)",
            "radial-gradient(70% 60% at 70% 100%, oklch(0.5 0.24 274 / 0.8) 0%, transparent 70%)",
          ].join(","),
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.07] [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]"
        style={{
          backgroundImage:
            "linear-gradient(to right, white 1px, transparent 1px), linear-gradient(to bottom, white 1px, transparent 1px)",
          backgroundSize: "44px 44px",
        }}
      />

      <div className="relative flex items-center gap-3">
        <LogoMark className="size-10 rounded-xl ring-1 ring-white/25" />
        <span className="text-lg font-semibold tracking-[-0.015em]">Placewise</span>
      </div>

      <div className="relative max-w-lg space-y-10">
        <div className="space-y-4">
          <p className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-white/85 ring-1 ring-white/15 backdrop-blur">
            <span className="size-1.5 rounded-full bg-emerald-300" aria-hidden="true" />
            For Architecture, Engineering &amp; Construction recruiters
          </p>
          <h1 className="text-[34px] leading-[1.15] font-semibold tracking-[-0.025em] text-balance xl:text-[40px]">
            AI that finds and explains the right A/E/C candidates, with evidence from every resume.
          </h1>
        </div>
        <ul className="space-y-5">
          {PROOF_POINTS.map((p) => (
            <li key={p.title} className="flex gap-3.5">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-white/10 ring-1 ring-white/15 backdrop-blur">
                <p.icon className="size-[18px] text-white" aria-hidden="true" />
              </span>
              <span>
                <span className="block text-[15px] font-medium">{p.title}</span>
                <span className="block text-sm text-white/70">{p.body}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>

      <p className="relative text-xs text-white/60">Personal demo project · synthetic data only</p>
    </section>
  );
}

export default function LoginPage() {
  return (
    <main className="grid min-h-svh flex-1 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <BrandPanel />
      <section className="relative flex flex-col items-center justify-center bg-background px-4 py-16 sm:px-8">
        <div className="absolute top-4 right-4">
          <ThemeToggle />
        </div>
        <div className="w-full max-w-sm space-y-8">
          <div className="space-y-6">
            <Wordmark className="lg:hidden" />
            <div className="space-y-1.5">
              <h2 className="text-2xl font-semibold tracking-[-0.022em]">Welcome back</h2>
              <p className="text-sm text-muted-foreground">Sign in to your Placewise workspace.</p>
            </div>
            <p className="text-sm leading-relaxed text-muted-foreground lg:hidden">
              AI that finds and explains the right A/E/C candidates, with evidence from every resume.
            </p>
          </div>
          <Suspense fallback={<div className="h-64 rounded-xl border bg-card shadow-sm" />}>
            <LoginForm />
          </Suspense>
          <p className="text-center text-xs text-muted-foreground">
            Demo build with two roles: Admin and Recruiter. Synthetic data only.
          </p>
        </div>
      </section>
    </main>
  );
}
