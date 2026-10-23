import { UserProvider } from "@/components/auth/user-provider";
import { AppSidebar } from "@/components/shell/app-sidebar";
import { TopBar } from "@/components/shell/top-bar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

// Portal shell: sidebar + top bar around every signed-in page.
// /login and the dev pages (/ and /seed) live outside this route group.
// src/proxy.ts redirects visitors without a session cookie to /login; the API checks the session
// on every call, and any 401 sends the browser back to /login (lib/api.ts).
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <UserProvider>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <TopBar />
          <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">{children}</div>
        </SidebarInset>
      </SidebarProvider>
    </UserProvider>
  );
}
