import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/** Soft brand tile holding a page or card icon. */
export function IconTile({
  icon: Icon,
  className,
  tone = "brand",
  size = "md",
}: {
  icon: LucideIcon;
  className?: string;
  tone?: "brand" | "success" | "warning" | "danger" | "info" | "tamper" | "muted";
  size?: "sm" | "md" | "lg";
}) {
  const tones = {
    brand: "bg-brand-soft text-brand ring-brand/15",
    success: "bg-success-soft text-success-strong ring-success/20",
    warning: "bg-warning-soft text-warning-strong ring-warning/25",
    danger: "bg-danger-soft text-danger-strong ring-danger/20",
    info: "bg-info-soft text-info-strong ring-info/20",
    tamper: "bg-tamper-soft text-tamper-strong ring-tamper/20",
    muted: "bg-muted text-muted-foreground ring-border",
  };
  const sizes = { sm: "size-8 rounded-lg [&>svg]:size-4", md: "size-10 rounded-xl [&>svg]:size-[18px]", lg: "size-11 rounded-xl [&>svg]:size-5" };
  return (
    <span
      aria-hidden="true"
      className={cn("flex shrink-0 items-center justify-center ring-1 ring-inset", tones[tone], sizes[size], className)}
    >
      <Icon />
    </span>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  icon,
  eyebrow,
  className,
}: {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  /** Optional icon shown in a soft brand tile left of the title. */
  icon?: LucideIcon;
  /** Small label above the title, e.g. a date or section name. */
  eyebrow?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between", className)}>
      <div className="flex min-w-0 items-center gap-3.5">
        {icon && <IconTile icon={icon} size="lg" className="hidden sm:flex" />}
        <div className="min-w-0 space-y-1">
          {eyebrow && <p className="text-xs font-medium text-muted-foreground">{eyebrow}</p>}
          <h1 className="text-2xl leading-tight font-semibold tracking-[-0.022em] sm:text-[26px]">{title}</h1>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
