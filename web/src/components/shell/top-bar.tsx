"use client";

import { Fragment } from "react";
import { usePathname } from "next/navigation";
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
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { breadcrumbFor } from "./nav";
import { UserMenu } from "./user-menu";

function SearchBox() {
  // Disabled inputs don't fire pointer events, so the tooltip hangs off a focusable wrapper.
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          tabIndex={0}
          aria-label="Search candidates (available after ingest)"
          className="relative hidden w-64 rounded-lg outline-none focus-visible:ring-3 focus-visible:ring-ring/50 sm:block lg:w-80"
        >
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            type="search"
            placeholder="Search candidates…"
            disabled
            tabIndex={-1}
            aria-hidden="true"
            className="pl-8"
          />
        </div>
      </TooltipTrigger>
      <TooltipContent>Available after ingest</TooltipContent>
    </Tooltip>
  );
}

export function TopBar() {
  const crumbs = breadcrumbFor(usePathname());
  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/80 px-3 backdrop-blur supports-backdrop-filter:bg-background/70 sm:px-4">
      <SidebarTrigger className="-ml-1" aria-label="Toggle sidebar" />
      <Separator orientation="vertical" className="mr-1 data-vertical:h-4 data-vertical:self-center" />
      <Breadcrumb className="min-w-0 flex-1">
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
      </Breadcrumb>
      <div className="flex items-center gap-1 sm:gap-2">
        <SearchBox />
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
