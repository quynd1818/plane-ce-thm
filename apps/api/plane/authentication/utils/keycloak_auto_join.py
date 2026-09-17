# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""THM: put every Keycloak-authenticated user into the group workspace.

Plane's default flow expects a per-user invitation; with corporate SSO that
means an admin inviting hundreds of people by hand, and with workspace
creation disabled a new user lands on a dead end after the first login.

Configuration (God Mode -> THM SSO, or env on first boot):
    KEYCLOAK_AUTO_JOIN_WORKSPACE_SLUG  slug of the workspace to join ("" = off)
    KEYCLOAK_AUTO_JOIN_ROLE            "5" (Guest, default) or "15" (Member)
"""

import logging
import os

from plane.db.models import Workspace, WorkspaceMember
from plane.license.utils.instance_value import get_configuration_value
from plane.utils.cache import invalidate_cache_directly

from .user_auth_workflow import post_user_auth_workflow

logger = logging.getLogger("plane.authentication")

ALLOWED_ROLES = {"5", "15"}  # Guest, Member — never auto-grant Admin


def get_auto_join_settings():
    slug, role = get_configuration_value(
        [
            {
                "key": "KEYCLOAK_AUTO_JOIN_WORKSPACE_SLUG",
                "default": os.environ.get("KEYCLOAK_AUTO_JOIN_WORKSPACE_SLUG", ""),
            },
            {"key": "KEYCLOAK_AUTO_JOIN_ROLE", "default": os.environ.get("KEYCLOAK_AUTO_JOIN_ROLE", "5")},
        ]
    )
    slug = (slug or "").strip()
    role = str(role or "5").strip()
    if role not in ALLOWED_ROLES:
        role = "5"
    return slug, int(role)


def auto_join_workspace(user):
    """Add ``user`` to the configured workspace if they are not a member yet.

    Returns the WorkspaceMember that was created, or None when nothing was
    done (feature off, workspace missing, or user already a member).
    """
    slug, role = get_auto_join_settings()
    if not slug:
        return None

    workspace = Workspace.objects.filter(slug=slug).first()
    if workspace is None:
        logger.warning("keycloak auto-join: workspace with slug %r does not exist", slug)
        return None

    # all_objects: a member the admin deactivated or removed must not be
    # silently re-added on the next login.
    if WorkspaceMember.all_objects.filter(workspace=workspace, member=user).exists():
        return None

    membership = WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    invalidate_cache_directly(
        path=f"/api/workspaces/{workspace.slug}/members/",
        url_params=False,
        user=False,
        multiple=True,
    )
    logger.info("keycloak auto-join: added %s to workspace %s as role %s", user.email, slug, role)
    return membership


def keycloak_post_auth_workflow(user, is_signup, request):
    """Callback for the Keycloak provider: default workflow + auto-join."""
    post_user_auth_workflow(user, is_signup, request)
    try:
        auto_join_workspace(user)
    except Exception:  # never block a successful login on the convenience step
        logger.exception("keycloak auto-join failed for %s", user.email)
