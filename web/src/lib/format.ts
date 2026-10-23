// Display helpers shared by the portal pages (rules from docs/api-contract.md).

const DISCIPLINES: Record<string, string> = {
  architecture: "Architecture",
  interior_design: "Interior design",
  civil: "Civil",
  structural: "Structural",
  mep: "MEP",
  construction_management: "Construction mgmt",
};

const CREDENTIALS: Record<string, string> = {
  LEED_AP: "LEED AP",
  LEED_GA: "LEED GA",
  OSHA_30: "OSHA 30",
  TX_RID: "RID",
};

const ISSUES: Record<string, string> = {
  hidden_text: "Hidden text",
  prompt_injection: "Instructions aimed at AI systems",
  image_only_pdf: "Scanned image (no text layer)",
  corrupt_file: "Corrupt file",
  unusual_headers: "Unusual section headers",
  unusual_headings: "Unusual section headings",
  no_quantified_results: "No quantified results",
};

/** "construction_management" → "Construction mgmt"; unknown values get sentence case. */
export function disciplineLabel(value: string | null | undefined): string {
  if (!value) return "–";
  return DISCIPLINES[value] ?? humanize(value);
}

/** "PE:TX" → "PE · TX", "LEED_AP" → "LEED AP". */
export function licenseLabel(code: string): string {
  const [key, state] = code.split(":");
  const name = CREDENTIALS[key] ?? key.replace(/_/g, " ");
  return state ? `${name} · ${state}` : name;
}

export function credentialLabel(key: string, state: string | null): string {
  return licenseLabel(state ? `${key}:${state}` : key);
}

export function issueLabel(issue: string): string {
  return ISSUES[issue] ?? humanize(issue);
}

export function humanize(value: string): string {
  const s = value.replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function formatYears(years: number | null | undefined): string {
  if (years === null || years === undefined) return "–";
  return `${Number.isInteger(years) ? years : years.toFixed(1)} yrs`;
}

export function formatUsd(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "–";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "–";
  return new Intl.NumberFormat("en-US").format(value);
}

const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

/** "3 hours ago", "yesterday", or a short date when older than a week. */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  const then = new Date(iso);
  const diff = (then.getTime() - Date.now()) / 1000;
  const abs = Math.abs(diff);
  if (abs < 60) return "just now";
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  if (abs < 7 * 86400) return rtf.format(Math.round(diff / 86400), "day");
  return formatDate(iso);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}
