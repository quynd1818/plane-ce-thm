/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// THM custom dashboards

export type TThmChartType = "number" | "bar" | "pie" | "line" | "table";
export type TThmMetric = "count" | "estimate_points" | "worklog_hours";
export type TThmGroupBy =
  | ""
  | "state"
  | "state_group"
  | "priority"
  | "assignee"
  | "label"
  | "project"
  | "module"
  | "cycle"
  | "created_by"
  | "created_month"
  | "completed_month"
  | "target_month";
export type TThmDateRange =
  | ""
  | "this_week"
  | "last_week"
  | "this_month"
  | "last_month"
  | "last_30_days"
  | "last_90_days"
  | "this_year";
export type TThmDateField = "created_at" | "target_date" | "completed_at";

export type TThmWidgetFilters = {
  project_ids?: string[];
  state_ids?: string[];
  state_groups?: string[];
  priorities?: string[];
  assignee_ids?: string[];
  created_by_ids?: string[];
  label_ids?: string[];
  module_ids?: string[];
  cycle_ids?: string[];
  created_after?: string;
  created_before?: string;
  target_after?: string;
  target_before?: string;
  completed_after?: string;
  completed_before?: string;
  date_range?: TThmDateRange;
  date_field?: TThmDateField;
  overdue_only?: boolean;
  unassigned_only?: boolean;
  include_sub_issues?: boolean;
};

export type TThmWidget = {
  id: string;
  dashboard: string;
  title: string;
  chart_type: TThmChartType;
  metric: TThmMetric;
  group_by: TThmGroupBy;
  filters: TThmWidgetFilters;
  width: 1 | 2 | 3;
  height: 1 | 2;
  sort_order: number;
  config: { limit?: number; show_legend?: boolean };
  created_at: string;
  updated_at: string;
};

export type TThmWidgetInput = Partial<
  Pick<
    TThmWidget,
    "title" | "chart_type" | "metric" | "group_by" | "filters" | "width" | "height" | "sort_order" | "config"
  >
>;

export type TThmDashboard = {
  id: string;
  workspace: string;
  name: string;
  description: string;
  owner: string | null;
  owner_detail?: { id: string; display_name?: string; email?: string } | null;
  project: string | null;
  is_shared: boolean;
  logo_props: Record<string, unknown>;
  widget_count: number;
  created_at: string;
  updated_at: string;
};

export type TThmDashboardDetail = TThmDashboard & { widgets: TThmWidget[]; can_edit: boolean };

export type TThmWidgetGroup = { key: string; label: string; color: string | null; value: number };
export type TThmWidgetData = {
  total: number;
  groups: TThmWidgetGroup[];
  metric: TThmMetric;
  group_by: TThmGroupBy;
};
