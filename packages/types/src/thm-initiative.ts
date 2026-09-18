/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// THM epics + initiatives

export type TThmRollup = {
  total: number;
  backlog: number;
  unstarted: number;
  started: number;
  completed: number;
  cancelled: number;
  overdue: number;
  progress: number;
  done: number;
};

export type TThmEpic = {
  id: string;
  name: string;
  sequence_id: number;
  state_id: string | null;
  priority: string;
  start_date: string | null;
  target_date: string | null;
  project_id: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  created_by_id: string | null;
  assignee_ids: string[];
  label_ids: string[];
  rollup: TThmRollup;
};

export type TThmEpicChild = {
  id: string;
  name: string;
  sequence_id: number;
  state_id: string | null;
  priority: string;
  target_date: string | null;
  project_id: string;
  completed_at: string | null;
  assignee_ids: string[];
};

export type TThmEpicDetail = TThmEpic & { work_items: TThmEpicChild[] };

export type TThmEpicInput = {
  name: string;
  description_html?: string;
  priority?: string;
  state_id?: string | null;
  start_date?: string | null;
  target_date?: string | null;
  assignee_ids?: string[];
  label_ids?: string[];
};

export type TThmInitiativeStatus = "planned" | "in_progress" | "completed" | "cancelled";

export type TThmInitiative = {
  id: string;
  workspace: string;
  name: string;
  description_html: string;
  status: TThmInitiativeStatus;
  lead: string | null;
  lead_detail?: { id: string; display_name?: string; email?: string } | null;
  start_date: string | null;
  end_date: string | null;
  logo_props: Record<string, unknown>;
  sort_order: number;
  project_ids: string[];
  epic_ids: string[];
  created_by: string | null;
  created_at: string;
  updated_at: string;
  analytics?: TThmInitiativeAnalytics;
};

export type TThmInitiativeAnalytics = TThmRollup & { project_count: number; epic_count: number };

export type TThmInitiativeProject = {
  id: string;
  name: string;
  identifier: string;
  logo_props: Record<string, unknown>;
  archived_at: string | null;
  is_member: boolean;
};

export type TThmInitiativeDetail = TThmInitiative & {
  analytics: TThmInitiativeAnalytics;
  can_edit: boolean;
  projects: TThmInitiativeProject[];
  epics: TThmEpic[];
};

export type TThmInitiativeInput = Partial<
  Pick<TThmInitiative, "name" | "description_html" | "status" | "lead" | "start_date" | "end_date" | "logo_props">
>;
