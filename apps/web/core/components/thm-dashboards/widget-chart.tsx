/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { useTranslation } from "@plane/i18n";
import { BarChart } from "@plane/propel/charts/bar-chart";
import { LineChart } from "@plane/propel/charts/line-chart";
import { PieChart } from "@plane/propel/charts/pie-chart";
import type { TThmWidget, TThmWidgetData } from "@plane/types";
import { cn } from "@plane/utils";
import { colorFor } from "./constants";

type Props = { widget: TThmWidget; data: TThmWidgetData | undefined; className?: string };

const formatValue = (value: number, metric: TThmWidget["metric"]) =>
  metric === "worklog_hours" ? `${value.toFixed(value % 1 === 0 ? 0 : 1)}h` : String(value);

/** THM: renders one widget's data as the configured chart. */
export function ThmWidgetChart({ widget, data, className }: Props) {
  const { t } = useTranslation();
  const rows = useMemo(
    () =>
      (data?.groups ?? []).map((g, index) => ({
        key: g.key || `g${index}`,
        name: g.label,
        label: g.label,
        value: g.value,
        color: colorFor(g.color, index),
      })),
    [data]
  );

  if (!data) return <div className={cn("animate-pulse rounded bg-layer-2", className)} />;

  if (widget.chart_type === "number") {
    return (
      <div className={cn("flex h-full flex-col items-center justify-center gap-1", className)}>
        <span className="text-4xl font-semibold text-primary">{formatValue(data.total, widget.metric)}</span>
        <span className="text-caption text-tertiary">{t(`thm_dashboards.metric.${widget.metric}`)}</span>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className={cn("flex h-full items-center justify-center text-13 text-tertiary", className)}>
        {t("thm_dashboards.widget.no_data")}
      </div>
    );
  }

  if (widget.chart_type === "table") {
    const total = data.total || rows.reduce((s, r) => s + r.value, 0) || 1;
    return (
      <div className={cn("h-full overflow-auto", className)}>
        <table className="w-full text-13">
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className="border-b border-subtle last:border-b-0">
                <td className="flex items-center gap-2 py-1.5 pr-2">
                  <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: r.color }} />
                  <span className="truncate">{r.label}</span>
                </td>
                <td className="py-1.5 text-right font-medium tabular-nums">{formatValue(r.value, widget.metric)}</td>
                <td className="w-14 py-1.5 text-right text-tertiary tabular-nums">
                  {Math.round((r.value / total) * 100)}%
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td className="py-1.5 pr-2 font-medium">{t("thm_dashboards.widget.total")}</td>
              <td className="py-1.5 text-right font-medium tabular-nums">{formatValue(data.total, widget.metric)}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    );
  }

  if (widget.chart_type === "pie") {
    return (
      <PieChart
        className={cn("size-full", className)}
        dataKey="value"
        data={rows}
        cells={rows.map((r) => ({ key: r.key, fill: r.color }))}
        showTooltip
        showLabel={false}
        innerRadius="55%"
        outerRadius="85%"
        paddingAngle={2}
        cornerRadius={3}
        centerLabel={{ text: formatValue(data.total, widget.metric), fill: "currentColor", className: "text-primary" }}
        legend={
          widget.config?.show_legend === false
            ? undefined
            : { align: "right", verticalAlign: "middle", layout: "vertical" }
        }
        margin={{ top: 4, right: 4, bottom: 4, left: 4 }}
        tooltipLabel={(payload: { name?: string }) => payload?.name ?? ""}
      />
    );
  }

  if (widget.chart_type === "line") {
    return (
      <LineChart
        className={cn("size-full", className)}
        data={rows}
        lines={[
          {
            key: "value",
            label: t(`thm_dashboards.metric.${widget.metric}`),
            dashedLine: false,
            fill: "var(--color-accent-primary)",
            showDot: true,
            smoothCurves: true,
            stroke: "var(--color-accent-primary)",
          },
        ]}
        xAxis={{ key: "label" }}
        yAxis={{ key: "value", allowDecimals: widget.metric !== "count" }}
        margin={{ top: 8, right: 12, bottom: 8, left: 0 }}
        showTooltip
      />
    );
  }

  return (
    <BarChart
      className={cn("size-full", className)}
      data={rows}
      bars={[
        {
          key: "value",
          label: t(`thm_dashboards.metric.${widget.metric}`),
          fill: (payload: { color?: string }) => payload?.color ?? "var(--color-accent-primary)",
          textClassName: "text-primary",
          stackId: "value",
          showTopBorderRadius: () => true,
        },
      ]}
      xAxis={{ key: "label" }}
      yAxis={{ key: "value", allowDecimals: widget.metric !== "count" }}
      margin={{ top: 8, right: 12, bottom: 8, left: 0 }}
      showTooltip
    />
  );
}
