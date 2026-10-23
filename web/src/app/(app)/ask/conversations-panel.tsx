"use client";

import Link from "next/link";
import { Briefcase, CircleAlert, MessagesSquare, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ApiError, ConversationSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

type Group = { label: string; items: ConversationSummary[] };

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

/** Today / Yesterday / Earlier by last_message_at, in the viewer's local time. List order is kept (newest first). */
function groupByDay(items: ConversationSummary[]): Group[] {
  const today = startOfDay(new Date());
  const yesterday = today - 86_400_000;
  const groups: Group[] = [
    { label: "Today", items: [] },
    { label: "Yesterday", items: [] },
    { label: "Earlier", items: [] },
  ];
  for (const c of items) {
    const day = startOfDay(new Date(c.last_message_at ?? c.created_at));
    groups[day >= today ? 0 : day >= yesterday ? 1 : 2].items.push(c);
  }
  return groups.filter((g) => g.items.length > 0);
}

export function ConversationsPanel({
  conversations,
  error,
  loading,
  selectedId,
  onNewChat,
  onSelect,
  onRetry,
  className,
}: {
  conversations: ConversationSummary[] | undefined;
  error?: ApiError;
  loading: boolean;
  selectedId: number | null;
  onNewChat: () => void;
  onSelect?: () => void;
  onRetry: () => void;
  className?: string;
}) {
  const groups = groupByDay(conversations ?? []);
  return (
    <nav aria-label="Chats" className={cn("flex min-h-0 flex-col gap-3", className)}>
      <Button variant="outline" onClick={onNewChat} className="w-full justify-start">
        <Plus aria-hidden="true" /> New chat
      </Button>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {conversations === undefined && loading ? (
          <div className="space-y-2" aria-busy="true">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </div>
        ) : error && conversations === undefined ? (
          <div className="space-y-2 px-1 py-2 text-sm text-muted-foreground">
            <p className="flex items-center gap-1.5">
              <CircleAlert className="size-4 shrink-0" aria-hidden="true" /> Couldn&apos;t load your chats.
            </p>
            <Button variant="outline" size="xs" onClick={onRetry}>
              Try again
            </Button>
          </div>
        ) : groups.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-2 py-8 text-center text-sm text-muted-foreground">
            <MessagesSquare className="size-5" aria-hidden="true" />
            No chats yet
          </div>
        ) : (
          <div className="space-y-4">
            {groups.map((g) => (
              <section key={g.label} aria-label={g.label}>
                <h3 className="px-2 pb-1 text-xs font-medium text-muted-foreground">{g.label}</h3>
                <ul className="space-y-0.5">
                  {g.items.map((c) => {
                    const selected = c.id === selectedId;
                    return (
                      <li key={c.id}>
                        <Link
                          href={`/ask?c=${c.id}`}
                          onClick={onSelect}
                          aria-current={selected ? "page" : undefined}
                          className={cn(
                            "flex flex-col gap-1 rounded-md px-2 py-1.5 text-sm outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
                            selected && "bg-muted font-medium",
                          )}
                        >
                          <span className="line-clamp-1 break-all">{c.title || "New chat"}</span>
                          {(c.job_order_title || !c.active) && (
                            <span className="flex min-w-0 items-center gap-1.5">
                              {c.job_order_title && (
                                <Badge variant="outline" className="h-4 max-w-[11rem] gap-1 px-1.5 text-[10px] font-normal" title={c.job_order_title}>
                                  <Briefcase className="size-2.5" aria-hidden="true" />
                                  <span className="truncate">{c.title === c.job_order_title && c.job_order_id ? `JO-${String(c.job_order_id).padStart(2, "0")}` : c.job_order_title}</span>
                                </Badge>
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
