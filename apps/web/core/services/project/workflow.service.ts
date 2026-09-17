/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * THM workflow & approval: state-transition rules per project.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

/** Project role values as stored by the API: 20 admin, 15 member, 5 guest. */
export type TWorkflowRole = 20 | 15 | 5;

export type TWorkflowRule = {
  id: string;
  /** null = the rule applies whatever the current state is */
  from_state: string | null;
  to_state: string;
  allowed_roles: TWorkflowRole[];
  approver_ids: string[];
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type TWorkflowRulePayload = Partial<
  Pick<TWorkflowRule, "from_state" | "to_state" | "allowed_roles" | "approver_ids" | "description" | "is_active">
>;

export type TWorkflowAllowedStates = {
  issue_id: string;
  current_state_id: string;
  states: { state_id: string; allowed: boolean; reason: string }[];
};

export class ProjectWorkflowService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async listRules(workspaceSlug: string, projectId: string): Promise<TWorkflowRule[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/workflow-rules/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createRule(workspaceSlug: string, projectId: string, data: TWorkflowRulePayload): Promise<TWorkflowRule> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/workflow-rules/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateRule(
    workspaceSlug: string,
    projectId: string,
    ruleId: string,
    data: TWorkflowRulePayload
  ): Promise<TWorkflowRule> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/workflow-rules/${ruleId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteRule(workspaceSlug: string, projectId: string, ruleId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/workflow-rules/${ruleId}/`)
      .then(() => undefined)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async allowedStates(workspaceSlug: string, projectId: string, issueId: string): Promise<TWorkflowAllowedStates> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/workflow-allowed-states/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}

export const projectWorkflowService = new ProjectWorkflowService();
