import type { Metadata } from "next";
import { FileUp, Users } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export const metadata: Metadata = { title: "Candidates" };

const COLUMNS = ["Name", "Discipline", "Location", "Credentials", "Experience", "Quality", "Updated"];

export default function CandidatesPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Candidates"
        description="Every ingested resume as a structured, searchable profile."
        actions={
          <Button disabled>
            <FileUp aria-hidden="true" /> Ingest resumes
          </Button>
        }
      />
      <Card className="gap-0 overflow-hidden py-0">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow className="hover:bg-transparent">
              {COLUMNS.map((c) => (
                <TableHead key={c} className="h-10 px-4 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  {c}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={COLUMNS.length} className="p-0 whitespace-normal">
                <EmptyState
                  icon={Users}
                  title="No candidates yet"
                  description="Candidates appear here once resumes are ingested."
                />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
