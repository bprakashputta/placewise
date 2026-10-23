"use client";

import { Suspense } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUser } from "@/components/auth/user-provider";
import { LogoMark } from "@/components/logo";
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
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";
import { ADMIN_NAV, MAIN_NAV, isActive, type NavItem } from "./nav";

function NavList({ items, pathname }: { items: NavItem[]; pathname: string }) {
  const { isMobile, setOpenMobile } = useSidebar();
  return (
    <SidebarMenu>
      {items.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <SidebarMenuItem key={item.href}>
            <SidebarMenuButton
              asChild
              isActive={active}
              tooltip={item.title}
              className="text-sidebar-foreground/80 data-active:[&_svg]:text-brand"
            >
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                onClick={() => isMobile && setOpenMobile(false)}
              >
                <item.icon aria-hidden="true" />
                <span>{item.title}</span>
              </Link>
            </SidebarMenuButton>
            {item.badge && <SidebarMenuBadge className="text-muted-foreground">{item.badge}</SidebarMenuBadge>}
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

export function AppSidebar() {
  const { user } = useUser();
  // Recruiters never see admin pages; hidden until the user loads so it never flashes in.
  const showAdmin = user?.role === "admin";
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="h-14 justify-center border-b border-sidebar-border px-2 group-data-[collapsible=icon]:px-2">
        <Link
          href="/dashboard"
          className="flex items-center gap-2.5 rounded-md px-1 py-1 outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring group-data-[collapsible=icon]:px-0"
          aria-label="Placewise home"
        >
          <LogoMark />
          <span className="truncate text-[15px] font-semibold tracking-tight group-data-[collapsible=icon]:hidden">
            Placewise
          </span>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <Nav items={MAIN_NAV} />
          </SidebarGroupContent>
        </SidebarGroup>
        {showAdmin && (
          <>
            <SidebarSeparator className="mx-0 w-full" />
            <SidebarGroup>
              <SidebarGroupLabel>Admin</SidebarGroupLabel>
              <SidebarGroupContent>
                <Nav items={ADMIN_NAV} />
              </SidebarGroupContent>
            </SidebarGroup>
          </>
        )}
      </SidebarContent>
      <SidebarFooter className="group-data-[collapsible=icon]:hidden">
        <p className="px-2 pb-1 text-xs text-muted-foreground">Synthetic demo data only</p>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
