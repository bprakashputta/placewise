"use client";

import { Suspense } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { useUser } from "@/components/auth/user-provider";
import { LogoMark } from "@/components/logo";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { initials } from "@/lib/format";
import { ADMIN_NAV, MAIN_NAV, isActive, type NavItem } from "./nav";

// Active item: soft brand pill with a short accent bar on the left edge.
const ITEM_CLASS =
  "relative h-9 gap-2.5 rounded-lg px-2.5 font-medium text-sidebar-foreground transition-colors duration-150 " +
  "[&_svg]:text-muted-foreground hover:[&_svg]:text-sidebar-accent-foreground " +
  "before:absolute before:top-2 before:bottom-2 before:left-0 before:w-[3px] before:rounded-r-full before:bg-brand before:opacity-0 before:transition-opacity " +
  "data-active:bg-brand-soft data-active:text-brand-strong data-active:before:opacity-100 data-active:[&_svg]:text-brand " +
  "group-data-[collapsible=icon]:before:hidden";

function NavList({ items, pathname }: { items: NavItem[]; pathname: string }) {
  const { isMobile, setOpenMobile } = useSidebar();
  return (
    <SidebarMenu className="gap-0.5">
      {items.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <SidebarMenuItem key={item.href}>
            <SidebarMenuButton asChild isActive={active} tooltip={item.title} className={ITEM_CLASS}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                onClick={() => isMobile && setOpenMobile(false)}
              >
                <item.icon aria-hidden="true" />
                <span>{item.title}</span>
              </Link>
            </SidebarMenuButton>
            {item.badge && (
              <SidebarMenuBadge className="top-2 rounded-full border bg-card px-1.5 text-[10px] font-medium text-muted-foreground">
                {item.badge}
              </SidebarMenuBadge>
            )}
          </SidebarMenuItem>
        );
      })}
    </SidebarMenu>
  );
}

// usePathname is runtime URL data: with Cache Components it must sit under a Suspense boundary
// (dynamic routes like /candidates/[id] otherwise block prerendering). The fallback is the same
// list with nothing highlighted.
function ActiveNavList({ items }: { items: NavItem[] }) {
  return <NavList items={items} pathname={usePathname()} />;
}

function Nav({ items }: { items: NavItem[] }) {
  return (
    <Suspense fallback={<NavList items={items} pathname="" />}>
      <ActiveNavList items={items} />
    </Suspense>
  );
}

function UserCard() {
  const { user, signOut } = useUser();
  if (!user) {
    return (
      <div className="flex items-center gap-2.5 p-2 group-data-[collapsible=icon]:p-0">
        <Skeleton className="size-8 rounded-full" />
        <Skeleton className="h-4 flex-1 group-data-[collapsible=icon]:hidden" />
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2.5 rounded-xl border bg-card p-2 shadow-xs group-data-[collapsible=icon]:border-0 group-data-[collapsible=icon]:bg-transparent group-data-[collapsible=icon]:p-0 group-data-[collapsible=icon]:shadow-none">
      <Avatar className="size-8 shrink-0">
        <AvatarFallback className="bg-brand-gradient text-xs font-semibold text-white">{initials(user.display_name)}</AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
        <p className="truncate text-[13px] leading-tight font-semibold">{user.display_name}</p>
        <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span
            className={
              user.role === "admin"
                ? "rounded-full bg-brand-soft px-1.5 py-px font-medium text-brand-strong capitalize"
                : "rounded-full bg-muted px-1.5 py-px font-medium capitalize"
            }
          >
            {user.role}
          </span>
          <span className="truncate">@{user.username}</span>
        </p>
      </div>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon-sm"
            className="shrink-0 text-muted-foreground group-data-[collapsible=icon]:hidden"
            aria-label="Sign out"
            onClick={() => void signOut()}
          >
            <LogOut />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="top">Sign out</TooltipContent>
      </Tooltip>
    </div>
  );
}

export function AppSidebar() {
  const { user } = useUser();
  // Recruiters never see admin pages; hidden until the user loads so it never flashes in.
  const showAdmin = user?.role === "admin";
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="h-16 justify-center px-3 group-data-[collapsible=icon]:px-2">
        <Link
          href="/dashboard"
          className="flex items-center gap-2.5 rounded-lg px-1 py-1 outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring group-data-[collapsible=icon]:px-0"
          aria-label="Placewise home"
        >
          <LogoMark />
          <span className="min-w-0 leading-tight group-data-[collapsible=icon]:hidden">
            <span className="block truncate text-[15px] font-semibold tracking-[-0.015em] text-foreground">Placewise</span>
            <span className="block truncate text-[11px] text-muted-foreground">A/E/C talent intelligence</span>
          </span>
        </Link>
      </SidebarHeader>
      <SidebarContent className="gap-1 px-1.5">
        <SidebarGroup>
          <SidebarGroupLabel className="text-[11px] font-semibold tracking-[0.06em] text-muted-foreground/80 uppercase">
            Workspace
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <Nav items={MAIN_NAV} />
          </SidebarGroupContent>
        </SidebarGroup>
        {showAdmin && (
          <SidebarGroup>
            <SidebarGroupLabel className="text-[11px] font-semibold tracking-[0.06em] text-muted-foreground/80 uppercase">
              Admin
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <Nav items={ADMIN_NAV} />
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>
      <SidebarFooter className="gap-2 p-3 group-data-[collapsible=icon]:p-2">
        <p className="flex items-center gap-1.5 px-1 text-[11px] text-muted-foreground group-data-[collapsible=icon]:hidden">
          <span className="size-1.5 rounded-full bg-warning" aria-hidden="true" />
          Demo · seeded with synthetic data
        </p>
        <UserCard />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
