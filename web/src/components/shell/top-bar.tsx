"use client";

import { Fragment, Suspense, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { breadcrumbFor } from "./nav";
import { UserMenu } from "./user-menu";

function SearchBox() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);

  // ⌘K / Ctrl+K focuses the search from anywhere in the portal.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        input.current?.focus();
        input.current?.select();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Jumps to the candidates table with the query applied; the table owns the live search.
  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const q = String(new FormData(e.currentTarget).get("q") ?? "").trim();
    router.push(q ? `/candidates?q=${encodeURIComponent(q)}` : "/candidates");
    input.current?.blur();
  }
  return (
    <form role="search" onSubmit={onSubmit} className="group/search relative hidden w-64 sm:block lg:w-80">
      <Search
        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within/search:text-brand"
        aria-hidden="true"
      />
      <input
        ref={input}
        type="search"
        name="q"
        placeholder="Search candidates…"
        aria-label="Search candidates"
        aria-keyshortcuts="Meta+K Control+K"
        className="h-9 w-full rounded-lg border border-transparent bg-muted/70 pr-12 pl-9 text-sm shadow-none transition-[background-color,border-color,box-shadow] duration-150 outline-none placeholder:text-muted-foreground hover:bg-muted focus-visible:border-ring focus-visible:bg-card focus-visible:ring-3 focus-visible:ring-ring/25 [&::-webkit-search-cancel-button]:hidden"
      />
      <kbd
        className="pointer-events-none absolute top-1/2 right-2 hidden -translate-y-1/2 items-center gap-0.5 rounded-md border bg-card px-1.5 font-sans text-[11px] font-medium text-muted-foreground shadow-xs group-focus-within/search:opacity-0 md:inline-flex"
        aria-hidden="true"
      >
        ⌘K
      </kbd>
    </form>
  );
}

function Crumbs() {
  const crumbs = breadcrumbFor(usePathname());
  return (
    <BreadcrumbList className="flex-nowrap text-[13px]">
      {crumbs.map((c, i) => (
        <Fragment key={c}>
          {i > 0 && <BreadcrumbSeparator />}
          <BreadcrumbItem className="min-w-0">
            {i === crumbs.length - 1 ? (
              <BreadcrumbPage className="truncate font-semibold">{c}</BreadcrumbPage>
            ) : (
              <span className="truncate">{c}</span>
            )}
          </BreadcrumbItem>
        </Fragment>
      ))}
    </BreadcrumbList>
  );
}

export function TopBar() {
  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b bg-background/75 px-3 backdrop-blur-md supports-backdrop-filter:bg-background/65 sm:h-16 sm:px-6">
      <SidebarTrigger className="-ml-1 text-muted-foreground hover:text-foreground" aria-label="Toggle sidebar" />
      <Separator orientation="vertical" className="mr-1 data-vertical:h-4 data-vertical:self-center" />
      <Breadcrumb className="min-w-0 flex-1">
        {/* usePathname needs a Suspense boundary under Cache Components (see app-sidebar.tsx). */}
        <Suspense fallback={null}>
          <Crumbs />
        </Suspense>
      </Breadcrumb>
      <div className="flex items-center gap-1 sm:gap-2">
        <SearchBox />
        {/* Phones: the search field is hidden, so offer a button to the searchable table. */}
        <Button variant="ghost" size="icon" className="sm:hidden" asChild>
          <Link href="/candidates" aria-label="Search candidates">
            <Search />
          </Link>
        </Button>
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
