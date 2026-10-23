import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { issueLabel, qualityLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

// polished = success, flawed = warning, unusable = danger, adversarial = tamper (docs/api-contract.md).
export const QUALITY_STYLES: Record<string, { badge: string; dot: string; bar: string }> = {
  polished: {
    badge: "bg-success-soft text-success-strong ring-success/25",
    dot: "bg-success",
    bar: "bg-success",
  },
  flawed: {
    badge: "bg-warning-soft text-warning-strong ring-warning/30",
    dot: "bg-warning",
    bar: "bg-warning",
  },
  unusable: {
    badge: "bg-danger-soft text-danger-strong ring-danger/25",
    dot: "bg-danger",
    bar: "bg-danger",
  },
  adversarial: {
    badge: "bg-tamper-soft text-tamper-strong ring-tamper/25",
    dot: "bg-tamper",
    bar: "bg-tamper",
  },
};

const FALLBACK = { badge: "bg-muted text-muted-foreground ring-border", dot: "bg-muted-foreground", bar: "bg-muted-foreground" };

export function qualityStyle(quality: string | null | undefined) {
  return (quality && QUALITY_STYLES[quality]) || FALLBACK;
}

export function QualityBadge({
  quality,
  issues = [],
  short = false,
  className,
}: {
  quality: string | null | undefined;
  issues?: string[];
  /** Short label where space is tight ("Tampered" instead of "Tampered (hidden instructions)"). */
  short?: boolean;
  className?: string;
}) {
  const style = qualityStyle(quality);
  const badge = (
    <Badge
      className={cn("gap-1.5 ring-1 ring-inset", style.badge, issues.length > 0 && "cursor-help", className)}
      tabIndex={issues.length > 0 ? 0 : undefined}
    >
      <span className={cn("size-1.5 rounded-full", style.dot)} aria-hidden="true" />
      {qualityLabel(quality, short)}
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
