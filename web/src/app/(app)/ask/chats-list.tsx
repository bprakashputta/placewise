"use client";

import { useState } from "react";
import Link from "next/link";
import { CircleAlert, MessagesSquare, PanelLeftClose, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ApiError, ConversationSummary } from "@/lib/api";
import { cn } from "@/lib/utils";
import { BRAND_SOLID, dayBucket,isGreetingOnly, jobOrderCode, relativeTime } from "./lib";

const GROUPS = ["Today", "Yesterday", "Earlier"] as const;

/** The left column: New chat, a title filter, and chats grouped by day. */
export function ChatsList({
  conversations,
  error,
  loading,
  selectedId,
  onNewChat,
  onSelect,
  onRetry,
  onCollapse,
}: {
  conversations: ConversationSummary[] | undefined;
  error?: ApiError;
  loading: boolean;
  selectedId: number | null;
  onNewChat: () => void;
  onSelect?: () => void;
  onRetry: () => void;
  /** Shown as a collapse button when the list is docked (lg+). */
  onCollapse?: () => void;
}) {
  const [query, setQuery] = useState("");
  const now = new Date();
  const q = query.trim().toLowerCase();
  // Empty chats never show; greeting-only chats only while they're open.
  const visible = (conversations ?? []).filter(
    (c) => c.message_count > 0 && (c.id === selectedId || !isGreetingOnly(c)) && (!q || (c.title || "New chat").toLowerCase().includes(q)),
  );
  const groups = GROUPS.map((label, i) => ({
    label,
    items: visible.filter((c) => dayBucket(c.last_message_at ?? c.created_at, now) === i),
  })).filter((g) => g.items.length > 0);

  return (
    <nav aria-label="Chats" className="flex h-full min-h-0 flex-col">
      <div className="space-y-2.5 p-3 pb-2">
        <div className="flex items-center gap-1.5">
          <Button onClick={onNewChat} className={cn("h-9 flex-1 justify-start gap-2 shadow-sm", BRAND_SOLID)}>
            <Plus aria-hidden="true" /> New chat
          </Button>
          {onCollapse && (
            <Button variant="ghost" size="icon" onClick={onCollapse} aria-label="Hide chats" title="Hide chats" className="text-muted-foreground">
              <PanelLeftClose aria-hidden="true" />
            </Button>
          )}
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats"
            aria-label="Search chats by title"
            className="h-8 w-full rounded-md border border-input bg-background pr-2 pl-8 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
          />
        </div>
      </div>

      <div className="relative min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {conversations === undefined && loading ? (
          <div className="space-y-1.5 px-1 pt-2" aria-busy="true" aria-label="Loading chats">
            {[70, 90, 60, 80, 75].map((w, i) => (
              <div key={i} className="space-y-1.5 rounded-md px-2 py-2">
                <Skeleton className="h-3.5" style={{ width: `${w}%` }} />
              </div>
            ))}
          </div>
        ) : error && conversations === undefined ? (
          <div className="space-y-2 px-2 py-3 text-sm text-muted-foreground">
            <p className="flex items-center gap-1.5">
              <CircleAlert className="size-4 shrink-0" aria-hidden="true" /> Couldn&apos;t load your chats.
            </p>
            <Button variant="outline" size="xs" onClick={onRetry}>
              Try again
            </Button>
          </div>
        ) : groups.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-3 py-10 text-center text-sm text-muted-foreground">
            <span className="flex size-9 items-center justify-center rounded-lg bg-muted">
              <MessagesSquare className="size-4" aria-hidden="true" />
            </span>
            {q ? "No chats match that search" : "No chats yet"}
          </div>
        ) : (
          <div className="space-y-4 pt-1">
            {groups.map((g) => (
              <section key={g.label} aria-label={g.label}>
                <h3 className="px-2.5 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">{g.label}</h3>
                <ul className="space-y-px">
                  {g.items.map((c) => {
                    const selected = c.id === selectedId;
                    return (
                      <li key={c.id}>
                        <Link
                          href={`/ask?c=${c.id}`}
                          onClick={onSelect}
                          aria-current={selected ? "page" : undefined}
                          className={cn(
                            "group relative flex flex-col gap-1 rounded-md py-1.5 pr-2 pl-2.5 text-sm outline-none transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
                            selected && "bg-brand-soft text-foreground hover:bg-brand-soft",
                          )}
                        >
                          {selected && <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-full bg-brand" aria-hidden="true" />}
                          <span className="flex items-baseline gap-2">
                            <span className={cn("min-w-0 flex-1 truncate", selected ? "font-medium" : "text-foreground/90")}>{c.title || "New chat"}</span>
                            <span className="shrink-0 text-[11px] text-muted-foreground tabular-nums">
                              {relativeTime(c.last_message_at ?? c.created_at, now)}
                            </span>
                          </span>
                          {(c.job_order_id || !c.active) && (
                            <span className="flex items-center gap-1.5">
                              {c.job_order_id && (
                                <span
                                  className="rounded border border-brand/25 bg-brand/5 px-1 text-[10px] leading-4 font-medium text-brand"
                                  title={c.job_order_title ?? undefined}
                                >
                                  {jobOrderCode(c.job_order_id)}
                                </span>
                              )}
                              {!c.active && <span className="text-[10px] text-muted-foreground">Closed</span>}
                            </span>
                          )}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}
          </div>
        )}
      </div>
    </nav>
  );
}
