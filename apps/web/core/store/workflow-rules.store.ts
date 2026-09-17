/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * THM workflow & approval — client-side mirror of WorkflowTransitionRule.
 *
 * The API is the source of truth (it rejects a forbidden transition with
 * WORKFLOW_TRANSITION_DENIED); this store only exists so the UI can grey out
 * states and kanban columns before the user tries them.
 */

import { action, computed, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
import { projectWorkflowService } from "@/services/project/workflow.service";
import type { TWorkflowRule, TWorkflowRulePayload, TWorkflowRole } from "@/services/project/workflow.service";
import type { RootStore } from "@/store/root.store";

export type TTransitionDecision = { allowed: boolean; reason?: string };

const ROLE_LABELS: Record<TWorkflowRole, string> = { 20: "Admin", 15: "Member", 5: "Guest" };

export interface IWorkflowRulesStore {
  rulesByProject: Record<string, TWorkflowRule[]>;
  fetchedProjects: Record<string, boolean>;
  fetchRules: (workspaceSlug: string, projectId: string, force?: boolean) => Promise<TWorkflowRule[]>;
  createRule: (workspaceSlug: string, projectId: string, data: TWorkflowRulePayload) => Promise<TWorkflowRule>;
  updateRule: (
    workspaceSlug: string,
    projectId: string,
    ruleId: string,
    data: TWorkflowRulePayload
  ) => Promise<TWorkflowRule>;
  deleteRule: (workspaceSlug: string, projectId: string, ruleId: string) => Promise<void>;
  getProjectRules: (projectId: string | null | undefined) => TWorkflowRule[];
  /** Rules that restrict moving INTO the given state. */
  getRulesForTargetState: (projectId: string | null | undefined, toStateId: string) => TWorkflowRule[];
  isTransitionAllowed: (
    workspaceSlug: string | undefined,
    projectId: string | null | undefined,
    fromStateId: string | null | undefined,
    toStateId: string | null | undefined
  ) => TTransitionDecision;
}

export class WorkflowRulesStore implements IWorkflowRulesStore {
  rulesByProject: Record<string, TWorkflowRule[]> = {};
  fetchedProjects: Record<string, boolean> = {};
  rootStore: RootStore;

  constructor(rootStore: RootStore) {
    makeObservable(this, {
      rulesByProject: observable,
      fetchedProjects: observable,
      fetchRules: action,
      createRule: action,
      updateRule: action,
      deleteRule: action,
      hasAnyRule: computed,
    });
    this.rootStore = rootStore;
  }

  get hasAnyRule() {
    return Object.values(this.rulesByProject).some((rules) => rules.length > 0);
  }

  fetchRules = async (workspaceSlug: string, projectId: string, force = false) => {
    if (!force && this.fetchedProjects[projectId]) return this.rulesByProject[projectId] ?? [];
    const rules = await projectWorkflowService.listRules(workspaceSlug, projectId);
    runInAction(() => {
      this.rulesByProject[projectId] = rules;
      this.fetchedProjects[projectId] = true;
    });
    return rules;
  };

  createRule = async (workspaceSlug: string, projectId: string, data: TWorkflowRulePayload) => {
    const rule = await projectWorkflowService.createRule(workspaceSlug, projectId, data);
    runInAction(() => {
      this.rulesByProject[projectId] = [...(this.rulesByProject[projectId] ?? []), rule];
    });
    return rule;
  };

  updateRule = async (workspaceSlug: string, projectId: string, ruleId: string, data: TWorkflowRulePayload) => {
    const rule = await projectWorkflowService.updateRule(workspaceSlug, projectId, ruleId, data);
    runInAction(() => {
      this.rulesByProject[projectId] = (this.rulesByProject[projectId] ?? []).map((r) => (r.id === ruleId ? rule : r));
    });
    return rule;
  };

  deleteRule = async (workspaceSlug: string, projectId: string, ruleId: string) => {
    await projectWorkflowService.deleteRule(workspaceSlug, projectId, ruleId);
    runInAction(() => {
      this.rulesByProject[projectId] = (this.rulesByProject[projectId] ?? []).filter((r) => r.id !== ruleId);
    });
  };

  getProjectRules = computedFn((projectId: string | null | undefined) =>
    projectId ? (this.rulesByProject[projectId] ?? []) : []
  );

  getRulesForTargetState = computedFn((projectId: string | null | undefined, toStateId: string) =>
    this.getProjectRules(projectId).filter((rule) => rule.is_active && rule.to_state === toStateId)
  );

  isTransitionAllowed = computedFn(
    (
      workspaceSlug: string | undefined,
      projectId: string | null | undefined,
      fromStateId: string | null | undefined,
      toStateId: string | null | undefined
    ): TTransitionDecision => {
      if (!projectId || !toStateId || fromStateId === toStateId) return { allowed: true };
      const project = this.rootStore.projectRoot.project.getProjectById(projectId);
      if (!project?.is_workflow_enabled) return { allowed: true };

      const candidates = this.getRulesForTargetState(projectId, toStateId).filter(
        (rule) => rule.from_state === null || rule.from_state === fromStateId
      );
      if (candidates.length === 0) return { allowed: true };
      const specific = candidates.filter((rule) => rule.from_state !== null);
      const effective = specific.length > 0 ? specific : candidates;

      const role = workspaceSlug
        ? this.rootStore.user.permission.getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId)
        : undefined;
      const userId = this.rootStore.user.data?.id;

      for (const rule of effective) {
        if (role !== undefined && rule.allowed_roles.includes(role as TWorkflowRole)) return { allowed: true };
        if (userId && rule.approver_ids.includes(userId)) return { allowed: true };
      }

      const rule = effective[0];
      const stateName = this.rootStore.state.getStateById(toStateId)?.name ?? "";
      const who = [
        ...rule.allowed_roles.map((r) => ROLE_LABELS[r] ?? String(r)),
        ...(rule.approver_ids.length > 0 ? ["người duyệt được chỉ định"] : []),
      ].join(", ");
      const reason = `Chỉ ${who || "không ai"} được chuyển sang "${stateName}".${rule.description ? ` ${rule.description}` : ""}`;
      return { allowed: false, reason };
    }
  );
}
