import { CircleAlert, ShieldAlert } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { ApiError } from "@/lib/api";

/** Friendly full-card state for a failed API call: 403 → "Admins only", anything else → retry. */
export function ApiErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  if (error.status === 403) {
    return (
      <Card className="py-0">
        <EmptyState
          icon={ShieldAlert}
          tone="muted"
          title="Admins only"
          description="This page is available to admin accounts. Ask an admin if you need access."
        />
      </Card>
    );
  }
  return (
    <Card className="py-0">
      <EmptyState
        icon={CircleAlert}
        tone="danger"
        title="Couldn't load this data"
        description={error.message}
        action={
          onRetry && (
            <Button variant="outline" onClick={onRetry}>
              Try again
            </Button>
          )
        }
      />
    </Card>
  );
}
