"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
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

export function AppSidebar() {
  const pathname = usePathname();
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
            <NavList items={MAIN_NAV} pathname={pathname} />
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarSeparator className="mx-0 w-full" />
        <SidebarGroup>
          <SidebarGroupLabel>Admin</SidebarGroupLabel>
          <SidebarGroupContent>
            <NavList items={ADMIN_NAV} pathname={pathname} />
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="group-data-[collapsible=icon]:hidden">
        <p className="px-2 pb-1 text-xs text-muted-foreground">Synthetic demo data only</p>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
