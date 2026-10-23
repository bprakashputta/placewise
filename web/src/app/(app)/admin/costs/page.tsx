import type { Metadata } from "next";
import { CostsView } from "./costs-view";

export const metadata: Metadata = { title: "AI costs" };

export default function CostsPage() {
  return <CostsView />;
}
