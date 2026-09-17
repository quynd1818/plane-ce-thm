/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import type { TIssueGroupByOptions } from "@plane/types";
// hooks
import { useWorkflowRules } from "@/hooks/store/use-workflow-rules";

/**
 * THM: kanban / list drag-and-drop between state columns honours the
 * project's workflow rules. Other group-bys (priority, assignee, ...) are
 * never restricted. Outside a project context (workspace views) the server
 * still enforces the rule; we just cannot pre-check it here.
 */
export const useWorkFlowFDragNDrop = (groupBy: TIssueGroupByOptions | undefined, subGroupBy?: TIssueGroupByOptions) => {
  const { workspaceSlug, projectId } = useParams();
  const { isTransitionAllowed } = useWorkflowRules();
  const [disabledSource, setDisabledSource] = useState<string | undefined>(undefined);
  const [isDropDisabled, setIsDropDisabled] = useState(false);

  const stateAxis: "group" | "subgroup" | undefined =
    groupBy === "state" ? "group" : subGroupBy === "state" ? "subgroup" : undefined;

  const handleWorkFlowState = useCallback(
    (sourceGroupId: string, destinationGroupId: string, sourceSubGroupId?: string, destinationSubGroupId?: string) => {
      if (!stateAxis || !projectId) {
        setIsDropDisabled(false);
        setDisabledSource(undefined);
        return;
      }
      const from = stateAxis === "group" ? sourceGroupId : sourceSubGroupId;
      const to = stateAxis === "group" ? destinationGroupId : destinationSubGroupId;
      const decision = isTransitionAllowed(workspaceSlug?.toString(), projectId.toString(), from, to);
      setIsDropDisabled(!decision.allowed);
      setDisabledSource(decision.allowed ? undefined : from);
    },
    [stateAxis, projectId, workspaceSlug, isTransitionAllowed]
  );

  return {
    workflowDisabledSource: disabledSource,
    isWorkflowDropDisabled: isDropDisabled,
    // creating a work item directly in a column is not a transition; keep it open
    getIsWorkflowWorkItemCreationDisabled: (_groupId: string, _subGroupId?: string) => false,
    handleWorkFlowState,
  };
};
