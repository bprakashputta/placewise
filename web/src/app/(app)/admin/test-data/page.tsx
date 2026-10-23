import type { Metadata } from "next";
import { TestDataView } from "./test-data-view";

export const metadata: Metadata = { title: "Test data" };

// Dev/admin view of the synthetic dataset and the seed/ingest actions. The /api/dev/* endpoints it
// calls exist only when the API runs with APP_ENV=dev, and only for admins.
export default function TestDataPage() {
  return <TestDataView />;
}
