"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CircleAlert, Lock, MessagesSquare, PanelLeftOpen, PanelRightOpen, Plus, SearchX, SquarePen, Users } from "lucide-react";
import { ResumeViewer, type ViewerTarget } from "@/components/resume-viewer";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useSidebar } from "@/components/ui/sidebar";
import { ApiError, apiFetch, useApi, type Citation, type Conversation, type ConversationSummary, type SendMessageResponse } from "@/lib/api";
import { cn } from "@/lib/utils";
import { CandidatesPanel, type OpenResume } from "./candidates-panel";
import { ChatsList } from "./chats-list";
import { Composer, MAX_CHARS } from "./composer";
import { BRAND_SOLID, ENTER, searchResponse, sectionLabel, withKey, type UIMessage } from "./lib";
import { AssistantMessage, JobOrderChip, PendingReply, UserMessage } from "./messages";
import { Welcome } from "./welcome";

const TIMEOUT_MS = 90_000;

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

/** `?c=` → conversation id; null = new chat; 0 = present but not a valid id. */
function parseConversationId(raw: string | null): number | null {
  if (raw === null || raw === "") return null;
  return /^\d+$/.test(raw) && Number(raw) > 0 ? Number(raw) : 0;
}

const isWide = (px: number) => typeof window !== "undefined" && window.matchMedia(`(min-width: ${px}px)`).matches;

/**
 * The Ask workspace: chats on the left, the conversation in the middle, the selected answer's
 * candidates on the right. Each column scrolls on its own; the page itself doesn't scroll.
 */
export function AskView() {
  // On Ask the chats list is the navigation, so fold the app menu to its icon rail for more room.
  // It comes back as it was when you leave Ask, and can still be expanded at any time.
  const { open: menuOpen, setOpen: setMenuOpen } = useSidebar();
  const menuWasOpen = useRef(menuOpen);
  useEffect(() => {
    const restore = menuWasOpen.current;
    setMenuOpen(false);
    return () => {
      if (restore) setMenuOpen(true);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const router = useRouter();
  const params = useSearchParams();
  const urlId = parseConversationId(params.get("c"));
  const list = useApi<ConversationSummary[]>("/api/conversations");
  const [chatsSheet, setChatsSheet] = useState(false);
  const [chatsDocked, setChatsDocked] = useState(true);

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
    setChatsSheet(false);
    if (urlId === null) setThread((t) => ({ key: t.key + 1, id: null, created: null }));
    else router.push("/ask");
  }

  function onCreated(id: number) {
    setThread((t) => ({ ...t, created: id }));
    router.replace(`/ask?c=${id}`, { scroll: false });
  }

  const chats = (opts: { onSelect?: () => void; onCollapse?: () => void }) => (
    <ChatsList
      conversations={list.data}
      error={list.error}
      loading={list.loading}
      selectedId={urlId}
      onNewChat={newChat}
      onRetry={list.reload}
      {...opts}
    />
  );

  return (
    <div data-ask-workspace className="relative flex h-[calc(100svh-3.5rem)] sm:h-[calc(100svh-4rem)] w-full min-w-0 overflow-hidden">
      {chatsDocked && (
        <aside className="hidden w-[248px] shrink-0 border-r bg-muted/30 lg:block dark:bg-muted/10">{chats({ onCollapse: () => setChatsDocked(false) })}</aside>
      )}
      <ChatThread
        key={thread.key}
        id={thread.id}
        onCreated={onCreated}
        onChanged={list.reload}
        onNewChat={newChat}
        chatsDocked={chatsDocked}
        onShowChats={() => (isWide(1024) ? setChatsDocked(true) : setChatsSheet(true))}
        listTitle={list.data?.find((c) => c.id === urlId)?.title}
      />
      <Sheet open={chatsSheet} onOpenChange={setChatsSheet}>
        <SheetContent side="left" className="w-[300px] gap-0 p-0 pt-10">
          <SheetHeader className="sr-only">
            <SheetTitle>Chats</SheetTitle>
            <SheetDescription>Your saved Ask conversations.</SheetDescription>
          </SheetHeader>
          {chats({ onSelect: () => setChatsSheet(false) })}
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
  chatsDocked,
  onShowChats,
  listTitle,
}: {
  id: number | null;
  onCreated: (id: number) => void;
  onChanged: () => void;
  onNewChat: () => void;
  chatsDocked: boolean;
  onShowChats: () => void;
  /** The chat's title from the (reloaded) list: the API retitles a chat after a message. */
  listTitle?: string;
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
  // Which answer's candidates the right panel shows; null = the latest one.
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false); // lg–xl overlay
  const [sheetOpen, setSheetOpen] = useState(false); // below lg
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const alive = useRef(true);
  const scrollTarget = useRef<{ to: "bottom" | string; smooth: boolean } | null>(null);
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
        scrollTarget.current = { to: "bottom", smooth: false };
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

  // Scroll after render: to the bottom when a chat opens, or smoothly to the start of the newest
  // question when one is sent or answered (so long answers read from the top).
  useEffect(() => {
    const target = scrollTarget.current;
    if (!target) return;
    scrollTarget.current = null;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const behavior: ScrollBehavior = target.smooth && !reduce ? "smooth" : "auto";
    if (target.to === "bottom") endRef.current?.scrollIntoView({ block: "end", behavior });
    else document.querySelector(`[data-msg="${target.to}"]`)?.scrollIntoView({ behavior, block: "start" });
  }, [messages, pending]);

  // Esc closes the lg–xl candidates drawer.
  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

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
    scrollTarget.current = { to: localKey, smooth: true };
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
      setMessages((m) => [...m.map((x) => (x.localKey === localKey ? { ...res.user_message, localKey } : x)), withKey(res.assistant_message)]);
      setMeta((m) => m && { ...m, active: true });
      // A new answer with candidates takes over the panel.
      if ((res.assistant_message.response?.candidates?.length ?? 0) > 0) setSelectedKey(null);
      scrollTarget.current = { to: localKey, smooth: true };
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

  const openResume: OpenResume = ({ name, resumeFileId, subtitle }) =>
    setViewer({
      title: name,
      subtitle,
      viewUrl: `/api/candidates/files/${resumeFileId}/view`,
      downloadUrl: `/api/candidates/files/${resumeFileId}`,
    });
  const onCite = (c: Citation) =>
    openResume({ name: c.candidate_name, resumeFileId: c.resume_file_id, subtitle: `${sectionLabel(c.section)}: “${c.quote}”` });

  // Answers with candidates; the panel shows the chosen one, else the latest.
  const withCandidates = messages.filter((m) => (searchResponse(m)?.candidates?.length ?? 0) > 0);
  const selected = withCandidates.find((m) => m.localKey === selectedKey) ?? withCandidates[withCandidates.length - 1] ?? null;
  const panelResponse = selected ? searchResponse(selected) : null;
  const panelCount = panelResponse?.candidates.length ?? 0;

  function showInPanel(key: string) {
    setSelectedKey(key);
    if (isWide(1280)) return;
    if (isWide(1024)) setDrawerOpen(true);
    else setSheetOpen(true);
  }

  const last = messages[messages.length - 1];
  const suggestions = !pending && last?.role === "assistant" ? (last.suggestions ?? []).slice(0, 3) : [];
  const known = listTitle || meta?.title;
  const title = known && known !== "New chat" ? known : messages.length > 0 ? "New chat" : "Ask";
  const panel = (onClose?: () => void) => (
    <CandidatesPanel key={selected?.localKey ?? "none"} response={panelResponse} onOpenResume={openResume} onClose={onClose} />
  );

  let body: React.ReactNode;
  if (load.status === "missing" || load.status === "error") {
    const missing = load.status === "missing";
    body = (
      <div className="flex flex-1 flex-col items-center justify-center py-16 text-center">
        <span className="flex size-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
          {missing ? <SearchX className="size-5" aria-hidden="true" /> : <CircleAlert className="size-5" aria-hidden="true" />}
        </span>
        <h2 className="mt-4 text-base font-semibold">{missing ? "This chat doesn't exist or isn't yours" : "Couldn't load this chat"}</h2>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          {missing ? "It may have been removed, or it belongs to another user." : (load.error?.message ?? "Something went wrong.")}
        </p>
        <div className="mt-5">
          {missing ? (
            <Button onClick={onNewChat} className={BRAND_SOLID}>
              <Plus aria-hidden="true" /> New chat
            </Button>
          ) : (
            <Button
              variant="outline"
              onClick={() => {
                setLoad({ status: "loading" });
                setAttempt((a) => a + 1);
              }}
            >
              Try again
            </Button>
          )}
        </div>
      </div>
    );
  } else if (load.status === "loading") {
    body = (
      <div className="space-y-8 py-2" aria-busy="true" aria-label="Loading chat">
        <Skeleton className="ml-auto h-10 w-2/5 rounded-2xl" />
        <div className="flex gap-3">
          <Skeleton className="size-7 rounded-lg" />
          <div className="flex-1 space-y-2.5">
            <Skeleton className="h-4 w-11/12" />
            <Skeleton className="h-4 w-4/5" />
            <Skeleton className="h-4 w-3/5" />
            <Skeleton className="mt-4 h-12 w-full rounded-xl" />
          </div>
        </div>
        <Skeleton className="ml-auto h-10 w-1/3 rounded-2xl" />
        <div className="flex gap-3">
          <Skeleton className="size-7 rounded-lg" />
          <div className="flex-1 space-y-2.5">
            <Skeleton className="h-4 w-4/5" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        </div>
      </div>
    );
  } else if (messages.length === 0 && !pending) {
    body = <Welcome onPick={send} disabled={pending} />;
  } else {
    body = (
      <ol className="space-y-8" aria-label="Conversation">
        {messages.map((m) => (
          <li key={m.localKey} data-msg={m.localKey} className={cn("scroll-mt-6", ENTER)}>
            {m.role === "user" ? (
              <UserMessage m={m} pending={pending} onRetry={() => send(m.content)} />
            ) : (
              <AssistantMessage m={m} inPanel={selected?.localKey === m.localKey} onShowInPanel={() => showInPanel(m.localKey)} onCite={onCite} />
            )}
          </li>
        ))}
        {pending && (
          <li className={ENTER}>
            <PendingReply />
          </li>
        )}
      </ol>
    );
  }

  return (
    <>
      <section className="flex min-w-0 flex-1 flex-col bg-background" aria-label="Conversation">
        <header className="flex h-12 shrink-0 items-center gap-1.5 border-b px-2 sm:px-3">
          <Button variant="ghost" size="icon-sm" className="text-muted-foreground lg:hidden" onClick={onShowChats} aria-label="Show chats">
            <MessagesSquare aria-hidden="true" />
          </Button>
          {!chatsDocked && (
            <Button variant="ghost" size="icon-sm" className="hidden text-muted-foreground lg:inline-flex" onClick={onShowChats} aria-label="Show chats" title="Show chats">
              <PanelLeftOpen aria-hidden="true" />
            </Button>
          )}
          <div className="flex min-w-0 flex-1 items-center gap-2 pl-1">
            {load.status === "loading" ? (
              <Skeleton className="h-4 w-48" />
            ) : (
              <h1 className="truncate text-sm font-semibold" title={title}>
                {title}
              </h1>
            )}
            {meta?.job_order_id && <JobOrderChip id={meta.job_order_id} title={meta.job_order_title && meta.job_order_title !== meta.title ? meta.job_order_title : null} />}
            {meta && !meta.active && (
              <span className="hidden shrink-0 items-center gap-1 text-[11px] text-muted-foreground sm:inline-flex">
                <Lock className="size-3" aria-hidden="true" /> Closed
              </span>
            )}
          </div>
          {panelCount > 0 && (
            <>
              <Button variant="outline" size="sm" className="gap-1.5 lg:hidden" onClick={() => setSheetOpen(true)} aria-label={`Candidates (${panelCount})`}>
                <Users aria-hidden="true" /> <span className="hidden sm:inline">Candidates</span>
                <span className="text-muted-foreground tabular-nums">
                  <span className="hidden sm:inline">(</span>
                  {panelCount}
                  <span className="hidden sm:inline">)</span>
                </span>
              </Button>
              <Button
                variant={drawerOpen ? "secondary" : "outline"}
                size="sm"
                className="hidden gap-1.5 lg:inline-flex xl:hidden"
                onClick={() => setDrawerOpen((o) => !o)}
                aria-expanded={drawerOpen}
              >
                <PanelRightOpen aria-hidden="true" /> Candidates <span className="text-muted-foreground tabular-nums">({panelCount})</span>
              </Button>
            </>
          )}
          {messages.length > 0 && (
            <Button variant="ghost" size="icon-sm" className="text-muted-foreground" onClick={onNewChat} aria-label="New chat" title="New chat">
              <SquarePen aria-hidden="true" />
            </Button>
          )}
        </header>

        <div className="relative min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
          <div className="@container mx-auto flex min-h-full w-full max-w-[760px] flex-col px-4 pt-6 pb-4 sm:px-6 sm:pt-8">
            {body}
            <div ref={endRef} />
          </div>
        </div>

        {load.status !== "missing" && load.status !== "error" && (
          <Composer
            value={text}
            onChange={setText}
            onSend={send}
            pending={pending}
            disabled={load.status === "loading"}
            inputRef={inputRef}
            suggestions={suggestions}
            notice={
              meta && !meta.active && !pending ? (
                <p className="mb-2 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
                  <Lock className="size-3" aria-hidden="true" /> This chat is closed. Sending a message reopens it.
                </p>
              ) : null
            }
          />
        )}
      </section>

      {/* ≥ xl: docked candidates column. */}
      <aside className="hidden w-[400px] shrink-0 border-l bg-muted/30 xl:block 2xl:w-[460px] dark:bg-muted/10" aria-label="Candidates">
        {panel()}
      </aside>

      {/* lg–xl: the same panel as an overlay drawer. */}
      {drawerOpen && (
        <>
          <div className="absolute inset-0 z-20 hidden bg-black/20 motion-safe:animate-in motion-safe:fade-in-0 lg:block xl:hidden" onClick={() => setDrawerOpen(false)} aria-hidden="true" />
          <aside
            className="absolute inset-y-0 right-0 z-30 hidden w-[380px] max-w-[90%] border-l bg-background shadow-2xl motion-safe:animate-in motion-safe:slide-in-from-right-8 motion-safe:duration-200 lg:block xl:hidden"
            aria-label="Candidates"
          >
            {panel(() => setDrawerOpen(false))}
          </aside>
        </>
      )}

      {/* Below lg: a bottom sheet. */}
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="bottom" showCloseButton={false} className="gap-0 rounded-t-2xl p-0 data-[side=bottom]:h-[85svh]">
          <SheetHeader className="sr-only">
            <SheetTitle>Candidates</SheetTitle>
            <SheetDescription>Candidates from the selected answer.</SheetDescription>
          </SheetHeader>
          <div className="mx-auto mt-2 h-1 w-10 shrink-0 rounded-full bg-muted-foreground/25" aria-hidden="true" />
          <div className="min-h-0 flex-1">{panel(() => setSheetOpen(false))}</div>
        </SheetContent>
      </Sheet>

      <ResumeViewer target={viewer} onClose={() => setViewer(null)} />
    </>
  );
}
