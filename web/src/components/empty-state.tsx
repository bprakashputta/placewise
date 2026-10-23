import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description: string;
  /** Optional primary action, usually a disabled Button until the feature ships. */
  action?: React.ReactNode;
  tone?: "brand" | "muted" | "danger" | "success";
  className?: string;
};

const TONES = {
  brand: "bg-brand-soft text-brand ring-brand/15",
  muted: "bg-muted text-muted-foreground ring-border",
  danger: "bg-danger-soft text-danger-strong ring-danger/20",
  success: "bg-success-soft text-success-strong ring-success/20",
};

export function EmptyState({ icon: Icon, title, description, action, tone = "brand", className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-14 text-center", className)}>
      <div className="relative mb-4">
        <div className="absolute inset-0 -m-2 rounded-2xl bg-brand/5 blur-md" aria-hidden="true" />
        <div className={cn("relative flex size-12 items-center justify-center rounded-xl ring-1 ring-inset", TONES[tone])}>
          <Icon className="size-5" aria-hidden="true" />
        </div>
      </div>
      <h2 className="text-[15px] font-semibold tracking-[-0.01em]">{title}</h2>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
