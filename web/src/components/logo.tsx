import { cn } from "@/lib/utils";

// Placewise mark: a map pin on an indigo tile.
export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand text-white shadow-sm",
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
