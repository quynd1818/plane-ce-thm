# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from unittest.mock import patch

import pytest
from django.utils import timezone

from plane.authentication.utils.keycloak_auto_join import auto_join_workspace, get_auto_join_settings
from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow
from plane.db.models import User, Workspace, WorkspaceMember


@pytest.mark.unit
@pytest.mark.parametrize("configured,expected", [("5", 5), ("15", 15), ("20", 5), ("bad", 5), ("", 5)])
def test_settings_never_grant_admin(configured, expected):
    with patch(
        "plane.authentication.utils.keycloak_auto_join.get_configuration_value",
        return_value=(" default ", configured),
    ):
        assert get_auto_join_settings() == ("default", expected)


@pytest.fixture
def auto_join_context(db):
    user = User.objects.create(email="default-workspace@example.test")
    default = Workspace.objects.create(name="Default", slug="default", owner=user)
    other = Workspace.objects.create(name="Other", slug="other", owner=user)
    with patch("plane.authentication.utils.keycloak_auto_join.get_auto_join_settings", return_value=("default", 5)):
        yield user, default, other


@pytest.mark.unit
@pytest.mark.django_db
@pytest.mark.parametrize("role", [5, 15, 20])
def test_existing_workspace_prevents_fallback_and_preserves_role(auto_join_context, role):
    user, default, other = auto_join_context
    member = WorkspaceMember.objects.create(workspace=other, member=user, role=role)
    assert auto_join_workspace(user) is None
    member.refresh_from_db()
    assert member.role == role
    assert not WorkspaceMember.objects.filter(workspace=default, member=user).exists()


@pytest.mark.unit
@pytest.mark.django_db
@pytest.mark.parametrize("revocation", ["inactive", "deleted"])
def test_revoked_default_membership_is_never_restored(auto_join_context, revocation):
    user, default, _ = auto_join_context
    member = WorkspaceMember.objects.create(workspace=default, member=user, is_active=revocation != "inactive")
    if revocation == "deleted":
        member.delete()
    assert auto_join_workspace(user) is None
    member.refresh_from_db()
    assert not member.is_active if revocation == "inactive" else member.deleted_at is not None
    assert WorkspaceMember.all_objects.filter(workspace=default, member=user).count() == 1


@pytest.mark.unit
@pytest.mark.django_db
@pytest.mark.parametrize("revocation", ["inactive", "deleted", "workspace_deleted"])
def test_unavailable_other_workspace_does_not_prevent_fallback(auto_join_context, revocation):
    user, default, other = auto_join_context
    member = WorkspaceMember.objects.create(workspace=other, member=user, is_active=revocation != "inactive")
    if revocation == "deleted":
        member.delete()
    elif revocation == "workspace_deleted":
        Workspace.objects.filter(pk=other.pk).update(deleted_at=timezone.now())
    result = auto_join_workspace(user)
    assert result.workspace_id == default.id
    assert result.role == 5
    assert auto_join_workspace(user) is None
    assert WorkspaceMember.objects.filter(workspace=default, member=user).count() == 1


@pytest.mark.unit
@pytest.mark.django_db
def test_deleted_default_workspace_does_not_get_recreated(auto_join_context):
    user, default, _ = auto_join_context
    Workspace.objects.filter(pk=default.pk).update(deleted_at=timezone.now())
    assert auto_join_workspace(user) is None
    assert not WorkspaceMember.objects.filter(member=user).exists()
    assert Workspace.all_objects.count() == 2


@pytest.mark.unit
@pytest.mark.django_db
def test_standard_auth_workflow_does_not_auto_join(auto_join_context):
    user, _, _ = auto_join_context
    post_user_auth_workflow(user, True, None)
    assert not WorkspaceMember.objects.filter(member=user).exists()


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
def test_concurrent_callbacks_create_only_one_membership(auto_join_context):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections

    user, default, _ = auto_join_context
    ready = Barrier(2)

    def join():
        close_old_connections()
        try:
            ready.wait(timeout=10)
            return auto_join_workspace(user)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: join(), range(2)))
    assert sum(result is not None for result in results) == 1
    assert WorkspaceMember.objects.filter(workspace=default, member=user).count() == 1
