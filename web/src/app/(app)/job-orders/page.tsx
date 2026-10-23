import type { Metadata } from "next";
import { JobOrdersView } from "./job-orders-view";

export const metadata: Metadata = { title: "Job orders" };

export default function JobOrdersPage() {
  return <JobOrdersView />;
}
