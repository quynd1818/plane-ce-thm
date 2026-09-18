/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { EUserPermissionsLevel } from "@plane/constants";
import { EUserProjectRoles } from "@plane/types";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useUser, useUserPermissions } from "@/hooks/store/user";

/**
 * THM worklog approval: who may approve in a project and whether the flow is
 * on at all. Mirrors `plane.utils.worklog_approval` on the server — project
 * admins plus the users listed in `worklog_approver_ids`.
 */
export const useWorklogApproval = (workspaceSlug: string | undefined, projectId: string | undefined) => {
  const { getProjectById } = useProject();
  const { data: currentUser } = useUser();
  const { allowPermissions } = useUserPermissions();

  const project = getProjectById(projectId);
  const isApprovalEnabled = Boolean(project?.is_worklog_approval_enabled);
  const isProjectAdmin =
    Boolean(workspaceSlug && projectId) &&
    allowPermissions([EUserProjectRoles.ADMIN], EUserPermissionsLevel.PROJECT, workspaceSlug, projectId);
  const isNamedApprover = Boolean(currentUser?.id && project?.worklog_approver_ids?.includes(currentUser.id));

  return {
    isApprovalEnabled,
    isApprover: isProjectAdmin || isNamedApprover,
    isProjectAdmin,
    currentUserId: currentUser?.id,
  };
};
