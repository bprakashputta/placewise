"use client";

import { BadgeCheck, Briefcase, GitCompareArrows, Sparkles, type LucideIcon } from "lucide-react";
import { useUser } from "@/components/auth/user-provider";
import { cn } from "@/lib/utils";
import { ENTER, greetingFor } from "./lib";

const SUGGESTIONS: { icon: LucideIcon; title: string; example: string; tint: string }[] = [
  {
    icon: BadgeCheck,
    title: "Find licensed engineers",
    example: "Texas PEs in DFW with drainage experience",
    tint: "bg-sky-500/10 text-sky-700 dark:text-sky-300",
  },
  { icon: Briefcase, title: "Staff a job order", example: "Who fits JO-03?", tint: "bg-violet-500/10 text-violet-700 dark:text-violet-300" },
  {
    icon: GitCompareArrows,
    title: "Compare candidates",
    example: "Structural engineers in Houston with a Texas PE",
    tint: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  },
  { icon: Sparkles, title: "What can you do?", example: "What can you do?", tint: "bg-amber-500/10 text-amber-800 dark:text-amber-300" },
];

/** Empty-chat state: a personal greeting and four starting points. */
export function Welcome({ onPick, disabled }: { onPick: (text: string) => void; disabled: boolean }) {
  const { user } = useUser();
  const first = user?.display_name?.trim().split(/\s+/)[0];
  return (
    <div className={cn("flex flex-1 flex-col justify-center py-10 sm:py-16", ENTER)}>
      <h1 className="text-[28px] leading-tight font-semibold tracking-tight sm:text-4xl" suppressHydrationWarning>
        {greetingFor(new Date())}
        {first ? (
          <>
            , <span className="bg-gradient-to-r from-brand to-fuchsia-500 bg-clip-text text-transparent">{first}</span>
          </>
        ) : null}
      </h1>
      <p className="mt-2 text-base text-muted-foreground">Ask about your candidates, or pick a job order to staff.</p>
      <ul className="mt-8 grid gap-3 @md:grid-cols-2" aria-label="Suggestions">
        {SUGGESTIONS.map((s) => (
          <li key={s.title}>
            <button
              type="button"
              onClick={() => onPick(s.example)}
              disabled={disabled}
              className="group flex h-full w-full items-start gap-3 rounded-2xl border bg-card p-4 text-left shadow-xs outline-none transition-all hover:-translate-y-px hover:border-brand/30 hover:shadow-md focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-60 motion-reduce:hover:translate-y-0"
            >
              <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-xl", s.tint)}>
                <s.icon className="size-4" aria-hidden="true" />
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-medium">{s.title}</span>
                <span className="mt-0.5 block text-sm text-muted-foreground">{s.example === s.title ? "Examples and tips" : s.example}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
