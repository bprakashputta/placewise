"use client";

import { Fragment, Suspense } from "react";
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
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { breadcrumbFor } from "./nav";
import { UserMenu } from "./user-menu";

function SearchBox() {
  const router = useRouter();
  // Jumps to the candidates table with the query applied; the table owns the live search.
  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const q = String(new FormData(e.currentTarget).get("q") ?? "").trim();
    router.push(q ? `/candidates?q=${encodeURIComponent(q)}` : "/candidates");
  }
  return (
    <form role="search" onSubmit={onSubmit} className="relative hidden w-64 sm:block lg:w-80">
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
      <Input type="search" name="q" placeholder="Search candidates…" aria-label="Search candidates" className="pl-8" />
    </form>
  );
}

function Crumbs() {
  const crumbs = breadcrumbFor(usePathname());
  return (
    <BreadcrumbList className="flex-nowrap">
      {crumbs.map((c, i) => (
        <Fragment key={c}>
          {i > 0 && <BreadcrumbSeparator />}
          <BreadcrumbItem className="min-w-0">
            {i === crumbs.length - 1 ? (
              <BreadcrumbPage className="truncate font-medium">{c}</BreadcrumbPage>
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
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/80 px-3 backdrop-blur supports-backdrop-filter:bg-background/70 sm:px-4">
      <SidebarTrigger className="-ml-1" aria-label="Toggle sidebar" />
      <Separator orientation="vertical" className="mr-1 data-vertical:h-4 data-vertical:self-center" />
      <Breadcrumb className="min-w-0 flex-1">
        {/* usePathname needs a Suspense boundary under Cache Components (see app-sidebar.tsx). */}
        <Suspense fallback={null}>
          <Crumbs />
        </Suspense>
      </Breadcrumb>
      <div className="flex items-center gap-1 sm:gap-2">
        <SearchBox />
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
