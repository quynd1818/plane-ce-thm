/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TThmChartType, TThmDateField, TThmDateRange, TThmGroupBy, TThmMetric } from "@plane/types";

// i18n keys live under thm_dashboards.* in common.json
export const CHART_TYPES: TThmChartType[] = ["number", "bar", "pie", "line", "table"];
export const METRICS: TThmMetric[] = ["count", "estimate_points", "worklog_hours"];
export const GROUP_BYS: TThmGroupBy[] = [
  "",
  "state",
  "state_group",
  "priority",
  "assignee",
  "label",
  "project",
  "module",
  "cycle",
  "created_by",
  "created_month",
  "completed_month",
  "target_month",
];
export const DATE_RANGES: TThmDateRange[] = [
  "",
  "this_week",
  "last_week",
  "this_month",
  "last_month",
  "last_30_days",
  "last_90_days",
  "this_year",
];
export const DATE_FIELDS: TThmDateField[] = ["created_at", "target_date", "completed_at"];
export const STATE_GROUP_KEYS = ["backlog", "unstarted", "started", "completed", "cancelled"];
export const PRIORITY_KEYS = ["urgent", "high", "medium", "low", "none"];

/** Fallback palette when the server has no color for a group. */
export const PALETTE = [
  "#b91c1c",
  "#2563eb",
  "#16a34a",
  "#d97706",
  "#7c3aed",
  "#0891b2",
  "#db2777",
  "#65a30d",
  "#ea580c",
  "#475569",
  "#0d9488",
  "#9333ea",
];

export const colorFor = (color: string | null | undefined, index: number) => color || PALETTE[index % PALETTE.length];

/** Charts that need a group_by. */
export const needsGroupBy = (chart: TThmChartType) => chart === "bar" || chart === "pie" || chart === "line";
