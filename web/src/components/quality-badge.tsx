import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { humanize, issueLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

// polished = green, flawed = amber, unusable = red, adversarial = fuchsia (docs/api-contract.md).
export const QUALITY_STYLES: Record<string, { badge: string; dot: string; bar: string }> = {
  polished: {
    badge: "bg-emerald-500/10 text-emerald-700 ring-emerald-600/20 dark:text-emerald-300 dark:ring-emerald-400/25",
    dot: "bg-emerald-500",
    bar: "bg-emerald-500",
  },
  flawed: {
    badge: "bg-amber-500/10 text-amber-800 ring-amber-600/25 dark:text-amber-300 dark:ring-amber-400/25",
    dot: "bg-amber-500",
    bar: "bg-amber-500",
  },
  unusable: {
    badge: "bg-red-500/10 text-red-700 ring-red-600/20 dark:text-red-300 dark:ring-red-400/25",
    dot: "bg-red-500",
    bar: "bg-red-500",
  },
  adversarial: {
    badge: "bg-fuchsia-500/10 text-fuchsia-700 ring-fuchsia-600/20 dark:text-fuchsia-300 dark:ring-fuchsia-400/25",
    dot: "bg-fuchsia-500",
    bar: "bg-fuchsia-500",
  },
};

const FALLBACK = { badge: "bg-muted text-muted-foreground ring-border", dot: "bg-muted-foreground", bar: "bg-muted-foreground" };

export function qualityStyle(quality: string | null | undefined) {
  return (quality && QUALITY_STYLES[quality]) || FALLBACK;
}

export function QualityBadge({
  quality,
  issues = [],
  className,
}: {
  quality: string | null | undefined;
  issues?: string[];
  className?: string;
}) {
  const style = qualityStyle(quality);
  const badge = (
    <Badge
      className={cn("gap-1.5 ring-1 ring-inset", style.badge, issues.length > 0 && "cursor-help", className)}
      tabIndex={issues.length > 0 ? 0 : undefined}
    >
      <span className={cn("size-1.5 rounded-full", style.dot)} aria-hidden="true" />
      {quality ? humanize(quality) : "Unknown"}
      {issues.length > 0 && <span className="sr-only">: {issues.map(issueLabel).join(", ")}</span>}
    </Badge>
  );
  if (issues.length === 0) return badge;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{badge}</TooltipTrigger>
      <TooltipContent className="max-w-64">
        <ul className="space-y-0.5">
          {issues.map((i) => (
            <li key={i}>• {issueLabel(i)}</li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  );
}
