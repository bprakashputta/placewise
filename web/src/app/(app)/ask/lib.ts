// Display helpers for the Ask workspace (chats list, conversation, candidates panel).
import type { ConversationResponse, ConversationSummary, Message } from "@/lib/api";
import { SEARCH_KINDS } from "@/lib/api";
import { disciplineLabel, humanize, licenseLabel, qualityLabel } from "@/lib/format";

/** A message as shown: server messages plus the optimistic user bubble, which may have failed. */
export type UIMessage = Message & { localKey: string; failed?: string };

export const withKey = (m: Message): UIMessage => ({ ...m, localKey: `m${m.id}` });

// Resume section names from the search index → recruiter wording.
const SECTION_LABELS: Record<string, string> = {
  job: "Work history",
  jobs: "Work history",
  summary: "Summary",
  credentials: "Licenses & certifications",
  skills: "Skills",
  education: "Education",
};

export function sectionLabel(section: string): string {
  return SECTION_LABELS[section] ?? humanize(section);
}

/** "Austin · Austin" → "Austin": the metro is only worth showing when it adds something. */
export function placeLabel(city: string | null, metro: string | null): string {
  return [city, metro && metro !== city ? metro : null].filter(Boolean).join(" · ");
}

/** Indexed chunks start with "[headline | discipline] section: "; the panel only wants the resume text. */
export function cleanSnippet(content: string): string {
  return content.replace(/^\[[^\]]*\]\s*[\w ]+:\s*/, "").trim();
}

/** Plan filters → readable chips, e.g. {license_codes:["PE:TX"], min_years: 8} → "PE · TX", "8+ yrs". */
export function filterChips(filters: Record<string, unknown>): string[] {
  const chips: string[] = [];
  for (const [key, value] of Object.entries(filters ?? {})) {
    if (value === null || value === undefined || value === "" || value === false) continue;
    if (Array.isArray(value)) {
      if (value.length === 0) continue;
      chips.push(...value.map((v) => (key.includes("license") ? licenseLabel(String(v)) : humanize(String(v)))));
    } else if (key === "min_years") chips.push(`${value}+ yrs`);
    else if (key === "discipline") chips.push(disciplineLabel(String(value)));
    else if (key === "metro") chips.push(String(value));
    else if (value === true) chips.push(humanize(key));
    else chips.push(key === "quality" ? qualityLabel(String(value)) : String(value));
  }
  return chips;
}

/** The search response of an assistant message, or null for greetings, help and the like. */
export function searchResponse(m: UIMessage): ConversationResponse | null {
  return m.role === "assistant" && SEARCH_KINDS.has(m.kind) && m.response ? m.response : null;
}

/** Unique people the answer cites, in citation order. */
export function citedPeople(r: ConversationResponse): number[] {
  return [...new Set((r.citations ?? []).map((c) => c.person_id))];
}

export function jobOrderCode(id: number): string {
  return `JO-${String(id).padStart(2, "0")}`;
}

const GREETING_TITLE = /^(hi+|hey+|hello+|yo|hiya|thanks?|thank you|good (morning|afternoon|evening)|help|what can you do)\b/i;

/**
 * Chats that never got past small talk: the default title, or a title that is just a greeting
 * ("Hi there", "hello again"). They stay out of the list unless open. Heuristic: the list API
 * doesn't say which kinds a chat holds.
 */
export function isGreetingOnly(c: ConversationSummary): boolean {
  if (c.job_order_id) return false;
  if (typeof c.has_search === "boolean") return !c.has_search;   // exact, from the API
  const t = (c.title ?? "").trim();
  return !t || t === "New chat" || (GREETING_TITLE.test(t) && t.split(/\s+/).length <= 4 && !t.includes(","));
}

const CHICAGO = "America/Chicago";

function chicagoParts(d: Date) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: CHICAGO,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    hourCycle: "h23",
  }).formatToParts(d);
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value ?? 0);
  return { day: Date.UTC(get("year"), get("month") - 1, get("day")), hour: get("hour") };
}

/** "Good morning" / "Good afternoon" / "Good evening" in Central time (the firm is in DFW). */
export function greetingFor(now: Date): string {
  const { hour } = chicagoParts(now);
  return hour < 5 ? "Good evening" : hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
}

/** Today / Yesterday / Earlier, by calendar day in Central time. */
export function dayBucket(iso: string, now: Date): 0 | 1 | 2 {
  const diff = (chicagoParts(now).day - chicagoParts(new Date(iso)).day) / 86_400_000;
  return diff <= 0 ? 0 : diff === 1 ? 1 : 2;
}

/** "now", "2m", "3h", "Mon", "Oct 12". */
export function relativeTime(iso: string, now: Date): string {
  const then = new Date(iso);
  const mins = Math.max(0, Math.round((now.getTime() - then.getTime()) / 60_000));
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  if (mins < 24 * 60) return `${Math.round(mins / 60)}h`;
  if (mins < 6 * 24 * 60) return new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: CHICAGO }).format(then);
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: CHICAGO }).format(then);
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}

// Avatar tints: soft background + readable text in both themes.
const AVATAR_TINTS = [
  "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  "bg-violet-500/15 text-violet-700 dark:text-violet-300",
  "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  "bg-amber-500/15 text-amber-800 dark:text-amber-300",
  "bg-rose-500/15 text-rose-700 dark:text-rose-300",
  "bg-teal-500/15 text-teal-700 dark:text-teal-300",
  "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300",
  "bg-orange-500/15 text-orange-800 dark:text-orange-300",
];

export function avatarTint(key: string | number): string {
  const s = String(key);
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return AVATAR_TINTS[Math.abs(h) % AVATAR_TINTS.length];
}

/** Solid brand fill with white text; deepened in dark mode, where the brand token is light, to keep AA contrast. */
export const BRAND_SOLID =
  "bg-brand text-white hover:bg-brand/90 dark:bg-[color-mix(in_oklch,var(--brand)_82%,black)] dark:hover:bg-[color-mix(in_oklch,var(--brand)_90%,black)]";

/** Entry animation for new content; skipped for people who prefer reduced motion. */
export const ENTER = "motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-1.5 motion-safe:duration-200";
