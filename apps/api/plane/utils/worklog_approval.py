# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""THM worklog approval helpers."""

from plane.app.permissions import ROLE
from plane.db.models import Project, ProjectMember, WorkLog


def approval_enabled(project) -> bool:
    return bool(getattr(project, "is_worklog_approval_enabled", False))


def initial_status(project) -> str:
    return WorkLog.STATUS_SUBMITTED if approval_enabled(project) else WorkLog.STATUS_APPROVED


def is_worklog_approver(project, user) -> bool:
    """Project admins and users listed in Project.worklog_approver_ids."""
    if str(user.id) in [str(uid) for uid in (project.worklog_approver_ids or [])]:
        return True
    return ProjectMember.objects.filter(project=project, member=user, role=ROLE.ADMIN.value, is_active=True).exists()


def can_modify_worklog(worklog, user) -> tuple[bool, str]:
    """Author may edit while submitted/rejected; approved logs are locked for
    everyone except approvers."""
    project = worklog.project if isinstance(worklog.project, Project) else Project.objects.get(pk=worklog.project_id)
    approver = is_worklog_approver(project, user)
    if approver:
        return True, ""
    if worklog.user_id != user.id:
        return False, "Only the author or a project admin can change this worklog."
    if approval_enabled(project) and worklog.status == WorkLog.STATUS_APPROVED:
        return False, "This worklog has been approved and is locked. Ask an approver to reopen it."
    return True, ""
