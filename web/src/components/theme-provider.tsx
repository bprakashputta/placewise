"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

// React warns when a client component renders a <script>. next-themes injects one to set the
// theme class before first paint, so it is executable only in the server HTML and inert
// (text/plain) on the client. next-themes already puts suppressHydrationWarning on that tag.
const scriptProps = {
  type: typeof window === "undefined" ? "text/javascript" : "text/plain",
} as const;

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      scriptProps={scriptProps}
    >
      {children}
    </NextThemesProvider>
  );
}
