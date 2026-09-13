"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { TrendAnalysisResult } from "@/lib/types/api";
import { formatDate } from "@/lib/utils/format";

export function TrendChart({ result }: { result: TrendAnalysisResult }) {
  const data = result.evidence.map((point) => ({
    label: formatDate(point.recorded_at),
    value: point.normalized_value,
  }));
  if (data.length === 0) return <p className="helper-text">No recorded values are available to chart.</p>;
  return (
    <div
      className="trend-chart"
      role="img"
      aria-label={`${result.metric_label} time-series chart using ${data.length} recorded values`}
    >
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 10, right: 18, bottom: 8, left: 2 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e4ebef" />
          <XAxis dataKey="label" tick={{ fontSize: 10 }} minTickGap={24} />
          <YAxis tick={{ fontSize: 10 }} width={48} domain={["auto", "auto"]} />
          <Tooltip formatter={(value) => [`${value} ${result.unit}`, result.metric_label]} />
          <ReferenceLine
            x={formatDate(`${result.recent_period.start}T00:00:00`)}
            stroke="#d7943e"
            strokeDasharray="4 4"
            label={{ value: "Recent", fill: "#8a622c", fontSize: 10 }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="#0f8f83"
            strokeWidth={3}
            dot={{ fill: "#0f8f83", r: 4 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
