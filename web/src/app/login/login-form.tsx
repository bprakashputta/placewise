"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function LoginForm() {
  const router = useRouter();

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    // TODO(Block 3 auth): POST username/password to the API, which verifies the hashed password and
    // sets a session cookie; show an error on failure. Until then, any input goes to the dashboard.
    router.push("/dashboard");
  }

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-lg">Sign in</CardTitle>
        <CardDescription>Use your Placewise account to continue.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input id="username" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input id="password" name="password" type="password" autoComplete="current-password" />
          </div>
          <Button type="submit" className="h-9 w-full">
            Sign in
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
