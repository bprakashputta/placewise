"use client";

import { LogOut } from "lucide-react";
import { useUser } from "@/components/auth/user-provider";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { initials } from "@/lib/format";

export function UserMenu() {
  const { user, signOut } = useUser();
  if (!user) return <Skeleton className="size-7 rounded-full" aria-label="Loading user" />;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="rounded-full" aria-label={`Open user menu for ${user.display_name}`}>
          <Avatar className="size-8">
            <AvatarFallback className="bg-brand-gradient text-xs font-semibold text-white">
              {initials(user.display_name)}
            </AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="flex items-center justify-between gap-2 font-normal">
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-foreground">{user.display_name}</span>
            <span className="block truncate text-xs text-muted-foreground">@{user.username}</span>
          </span>
          <Badge variant={user.role === "admin" ? "default" : "secondary"} className="capitalize">
            {user.role}
          </Badge>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void signOut()}>
          <LogOut /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
