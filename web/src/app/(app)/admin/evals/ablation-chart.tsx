"use client";

import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { RETRIEVAL_ABLATION } from "../eval-numbers";

const FILLS = ["var(--chart-5)", "var(--chart-2)", "var(--chart-1)"];

/** Retrieval ablation: recall@10 as each search layer is added. Static data, so no animation and no tooltip. */
export function AblationChart() {
  return (
    <figure className="space-y-2">
      <figcaption className="text-xs font-medium text-muted-foreground">What each layer adds (recall@10)</figcaption>
      <div
        className="h-44 w-full"
        role="img"
        aria-label={`Recall at 10 by search setup: ${RETRIEVAL_ABLATION.map((d) => `${d.step} ${d.recall}%`).join(", ")}`}
      >
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 480, height: 176 }}>
          <BarChart data={RETRIEVAL_ABLATION} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 0 }} barCategoryGap={10}>
            <CartesianGrid horizontal={false} stroke="var(--border)" />
            <XAxis type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(v: number) => `${v}%`} tickLine={false} axisLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
            <YAxis type="category" dataKey="step" width={160} tickLine={false} axisLine={false} tick={{ fill: "var(--foreground)", fontSize: 12 }} />
            <Bar dataKey="recall" radius={[0, 4, 4, 0]} isAnimationActive={false} maxBarSize={28}>
              {RETRIEVAL_ABLATION.map((d, i) => (
                <Cell key={d.step} fill={FILLS[i]} />
              ))}
              <LabelList dataKey="recall" position="right" formatter={(v) => `${v}%`} style={{ fill: "var(--foreground)", fontSize: 12, fontWeight: 600 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
