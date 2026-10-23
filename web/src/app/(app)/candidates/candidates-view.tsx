"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight, Search, SearchX, Sparkles, X } from "lucide-react";
import { ApiErrorState } from "@/components/api-state";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { QualityBadge } from "@/components/quality-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useApi, type CandidateList, type CandidateRow, type Facets, type SearchResponse } from "@/lib/api";

import { disciplineLabel, formatNumber, formatYears, licenseLabel, qualityLabel, relativeTime } from "@/lib/format";
import { NeedsAttentionList } from "./needs-attention-list";
import { UploadDialog } from "./upload-dialog";

type Row = CandidateRow & { match?: string | null };

const PAGE_SIZE = 50;
const FILTERS = ["discipline", "metro", "license", "quality"] as const;
type FilterKey = (typeof FILTERS)[number];
const ALL_LABELS: Record<FilterKey, string> = {
  discipline: "All disciplines",
  metro: "All metros",
  license: "All licenses",
  quality: "All resumes",
};
const FILTER_LABELS: Record<FilterKey, string> = {
  discipline: "Discipline",
  metro: "Metro",
  license: "License",
  quality: "Resume",
};
const ALL = "__all__"; // Radix Select can't use "" as an item value.

function facetLabel(key: FilterKey, value: string) {
  if (key === "discipline") return disciplineLabel(value);
  if (key === "license") return licenseLabel(value);
  if (key === "quality") return qualityLabel(value);
  return value;
}

/** URL query params are the single source of truth for filters, so every view is shareable. */
function useQueryState() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const set = useCallback((updates: Record<string, string | null>, resetPage = true) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(updates)) {
      if (v === null || v === "") next.delete(k);
      else next.set(k, v);
    }
    if (resetPage) next.delete("page");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [params, pathname, router]);
  return { params, set };
}

function FilterSelect({
  name,
  value,
  options,
  onChange,
  disabled,
}: {
  name: FilterKey;
  disabled?: boolean;
  value: string;
  options: Record<string, number> | undefined;
  onChange: (v: string | null) => void;
}) {
  return (
    <Select disabled={disabled} value={value || ALL} onValueChange={(v) => onChange(v === ALL ? null : v)}>
      <SelectTrigger className="w-full" aria-label={FILTER_LABELS[name]}>
        <SelectValue placeholder={FILTER_LABELS[name]} />
      </SelectTrigger>
      <SelectContent position="popper" className="max-h-80">
        <SelectItem value={ALL}>{ALL_LABELS[name]}</SelectItem>
        {Object.entries(options ?? {}).map(([v, n]) => (
          <SelectItem key={v} value={v}>
            <span className="flex w-full items-center justify-between gap-4">
              <span>{facetLabel(name, v)}</span>
              <span className="text-xs text-muted-foreground tabular-nums">{n}</span>
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function SearchInput({ value, onChange, smart }: { value: string; onChange: (v: string) => void; smart: boolean }) {
  const [text, setText] = useState(value);
  const [synced, setSynced] = useState(value);
  // Follow outside changes to ?q= (top-bar search, "clear filters") without fighting the user's typing.
  if (value !== synced) {
    setSynced(value);
    setText(value);
  }
  useEffect(() => {
    if (text === value) return;
    const t = setTimeout(() => onChange(text.trim()), 300);
    return () => clearTimeout(t);
  }, [text, value, onChange]);
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
      <Input
        type="search"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={smart ? "Describe the candidate, e.g. hospital MEP design" : "Search candidates…"}
        aria-label="Search candidates"
        className="pl-8"
      />
    </div>
  );
}

const ALL_COLUMNS: { label: string; className?: string }[] = [
  { label: "Name" },
  { label: "Discipline", className: "hidden md:table-cell" },
  { label: "Location", className: "hidden lg:table-cell" },
  { label: "Credentials", className: "hidden sm:table-cell" },
  { label: "Experience", className: "hidden md:table-cell text-right" },
  { label: "Resume" },
  { label: "Updated", className: "hidden xl:table-cell" },
];
// Smart search results carry no processed date, so the Updated column is dropped there.
const SMART_COLUMNS = ALL_COLUMNS.filter((c) => c.label !== "Updated");

function CandidateTable() {
  const router = useRouter();
  const { params, set } = useQueryState();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const filters = Object.fromEntries(FILTERS.map((k) => [k, params.get(k) ?? ""])) as Record<FilterKey, string>;
  const q = params.get("q") ?? "";
  const smart = params.get("mode") === "smart";
  const minYears = params.get("min_years") ?? "";
  const hasFilters = Boolean(q || minYears || FILTERS.some((k) => filters[k]));
  const COLUMNS = smart ? SMART_COLUMNS : ALL_COLUMNS;

  const listPath = (() => {
    const api = new URLSearchParams();
    if (smart) {
      // Smart search ranks by meaning (vectors + full text); no paging, quality isn't a search filter.
      if (!q) return null;
      api.set("q", q);
      for (const k of FILTERS) if (filters[k] && k !== "quality") api.set(k, filters[k]);
      if (minYears) api.set("min_years", minYears);
      api.set("limit", "20");
      return `/api/search?${api}`;
    }
    if (q) api.set("q", q);
    for (const k of FILTERS) if (filters[k]) api.set(k, filters[k]);
    if (minYears) api.set("min_years", minYears);
    api.set("limit", String(PAGE_SIZE));
    api.set("offset", String((page - 1) * PAGE_SIZE));
    return `/api/candidates?${api}`;
  })();

  const facets = useApi<Facets>("/api/candidates/facets");
  const list = useApi<CandidateList | SearchResponse>(listPath);
  const raw = list.data;
  // Normalize both endpoints to one row shape; ignore stale data from the other mode while switching.
  const data: { total: number; items: Row[] } | undefined = smart
    ? raw && "query" in raw
      ? {
          total: raw.items.length,
          items: raw.items.map((i) => ({ ...i, subdiscipline: null, city: i.city ?? null, state: null, quality_issues: [], processed_at: null })),
        }
      : undefined
    : raw && "total" in raw
      ? raw
      : undefined;
  const awaitingQuery = smart && !q;
  const total = data?.total ?? 0;
  const from = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(total, page * PAGE_SIZE);
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const clear = () => set({ q: null, min_years: null, discipline: null, metro: null, license: null, quality: null });
  const onSearch = useCallback((v: string) => set({ q: v || null }), [set]);

  if (list.error && !data) return <ApiErrorState error={list.error} onRetry={list.reload} />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-[minmax(0,2fr)_repeat(4,minmax(0,1fr))_7rem]">
        <div className="col-span-2 lg:col-span-1">
          <div className="flex gap-2">
            <div className="min-w-0 flex-1">
              <SearchInput value={q} onChange={onSearch} smart={smart} />
            </div>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={smart ? "default" : "outline"}
                  aria-pressed={smart}
                  onClick={() => set({ mode: smart ? null : "smart" })}
                  className="h-8 shrink-0"
                >
                  <Sparkles aria-hidden="true" /> Smart
                </Button>
              </TooltipTrigger>
              <TooltipContent>Smart search finds candidates by meaning, e.g. &ldquo;hospital MEP design&rdquo;</TooltipContent>
            </Tooltip>
          </div>
        </div>
        {FILTERS.map((k) => (
          <FilterSelect key={k} name={k} disabled={smart && k === "quality"} value={filters[k]} options={facets.data?.[k]} onChange={(v) => set({ [k]: v })} />
        ))}
        <Input
          type="number"
          inputMode="numeric"
          min={0}
          max={60}
          placeholder="Min yrs"
          aria-label="Minimum years of experience"
          defaultValue={minYears}
          key={minYears}
          onBlur={(e) => e.target.value !== minYears && set({ min_years: e.target.value || null })}
          onKeyDown={(e) => e.key === "Enter" && set({ min_years: e.currentTarget.value || null })}
        />
      </div>

      <div className="flex min-h-7 flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
        <p aria-live="polite">
          {awaitingQuery ? (
            "Describe who you're looking for, e.g. “hospital MEP design in Houston”"
          ) : data && smart ? (
            total > 0 ? (
              <>
                <span className="font-medium text-foreground tabular-nums">{total}</span> best matches by meaning
              </>
            ) : (
              "No matches"
            )
          ) : data ? (
            total > 0 ? (
              <>
                <span className="font-medium text-foreground tabular-nums">
                  {formatNumber(from)}–{formatNumber(to)}
                </span>{" "}
                of <span className="tabular-nums">{formatNumber(total)}</span> candidates
              </>
            ) : (
              "No matches"
            )
          ) : (
            "Loading candidates…"
          )}
        </p>
        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={clear}>
            <X aria-hidden="true" /> Clear filters
          </Button>
        )}
      </div>

      <Card className="gap-0 overflow-hidden py-0">
        <Table aria-busy={list.loading}>
          <TableHeader className="bg-muted/40">
            <TableRow className="hover:bg-transparent">
              {COLUMNS.map((c) => (
                <TableHead key={c.label} className={`h-10 px-4 text-xs font-medium tracking-wide text-muted-foreground uppercase ${c.className ?? ""}`}>
                  {c.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody className={list.loading && data ? "opacity-60 transition-opacity" : undefined}>
            {awaitingQuery && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={COLUMNS.length} className="p-0 whitespace-normal">
                  <EmptyState
                    icon={Sparkles}
                    title="Smart search"
                    description="Type what you need in plain words. Results are ranked by meaning, not just keywords, and show the matching resume text."
                  />
                </TableCell>
              </TableRow>
            )}
            {!data && !awaitingQuery &&
              Array.from({ length: 8 }, (_, i) => (
                <TableRow key={i} className="hover:bg-transparent">
                  {COLUMNS.map((c) => (
                    <TableCell key={c.label} className={`px-4 py-3 ${c.className ?? ""}`}>
                      <Skeleton className={c.label === "Name" ? "h-9 w-48" : "h-4 w-20"} />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            {data && data.items.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={COLUMNS.length} className="p-0 whitespace-normal">
                  <EmptyState
                    icon={SearchX}
                    title="No candidates match"
                    description="Try a broader search or remove a filter."
                    action={
                      hasFilters && (
                        <Button variant="outline" onClick={clear}>
                          Clear filters
                        </Button>
                      )
                    }
                  />
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((c, idx) => {
              const href = `/candidates/${c.person_id}`;
              const place = c.city ? [c.city, c.state].filter(Boolean).join(", ") : null;
              const showMetro = c.metro && c.metro !== c.city;
              return (
                <TableRow key={c.person_id} className="cursor-pointer" onClick={() => router.push(href)}>
                  <TableCell className="max-w-72 px-4 py-2.5 whitespace-normal">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                      {smart && (
                        <span className="text-xs text-muted-foreground tabular-nums" aria-label={`Rank ${idx + 1}`}>
                          #{idx + 1}
                        </span>
                      )}
                      <Link href={href} className="font-medium hover:underline focus-visible:underline focus-visible:outline-none" onClick={(e) => e.stopPropagation()}>
                        {c.full_name}
                      </Link>
                      {smart && idx === 0 && (
                        <Badge className="h-4 bg-brand-soft px-1.5 text-[10px] text-brand">Best match</Badge>
                      )}
                    </div>
                    <p className="line-clamp-1 text-xs text-muted-foreground">{c.headline ?? "–"}</p>
                    {c.match && (
                      <p className="mt-1 line-clamp-2 border-l-2 border-brand/40 pl-2 text-xs text-muted-foreground italic">{c.match}</p>
                    )}
                    <p className="text-xs text-muted-foreground lg:hidden">{[c.city, showMetro ? c.metro : null].filter(Boolean).join(" · ")}</p>
                  </TableCell>
                  <TableCell className="hidden px-4 md:table-cell">
                    <span className="text-sm">{disciplineLabel(c.discipline)}</span>
                  </TableCell>
                  <TableCell className="hidden px-4 lg:table-cell">
                    <span className="text-sm">{place ?? c.metro ?? "–"}</span>
                    {place && showMetro && <p className="text-xs text-muted-foreground">{c.metro}</p>}
                  </TableCell>
                  <TableCell className="hidden max-w-56 px-4 whitespace-normal sm:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {c.license_codes.length === 0 && <span className="text-muted-foreground">–</span>}
                      {c.license_codes.map((code) => (
                        <Badge key={code} variant="outline" className="font-normal">
                          {licenseLabel(code)}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="hidden px-4 text-right tabular-nums md:table-cell">{formatYears(c.years_experience)}</TableCell>
                  <TableCell className="px-4">
                    <QualityBadge quality={c.quality} issues={c.quality_issues} short />
                  </TableCell>
                  {!smart && <TableCell className="hidden px-4 text-muted-foreground xl:table-cell">{relativeTime(c.processed_at)}</TableCell>}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>

      {!smart && total > PAGE_SIZE && (
        <nav aria-label="Pagination" className="flex items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">
            Page {page} of {pages}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => set({ page: page > 2 ? String(page - 1) : null }, false)}>
              <ChevronLeft aria-hidden="true" /> Previous
            </Button>
            <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => set({ page: String(page + 1) }, false)}>
              Next <ChevronRight aria-hidden="true" />
            </Button>
          </div>
        </nav>
      )}
    </div>
  );
}

export function CandidatesView() {
  const { params, set } = useQueryState();
  const tab = params.get("tab") === "attention" ? "attention" : "all";
  const facets = useApi<Facets>("/api/candidates/facets");
  const attention = facets.data?.files?.needs_attention;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Candidates"
        description="Every ingested resume as a structured, searchable profile."
        actions={<UploadDialog />}
      />
      <Tabs value={tab} onValueChange={(v) => set({ tab: v === "attention" ? "attention" : null }, false)}>
        <TabsList>
          <TabsTrigger value="all">All candidates</TabsTrigger>
          <TabsTrigger value="attention">
            Needs attention
            {attention ? (
              <Badge variant="secondary" className="ml-1 h-4 px-1.5 text-[10px] tabular-nums">
                {attention}
              </Badge>
            ) : null}
          </TabsTrigger>
        </TabsList>
      </Tabs>
      {tab === "all" ? <CandidateTable /> : <NeedsAttentionList />}
    </div>
  );
}
