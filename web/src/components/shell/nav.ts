import {
  BriefcaseBusiness,
  CircleDollarSign,
  ClipboardCheck,
  Database,
  FlaskConical,
  LayoutDashboard,
  MessageSquareText,
  Users,
  type LucideIcon,
} from "lucide-react";

export type NavItem = { title: string; href: string; icon: LucideIcon; badge?: string };

export const MAIN_NAV: NavItem[] = [
  { title: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { title: "Candidates", href: "/candidates", icon: Users },
  { title: "Job Orders", href: "/job-orders", icon: BriefcaseBusiness },
  { title: "Ask", href: "/ask", icon: MessageSquareText },
  { title: "Approvals", href: "/approvals", icon: ClipboardCheck },
];

// "Test data" is the dev seed page; it lives outside the portal layout for now.
export const ADMIN_NAV: NavItem[] = [
  { title: "Test data", href: "/seed", icon: Database, badge: "Dev" },
  { title: "Evals", href: "/admin/evals", icon: FlaskConical },
  { title: "AI costs", href: "/admin/costs", icon: CircleDollarSign },
];

export function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** Breadcrumb trail for the top bar, e.g. ["Admin", "Evals"]. */
export function breadcrumbFor(pathname: string): string[] {
  const main = MAIN_NAV.find((i) => isActive(pathname, i.href));
  if (main) return [main.title];
  const admin = ADMIN_NAV.find((i) => isActive(pathname, i.href));
  if (admin) return ["Admin", admin.title];
  return [];
}
