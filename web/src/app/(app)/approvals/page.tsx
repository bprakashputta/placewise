import type { Metadata } from "next";
import { ApprovalsView } from "./approvals-view";

export const metadata: Metadata = { title: "Approvals" };

export default function ApprovalsPage() {
  return <ApprovalsView />;
}
