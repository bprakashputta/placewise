"use client";

import { Fragment, useEffect, useState } from "react";
import { ResumeViewer, type ViewerTarget } from "@/components/resume-viewer";

type Progress = {
  stage: string; status: string; total: number; done: number; ok: number; rejected: number;
  retried: number; cost_usd: number; elapsed_s: number; eta_s: number | null; updated_at: string;
};
type Stats = {
  candidates: number; people: number; written: number; rendered: number; job_orders: number;
  by_discipline: Record<string, number>; by_metro: Record<string, number>; by_format: Record<string, number>;
  by_split: Record<string, number>; credentials: Record<string, number>; tricky: Record<string, number>;
  quality?: Record<string, number>;
  updated_at: string;
};
type Showcase = {
  candidate_id: string; name: string; discipline: string; city: string; metro: string; years_experience: number;
  current_title: string; current_employer: string; license_codes: string[]; credential_texts: string[];
  software: string[]; tricky: string[]; quality: string; quality_issues: string[]; file: string; file_format: string; template: string; note: string;
  text_preview: string;
};
type JobOrder = { job_order_id: string; title: string; split: string; notes: string | null; spec: Record<string, unknown> | null };
type Status = { progress: Progress | null; stats: Stats | null; showcase: Showcase[]; job_orders: JobOrder[] };

const nice = (s: string) => s.replace(/_/g, " ");
const QUALITY_STYLE: Record<string, string> = {
  polished: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  flawed: "bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  unusable: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
  adversarial: "bg-fuchsia-50 text-fuchsia-700 dark:bg-fuchsia-950 dark:text-fuchsia-300",
};
const fmtSecs = (s: number | null) => (s == null ? "-" : s < 90 ? `${Math.round(s)}s` : `${Math.round(s / 60)} min`);

function Card({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-neutral-500">{sub}</p>}
    </div>
  );
}

function Bars({ title, data, total }: { title: string; data: Record<string, number>; total: number }) {
  const entries = Object.entries(data);
  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <p className="mb-3 text-sm font-semibold">{title}</p>
      {entries.length === 0 && <p className="text-sm text-neutral-500">No data yet</p>}
      <ul className="space-y-1.5">
        {entries.map(([k, v]) => (
          <li key={k} className="grid grid-cols-[minmax(0,10rem)_1fr_3rem] items-center gap-2 text-sm">
            <span className="truncate" title={nice(k)}>{nice(k)}</span>
            <span className="h-2 rounded-full bg-neutral-100 dark:bg-neutral-800">
              <span className="block h-2 rounded-full bg-indigo-500" style={{ width: `${Math.max(2, (v / Math.max(total, 1)) * 100)}%` }} />
            </span>
            <span className="text-right tabular-nums text-neutral-500">{v}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SeedDashboard() {
  const [data, setData] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);
  const [samples, setSamples] = useState<string[]>([]);

  useEffect(() => {
    fetch("/api/dev/seed/samples", { cache: "no-store" }).then((r) => (r.ok ? r.json() : [])).then(setSamples).catch(() => {});
  }, []);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch("/api/dev/seed/status", { cache: "no-store" });
        if (!res.ok) throw new Error(String(res.status));
        const json = (await res.json()) as Status;
        if (alive) { setData(json); setError(null); }
      } catch {
        if (alive) setError("Seed API unavailable. It runs only in dev mode (APP_ENV=dev).");
      }
    };
    load();
    const t = setInterval(load, 2000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (error) return <p className="text-sm text-red-600 dark:text-red-400">{error}</p>;
  if (!data) return <p className="text-sm text-neutral-500">Loading…</p>;
  const { progress: p, stats: s, showcase, job_orders } = data;
  const pct = p && p.total ? Math.round((p.done / p.total) * 100) : 0;

  return (
    <div className="space-y-8">
      <ResumeViewer target={viewer} onClose={() => setViewer(null)} />
      {p && (
        <section className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-semibold capitalize">{p.stage}</p>
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${p.status === "running"
              ? "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
              : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"}`}>
              {p.status === "running" ? "Running" : "Done"}
            </span>
          </div>
          <div className="mt-3 h-2.5 rounded-full bg-neutral-100 dark:bg-neutral-800" role="progressbar"
               aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-2.5 rounded-full bg-indigo-500 transition-all" style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-2 text-sm text-neutral-500 tabular-nums">
            {p.done} / {p.total} ({pct}%) · passed fact check {p.ok} · self-corrected on retry {p.retried} ·
            rejected {p.rejected} · cost ${p.cost_usd.toFixed(3)} · elapsed {fmtSecs(p.elapsed_s)}
            {p.status === "running" && <> · about {fmtSecs(p.eta_s)} left</>}
          </p>
        </section>
      )}

      {s && (
        <>
          <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Card label="Candidates" value={s.candidates} sub={`${s.people} unique people`} />
            <Card label="Resumes written" value={s.written} />
            <Card label="Files rendered" value={s.rendered}
                  sub={Object.entries(s.by_format).map(([k, v]) => `${v} ${k}`).join(" · ") || undefined} />
            <Card label="Job orders" value={s.job_orders} />
            <Card label="Dev / test split" value={`${s.by_split.dev ?? 0} / ${s.by_split.test ?? 0}`} sub="split by person" />
          </section>
          <section className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            <Bars title="Discipline" data={s.by_discipline} total={s.candidates} />
            <Bars title="Metro" data={s.by_metro} total={s.candidates} />
            <Bars title="Credentials actually held" data={s.credentials} total={s.candidates} />
            <Bars title="Edge cases built in" data={s.tricky} total={s.candidates} />
            {s.quality && <Bars title="Resume quality (deliberate, labeled)" data={s.quality} total={s.candidates} />}
          </section>
        </>
      )}

      {samples.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Template samples <span className="text-sm font-normal text-neutral-500">(one per layout, for review)</span></h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {samples.map((name) => {
              const label = name.startsWith("two_column") ? "two column" : name.startsWith("ats_plain") ? "ATS plain"
                : name.split("_")[0];
              const person = name.replace(".pdf", "").split("_").slice(-2).join(" ");
              return (
                <button key={name} onClick={() => setViewer({ title: person, subtitle: `${label} template`,
                          viewUrl: `/api/dev/seed/samples/${name}`, downloadUrl: `/api/dev/seed/samples/${name}?download=true` })}
                        className="rounded-xl border border-neutral-200 bg-white p-4 text-left shadow-sm transition hover:border-indigo-400 hover:shadow dark:border-neutral-800 dark:bg-neutral-900">
                  <p className="text-xs font-medium uppercase tracking-wide text-indigo-600 dark:text-indigo-400">{label}</p>
                  <p className="mt-1 font-medium">{person}</p>
                  <p className="mt-2 text-xs text-neutral-500">Click to view</p>
                </button>
              );
            })}
          </div>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Showcase candidates <span className="text-sm font-normal text-neutral-500">(dev split, answers visible)</span></h2>
        {showcase.length === 0 && <p className="text-sm text-neutral-500">Samples appear after rendering.</p>}
        <div className="overflow-x-auto rounded-xl border border-neutral-200 dark:border-neutral-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500 dark:bg-neutral-900">
              <tr><th className="px-3 py-2">Candidate</th><th className="px-3 py-2">Discipline</th><th className="px-3 py-2">Experience</th>
                <th className="px-3 py-2">True credentials</th><th className="px-3 py-2">Quality</th><th className="px-3 py-2">File</th></tr>
            </thead>
            <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800">
              {showcase.map((c) => (
                <Fragment key={c.candidate_id}>
                  <tr className="align-top hover:bg-neutral-50 dark:hover:bg-neutral-900/60">
                    <td className="px-3 py-2">
                      <button onClick={() => setOpen(open === c.candidate_id ? null : c.candidate_id)}
                              className="text-left font-medium hover:underline">{c.name}</button>
                      <p className="text-xs text-neutral-500">{c.current_title} · {c.current_employer}</p>
                      <p className="text-xs text-neutral-500">{c.city} ({c.metro})</p>
                    </td>
                    <td className="px-3 py-2 capitalize">{nice(c.discipline)}</td>
                    <td className="px-3 py-2 tabular-nums">{c.years_experience} yrs</td>
                    <td className="px-3 py-2">
                      {c.license_codes.length ? c.license_codes.map((l) => (
                        <span key={l} className="mr-1 inline-block rounded bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">{l.replace(":", " · ")}</span>
                      )) : <span className="text-xs text-neutral-500">none</span>}
                      <p className="mt-1 text-xs text-neutral-500">as written: {c.credential_texts.join("; ") || "-"}</p>
                    </td>
                    <td className="px-3 py-2">
                      <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium capitalize ${QUALITY_STYLE[c.quality] ?? ""}`}>
                        {c.quality}{c.quality !== "polished" && " (on purpose)"}</span>
                      {c.quality_issues.length > 0 && <p className="mt-1 text-xs text-neutral-500">{c.quality_issues.map(nice).join(", ")}</p>}
                      {c.note && <p className="text-xs text-neutral-500">{c.note}</p>}
                    </td>
                    <td className="px-3 py-2">
                      <button onClick={() => setViewer({ title: c.name, subtitle: `${c.candidate_id} · ${c.template} template`,
                                viewUrl: `/api/dev/seed/files/${c.candidate_id}/view`, downloadUrl: `/api/dev/seed/files/${c.candidate_id}` })}
                              className="font-medium text-indigo-600 hover:underline dark:text-indigo-400">View resume</button>
                      <p className="text-xs text-neutral-500">{c.template} template</p>
                    </td>
                  </tr>
                  {open === c.candidate_id && (
                    <tr><td colSpan={6} className="bg-neutral-50 px-3 py-3 dark:bg-neutral-900">
                      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-neutral-500">Resume text (first 1,500 characters, after noise)</p>
                      <pre className="max-h-80 overflow-auto whitespace-pre-wrap text-xs">{c.text_preview}</pre>
                    </td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Job orders</h2>
        {job_orders.length === 0 && <p className="text-sm text-neutral-500">Job orders are generated in the next step.</p>}
        <div className="grid gap-3 md:grid-cols-2">
          {job_orders.map((j) => (
            <div key={j.job_order_id} className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
              <p className="font-medium">{j.job_order_id} · {j.title} <span className="text-xs text-neutral-500">({j.split})</span></p>
              {j.notes && <pre className="mt-2 whitespace-pre-wrap text-xs text-neutral-600 dark:text-neutral-300">{j.notes}</pre>}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
