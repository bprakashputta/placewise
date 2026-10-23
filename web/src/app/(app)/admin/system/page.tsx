import type { Metadata } from "next";
import { SystemStatusView } from "./system-status-view";

export const metadata: Metadata = { title: "System status" };

// Live health of every service (API, database, LangSmith). It used to be the root page; "/" now
// sends you to the dashboard (or to login).
export default function SystemStatusPage() {
  return <SystemStatusView />;
}
