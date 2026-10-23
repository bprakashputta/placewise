"use client";

import { ArrowUp, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { BRAND_SOLID } from "./lib";

export const MAX_CHARS = 2000;

/** The docked input: auto-growing textarea (1–6 rows), round send button, keyboard hint. */
export function Composer({
  value,
  onChange,
  onSend,
  pending,
  disabled,
  inputRef,
  suggestions,
  notice,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: (text: string) => void;
  pending: boolean;
  disabled: boolean;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  suggestions: string[];
  notice?: React.ReactNode;
}) {
  return (
    <div className="relative mx-auto w-full max-w-[720px] px-4 pb-3 before:pointer-events-none before:absolute before:inset-x-0 before:-top-6 before:h-6 before:bg-gradient-to-t before:from-background before:to-transparent sm:px-6 sm:pb-4">
      {suggestions.length > 0 && (
        <ul className="mb-2.5 flex flex-wrap gap-1.5" aria-label="Suggested follow-ups">
          {suggestions.map((s) => (
            <li key={s} className="min-w-0 max-w-full">
              <button
                type="button"
                onClick={() => onSend(s)}
                disabled={pending}
                className="max-w-full truncate rounded-full border bg-background px-3 py-1 text-xs text-foreground/80 shadow-xs outline-none transition-colors hover:border-brand/40 hover:bg-brand-soft hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
              >
                {s}
              </button>
            </li>
          ))}
        </ul>
      )}
      {notice}
      <form
        aria-label="Send a message"
        onSubmit={(e) => {
          e.preventDefault();
          onSend(value);
        }}
        className="flex items-end gap-2 rounded-2xl border bg-card p-2 pl-4 shadow-lg shadow-black/[0.04] transition-[border-color,box-shadow] focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/30 dark:shadow-black/30"
      >
        <label htmlFor="ask-input" className="sr-only">
          Your message
        </label>
        <textarea
          id="ask-input"
          ref={inputRef}
          value={value}
          rows={1}
          maxLength={MAX_CHARS}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              onSend(value);
            }
          }}
          placeholder={pending ? "Working on it…" : "Ask about your candidates…"}
          className="field-sizing-content max-h-[9.75rem] min-h-6 flex-1 resize-none self-center bg-transparent py-1.5 text-[15px] leading-6 outline-none placeholder:text-muted-foreground disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={pending || !value.trim()}
          aria-label="Send message"
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-full shadow-sm outline-none transition-[opacity,transform] focus-visible:ring-3 focus-visible:ring-ring/50 active:scale-95 disabled:opacity-30",
            BRAND_SOLID,
          )}
        >
          {pending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <ArrowUp className="size-4" aria-hidden="true" />}
        </button>
      </form>
      <p className="mt-1.5 hidden text-center text-[11px] text-muted-foreground sm:block">
        <kbd className="font-sans font-medium">Enter</kbd> to send · <kbd className="font-sans font-medium">Shift+Enter</kbd> for a new line · Answers cite the resumes
      </p>
    </div>
  );
}
