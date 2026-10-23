import { cn } from "@/lib/utils";

// Placewise mark: a map pin on a gradient indigo tile.
export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-8 shrink-0 items-center justify-center rounded-[9px] bg-brand-gradient text-white shadow-[inset_0_1px_0_0_oklch(1_0_0/0.25),0_1px_2px_0_oklch(0.3_0.15_274/0.35),0_4px_12px_-4px_oklch(0.5_0.2_274/0.5)]",
        className,
      )}
    >
      <svg viewBox="0 0 24 24" fill="none" className="size-[60%]">
        <path
          d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 1 1 13 0c0 5.4-6.5 11-6.5 11Z"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        <circle cx="12" cy="10" r="2.25" fill="currentColor" />
      </svg>
    </span>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className="text-[15px] font-semibold tracking-tight">Placewise</span>
    </span>
  );
}
