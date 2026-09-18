from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import Page, Project, ProjectMember, ProjectPage, User

pytestmark = [pytest.mark.contract, pytest.mark.django_db]


@pytest.fixture
def tree(workspace, create_user):
    project = Project.objects.create(workspace=workspace, name="Pages", identifier="PG")
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20)
    parent = Page.objects.create(workspace=workspace, owned_by=create_user, name="Parent")
    child = Page.objects.create(workspace=workspace, owned_by=create_user, name="Child", parent=parent)
    for page in (parent, child):
        ProjectPage.objects.create(workspace=workspace, project=project, page=page)
    return project, parent, child


@pytest.fixture(autouse=True)
def tasks():
    with patch("plane.app.views.page.base.page_transaction"), patch("plane.app.views.page.base.recent_visited_task"):
        yield


def url(workspace, project, page=None):
    base = f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/"
    return f"{base}{page.id}/" if page else base


def test_list_and_retrieve_nested_page(session_client, workspace, tree):
    project, parent, child = tree
    response = session_client.get(url(workspace, project))
    assert response.status_code == 200
    assert {str(row["id"]) for row in response.data} == {str(parent.id), str(child.id)}
    response = session_client.get(url(workspace, project, child))
    assert response.status_code == 200, response.data
    assert response.data["parent"] == parent.id


def test_create_nested_page_and_move_to_root(session_client, workspace, tree):
    project, parent, child = tree
    response = session_client.post(
        url(workspace, project), {"name": "Grandchild", "parent": str(child.id)}, format="json"
    )
    assert response.status_code == 201, response.data
    created = Page.objects.get(pk=response.data["id"])
    assert created.parent_id == child.id
    response = session_client.patch(url(workspace, project, created), {"parent": None}, format="json")
    assert response.status_code == 200, response.data
    created.refresh_from_db()
    assert created.parent_id is None


@pytest.mark.parametrize("target", ["self", "descendant"])
def test_cycle_is_rejected(session_client, workspace, tree, target):
    project, parent, child = tree
    response = session_client.patch(
        url(workspace, project, parent), {"parent": str(parent.id if target == "self" else child.id)}, format="json"
    )
    assert response.status_code == 400
    parent.refresh_from_db()
    assert parent.parent_id is None


@pytest.mark.parametrize("operation", ["create", "move"])
@pytest.mark.parametrize("invalid", ["foreign", "private", "archived", "locked", "revoked"])
def test_invalid_parent_rejected(session_client, workspace, create_user, tree, operation, invalid):
    project, parent, child = tree
    if invalid == "foreign":
        other = Project.objects.create(workspace=workspace, name="Other", identifier="OTH")
        ProjectPage.objects.filter(page=parent).delete()
        ProjectPage.objects.create(workspace=workspace, project=other, page=parent)
    elif invalid == "private":
        parent.owned_by = User.objects.create(email="private@example.test", username="private")
        parent.access = Page.PRIVATE_ACCESS
        parent.save()
    elif invalid == "archived":
        parent.archived_at = timezone.now().date()
        parent.save()
    elif invalid == "locked":
        parent.is_locked = True
        parent.save()
    else:
        ProjectPage.objects.filter(page=parent).delete()
    payload = {"parent": str(parent.id), "name": "Invalid"}
    response = (
        session_client.post(url(workspace, project), payload, format="json")
        if operation == "create"
        else session_client.patch(url(workspace, project, child), payload, format="json")
    )
    assert response.status_code == 400, response.data
    assert not Page.objects.filter(name="Invalid").exists()


def test_guest_only_sees_owned_nested_pages(workspace, tree):
    project, parent, child = tree
    guest = User.objects.create(email="guest-pages@example.test", username="guest-pages")
    ProjectMember.objects.create(workspace=workspace, project=project, member=guest, role=5)
    project.guest_view_all_features = False
    project.save()
    child.owned_by = guest
    child.save()
    client = APIClient()
    client.force_authenticate(guest)
    response = client.get(url(workspace, project))
    assert [str(row["id"]) for row in response.data] == [str(child.id)]
    assert client.get(url(workspace, project, parent)).status_code in (403, 404)
    assert client.get(url(workspace, project, child)).status_code == 200
    assert client.patch(url(workspace, project, child), {"parent": str(parent.id)}, format="json").status_code == 400
    assert (
        client.post(url(workspace, project), {"name": "Forbidden", "parent": str(child.id)}, format="json").status_code
        == 403
    )


def test_private_child_is_not_exposed_through_public_parent(session_client, workspace, tree):
    project, parent, child = tree
    child.owned_by = User.objects.create(email="owner-private-child@example.test", username="private-child")
    child.access = Page.PRIVATE_ACCESS
    child.save()
    response = session_client.get(url(workspace, project))
    assert [str(row["id"]) for row in response.data] == [str(parent.id)]
    assert session_client.get(url(workspace, project, child)).status_code == 403


def test_archive_tree_and_delete_parent_detaches_children(session_client, workspace, tree):
    project, parent, child = tree
    assert session_client.post(url(workspace, project, parent) + "archive/").status_code == 200
    child.refresh_from_db()
    assert child.archived_at is not None
    assert session_client.delete(url(workspace, project, parent)).status_code == 204
    child.refresh_from_db()
    assert child.parent_id is None


@pytest.mark.django_db(transaction=True)
def test_concurrent_reparent_cannot_create_cycle(workspace, tree, create_user):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import close_old_connections

    project, parent, child = tree
    child.parent = None
    child.save()
    ready = Barrier(2)

    def move(pair):
        close_old_connections()
        try:
            client = APIClient()
            client.force_authenticate(create_user)
            ready.wait(timeout=10)
            source, destination = pair
            return client.patch(
                url(workspace, project, source), {"parent": str(destination.id)}, format="json"
            ).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as workers:
        statuses = list(workers.map(move, [(parent, child), (child, parent)]))
    assert sorted(statuses) == [200, 400]
    parent.refresh_from_db()
    child.refresh_from_db()
    assert not (parent.parent_id == child.id and child.parent_id == parent.id)
