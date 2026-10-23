"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowUp, Briefcase, CircleAlert, FileText, Loader2, MessagesSquare, Plus, SearchX, Sparkles } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { ResumeViewer, type ViewerTarget } from "@/components/resume-viewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ApiError,
  SEARCH_KINDS,
  apiFetch,
  useApi,
  type Citation,
  type Conversation,
  type ConversationSummary,
  type Message,
  type SendMessageResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { Answer, Markdown, PendingReply, sectionLabel } from "./answer";
import { ConversationsPanel } from "./conversations-panel";

const EXAMPLES = [
  "Who holds a Texas PE with drainage experience in DFW?",
  "Which licensed architects have healthcare projects over $50M?",
  "Find MEP engineers in Houston who know Revit and are LEED AP.",
];

const MAX_CHARS = 2000;
const TIMEOUT_MS = 90_000;

/** A message as shown: server messages plus the optimistic user bubble, which may have failed. */
type UIMessage = Message & { localKey: string; failed?: string };

function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 429) return "Today's AI spend cap has been reached, so Ask is paused until tomorrow. An admin can raise the cap.";
    if (e.status === 422) return `That message is too short or too long (1–${MAX_CHARS} characters).`;
    if (e.status === 404) return "This chat doesn't exist or isn't yours. Start a new chat.";
    return e.message;
  }
  if (e instanceof DOMException && (e.name === "TimeoutError" || e.name === "AbortError"))
    return "No answer after 90 seconds (the server may have restarted). Please ask again.";
  return "Can't reach the server. Check your connection and try again.";
}

const withKey = (m: Message): UIMessage => ({ ...m, localKey: `m${m.id}` });

/** `?c=` → conversation id; null = new chat; 0 = present but not a valid id. */
function parseConversationId(raw: string | null): number | null {
  if (raw === null || raw === "") return null;
  return /^\d+$/.test(raw) && Number(raw) > 0 ? Number(raw) : 0;
}

export function AskView() {
  const router = useRouter();
  const params = useSearchParams();
  const urlId = parseConversationId(params.get("c"));
  const list = useApi<ConversationSummary[]>("/api/conversations");
  const [sheetOpen, setSheetOpen] = useState(false);

  // The thread on screen. Navigating to another ?c= (or to a new chat) remounts it through `key`;
  // a new chat that just got its id keeps the same key, so its optimistic messages stay put.
  const [thread, setThread] = useState<{ key: number; id: number | null; created: number | null }>({ key: 0, id: urlId, created: null });
  if (thread.id !== urlId) {
    setThread(
      urlId !== null && urlId === thread.created
        ? { key: thread.key, id: urlId, created: null }
        : { key: thread.key + 1, id: urlId, created: null },
    );
  }

  function newChat() {
    setSheetOpen(false);
    if (urlId === null) setThread((t) => ({ key: t.key + 1, id: null, created: null }));
    else router.push("/ask");
  }

  function onCreated(id: number) {
    setThread((t) => ({ ...t, created: id }));
    router.replace(`/ask?c=${id}`, { scroll: false });
  }

  const panel = (onSelect?: () => void) => (
    <ConversationsPanel
      conversations={list.data}
      error={list.error}
      loading={list.loading}
      selectedId={urlId}
      onNewChat={newChat}
      onSelect={onSelect}
      onRetry={list.reload}
      className="h-full"
    />
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Ask"
        description="Chat about your candidate pool. Answers cite the resumes."
        actions={
          <Button variant="outline" className="lg:hidden" onClick={() => setSheetOpen(true)}>
            <MessagesSquare aria-hidden="true" /> Chats
          </Button>
        }
      />
      <div className="flex items-start gap-6">
        <aside className="sticky top-20 hidden max-h-[calc(100svh-7rem)] w-[260px] shrink-0 lg:flex lg:flex-col">{panel()}</aside>
        <div className="min-w-0 flex-1">
          <ChatThread key={thread.key} id={thread.id} onCreated={onCreated} onChanged={list.reload} onNewChat={newChat} />
        </div>
      </div>
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="left" className="w-[300px] gap-0 p-4 pt-12">
          <SheetHeader className="sr-only">
            <SheetTitle>Chats</SheetTitle>
            <SheetDescription>Your saved Ask conversations.</SheetDescription>
          </SheetHeader>
          {panel(() => setSheetOpen(false))}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function ChatThread({
  id,
  onCreated,
  onChanged,
  onNewChat,
}: {
  id: number | null;
  onCreated: (id: number) => void;
  onChanged: () => void;
  onNewChat: () => void;
}) {
  // Loaded once per mount; the parent remounts this component for a different conversation.
  const [initialId] = useState(id);
  const [conversationId, setConversationId] = useState<number | null>(id || null);
  const [meta, setMeta] = useState<ConversationSummary | null>(null);
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [load, setLoad] = useState<{ status: "loading" | "ready" | "missing" | "error"; error?: ApiError }>(
    initialId === null ? { status: "ready" } : initialId === 0 ? { status: "missing" } : { status: "loading" },
  );
  const [attempt, setAttempt] = useState(0);
  const [pending, setPending] = useState(false);
  const [text, setText] = useState("");
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const alive = useRef(true);
  const scrollTarget = useRef<"bottom" | string | null>(null);
  const seq = useRef(0);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    if (!initialId) return;
    let current = true;
    apiFetch<Conversation>(`/api/conversations/${initialId}`)
      .then((c) => {
        if (!current) return;
        const { messages: msgs, ...summary } = c;
        setMeta(summary);
        setMessages(msgs.map(withKey));
        scrollTarget.current = "bottom";
        setLoad({ status: "ready" });
      })
      .catch((e: unknown) => {
        if (!current) return;
        const err = e instanceof ApiError ? e : new ApiError(0, "Can't reach the server.");
        setLoad(err.status === 404 || err.status === 422 ? { status: "missing" } : { status: "error", error: err });
      });
    return () => {
      current = false;
    };
  }, [initialId, attempt]);

  // Scroll after render: to the bottom when a chat opens, or to the start of the newest question
  // when one is sent or answered (so long answers read from the top).
  useEffect(() => {
    const target = scrollTarget.current;
    if (!target) return;
    scrollTarget.current = null;
    if (target === "bottom") endRef.current?.scrollIntoView({ block: "end" });
    else document.querySelector(`[data-msg="${target}"]`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [messages, pending]);

  async function send(raw: string) {
    const content = raw.trim();
    if (!content || pending) return;
    const localKey = `local-${++seq.current}`;
    const optimistic: UIMessage = {
      id: -seq.current,
      role: "user",
      kind: "user",
      content,
      response: null,
      suggestions: [],
      created_at: new Date().toISOString(),
      localKey,
    };
    // A failed message was never saved, so a resend replaces it rather than stacking up.
    setMessages((m) => [...m.filter((x) => !x.failed), optimistic]);
    setPending(true);
    setText("");
    scrollTarget.current = localKey;
    const signal = AbortSignal.timeout(TIMEOUT_MS); // never leave the chat stuck "pending" if a request dies
    try {
      let cid = conversationId;
      if (cid === null) {
        // A new chat is only created once there's something to save.
        const created = await apiFetch<Conversation>("/api/conversations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
          signal,
        });
        if (!alive.current) return;
        cid = created.id;
        const { messages: _ignored, ...summary } = created;
        void _ignored;
        setConversationId(cid);
        setMeta(summary);
        onCreated(cid);
        onChanged();
      }
      const res = await apiFetch<SendMessageResponse>(`/api/conversations/${cid}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
        signal,
      });
      if (!alive.current) return;
      setMessages((m) => [
        ...m.map((x) => (x.localKey === localKey ? { ...res.user_message, localKey } : x)),
        withKey(res.assistant_message),
      ]);
      setMeta((m) => m && { ...m, active: true });
      scrollTarget.current = localKey;
      onChanged();
    } catch (e) {
      if (!alive.current) return;
      setMessages((m) => m.map((x) => (x.localKey === localKey ? { ...x, failed: errorMessage(e) } : x)));
      setText((t) => (t.trim() ? t : content)); // keep the text so it can be resent
    }
    if (!alive.current) return;
    setPending(false);
    inputRef.current?.focus();
  }

  const onCite = (c: Citation) =>
    setViewer({
      title: c.candidate_name,
      subtitle: `${sectionLabel(c.section)}: “${c.quote}”`,
      viewUrl: `/api/candidates/files/${c.resume_file_id}/view`,
      downloadUrl: `/api/candidates/files/${c.resume_file_id}`,
    });

  if (load.status === "missing") {
    return (
      <Card className="py-0">
        <EmptyState
          icon={SearchX}
          title="This chat doesn't exist or isn't yours"
          description="It may have been removed, or it belongs to another user."
          action={
            <Button onClick={onNewChat}>
              <Plus aria-hidden="true" /> New chat
            </Button>
          }
        />
      </Card>
    );
  }
  if (load.status === "error") {
    return (
      <Card className="py-0">
        <EmptyState
          icon={CircleAlert}
          title="Couldn't load this chat"
          description={load.error?.message ?? "Something went wrong."}
          action={
            <Button
              variant="outline"
              onClick={() => {
                setLoad({ status: "loading" });
                setAttempt((a) => a + 1);
              }}
            >
              Try again
            </Button>
          }
        />
      </Card>
    );
  }

  const last = messages[messages.length - 1];
  const showSuggestionsFor = !pending && last?.role === "assistant" ? last.localKey : null;

  return (
    <div className="space-y-3">
      <Card className="flex min-h-[32rem] flex-col gap-0 py-0">
        {meta?.job_order_id && (
          <div className="flex items-center gap-2 border-b px-4 py-2.5 text-xs text-muted-foreground sm:px-6">
            <Briefcase className="size-3.5 shrink-0" aria-hidden="true" />
            <span className="min-w-0 truncate">
              About{" "}
              <Link href={`/job-orders/${meta.job_order_id}`} className="font-medium text-foreground hover:underline">
                {meta.job_order_title ?? `job order ${meta.job_order_id}`}
              </Link>
            </span>
          </div>
        )}
        <CardContent className="flex flex-1 flex-col px-0">
          {load.status === "loading" ? (
            <div className="space-y-6 px-4 py-5 sm:px-6" aria-busy="true" aria-label="Loading chat">
              <Skeleton className="ml-auto h-9 w-2/5 rounded-2xl" />
              <Skeleton className="h-24 w-4/5" />
              <Skeleton className="ml-auto h-9 w-1/3 rounded-2xl" />
              <Skeleton className="h-16 w-3/5" />
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center px-6 py-12 text-center">
              <div className="mb-4 flex size-11 items-center justify-center rounded-xl bg-brand-soft text-brand">
                <Sparkles className="size-5" aria-hidden="true" />
              </div>
              <h2 className="text-sm font-semibold">Ask anything about your candidates</h2>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                Every answer links back to the resume lines it came from, and quotes are checked against the resumes. Ask follow-ups
                like &ldquo;which of those have a PMP?&rdquo;
              </p>
              <ul className="mt-6 flex max-w-2xl flex-wrap justify-center gap-2" aria-label="Example questions">
                {EXAMPLES.map((q) => (
                  <li key={q}>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => send(q)}
                      disabled={pending}
                      className="h-auto rounded-full px-3 py-1.5 text-left whitespace-normal"
                    >
                      {q}
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <ol className="flex-1 space-y-6 px-4 py-5 sm:px-6" aria-label="Conversation">
              {messages.map((m) => (
                <li key={m.localKey} data-msg={m.localKey} className="scroll-mt-20">
                  {m.role === "user" ? (
                    <UserMessage m={m} pending={pending} onRetry={() => send(m.content)} />
                  ) : (
                    <AssistantMessage
                      m={m}
                      showSuggestions={m.localKey === showSuggestionsFor}
                      onSuggestion={send}
                      onCite={onCite}
                    />
                  )}
                </li>
              ))}
              {pending && (
                <li>
                  <AssistantShell>
                    <PendingReply />
                  </AssistantShell>
                </li>
              )}
            </ol>
          )}
          <div ref={endRef} />
        </CardContent>
        {meta && !meta.active && !pending && (
          <p className="border-t px-4 py-2 text-xs text-muted-foreground sm:px-6">This chat is closed. Sending a message reopens it.</p>
        )}
        <form
          className="sticky bottom-0 flex items-end gap-2 rounded-b-xl border-t bg-card p-3"
          aria-label="Send a message"
          onSubmit={(e) => {
            e.preventDefault();
            send(text);
          }}
        >
          <label htmlFor="ask-input" className="sr-only">
            Your message
          </label>
          <textarea
            id="ask-input"
            ref={inputRef}
            value={text}
            rows={1}
            maxLength={MAX_CHARS}
            disabled={load.status === "loading"}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                send(text);
              }
            }}
            placeholder={pending ? "Working on it…" : "Ask about your candidate pool…"}
            className="field-sizing-content max-h-40 min-h-9 flex-1 resize-none rounded-lg border border-input bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30"
          />
          <Button type="submit" size="icon-lg" disabled={pending || !text.trim()} aria-label="Send message">
            {pending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <ArrowUp aria-hidden="true" />}
          </Button>
        </form>
      </Card>
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <FileText className="size-3.5 shrink-0" aria-hidden="true" /> Chats are saved for you. Searches cost a few cents of AI usage; greetings are
        free.
      </p>
      <ResumeViewer target={viewer} onClose={() => setViewer(null)} />
    </div>
  );
}

function UserMessage({ m, pending, onRetry }: { m: UIMessage; pending: boolean; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-end gap-2">
      <p
        className={cn(
          "max-w-[85%] rounded-2xl bg-muted px-3.5 py-2 text-sm break-words whitespace-pre-wrap",
          m.failed && "border border-destructive/40",
        )}
      >
        {m.content}
      </p>
      {m.failed && (
        <div role="alert" className="flex max-w-[85%] gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div className="space-y-2">
            <p>Not sent. {m.failed}</p>
            <Button variant="outline" size="xs" onClick={onRetry} disabled={pending}>
              Try again
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function AssistantShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand">
        <Sparkles className="size-3.5" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1 pt-1">{children}</div>
    </div>
  );
}

function AssistantMessage({
  m,
  showSuggestions,
  onSuggestion,
  onCite,
}: {
  m: UIMessage;
  showSuggestions: boolean;
  onSuggestion: (text: string) => void;
  onCite: (c: Citation) => void;
}) {
  const r = SEARCH_KINDS.has(m.kind) ? m.response : null;
  const searched = m.kind === "follow_up" ? r?.standalone_question : null;
  return (
    <AssistantShell>
      <div className="space-y-3">
        {(m.kind === "job_order" || searched) && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {m.kind === "job_order" && (
              <Badge variant="outline" className="gap-1 font-normal">
                <Briefcase className="size-3" aria-hidden="true" /> Job order
              </Badge>
            )}
            {searched && <span className="italic">Searched: {searched}</span>}
          </div>
        )}
        {r ? <Answer text={m.content} r={r} onCite={onCite} /> : <Markdown>{m.content}</Markdown>}
        {showSuggestions && m.suggestions?.length > 0 && (
          <ul className="flex flex-wrap gap-2 pt-1" aria-label="Suggested follow-ups">
            {m.suggestions.slice(0, 3).map((s) => (
              <li key={s}>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onSuggestion(s)}
                  className="h-auto rounded-full px-3 py-1.5 text-left whitespace-normal"
                >
                  {s}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AssistantShell>
  );
}
