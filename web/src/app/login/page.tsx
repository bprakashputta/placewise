import type { Metadata } from "next";
import { Wordmark } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <main className="relative flex flex-1 flex-col items-center justify-center bg-muted/40 px-4 py-16">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-sm space-y-6">
        <div className="flex justify-center">
          <Wordmark />
        </div>
        <LoginForm />
        <p className="text-center text-xs text-muted-foreground">
          Demo build with two roles: Admin and Recruiter. Synthetic data only.
        </p>
      </div>
    </main>
  );
}
