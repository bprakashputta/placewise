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
          {/* Normal pages are padded and centered. While Ask is on screen it sets html[data-ask-full] and the
              page area goes full-bleed (whole area under the top bar, whatever the chat length). */}
          <main
            id="main"
            className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-8 sm:py-8 [html[data-ask-full]_&]:max-w-none [html[data-ask-full]_&]:overflow-hidden [html[data-ask-full]_&]:p-0 sm:[html[data-ask-full]_&]:p-0"
          >
            {children}
          </main>
        </SidebarInset>
      </SidebarProvider>
    </UserProvider>
  );
}
