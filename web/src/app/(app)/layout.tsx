import { AppSidebar } from "@/components/shell/app-sidebar";
import { TopBar } from "@/components/shell/top-bar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

// Portal shell: sidebar + top bar around every signed-in page.
// /login and the dev pages (/ and /seed) live outside this route group.
// TODO(Block 3 auth): redirect to /login when there is no session.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <TopBar />
        <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}
