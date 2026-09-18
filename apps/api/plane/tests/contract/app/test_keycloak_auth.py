# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end contract tests for the THM Keycloak (OIDC) login flow.

The Keycloak token / userinfo endpoints are mocked at the HTTP layer so the
whole Django side (initiate -> state -> callback -> account linking -> session)
runs for real.
"""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone
from django.urls import reverse

from plane.db.models import Account, Profile, ProjectMember, User, Workspace, WorkspaceMember, WorkspaceMemberInvite
from plane.license.models import Instance, InstanceConfiguration

KEYCLOAK_HOST = "https://sso.example.test/realms/thm"
UA = "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/128.0"


def _configure(
    enabled="1",
    host=KEYCLOAK_HOST,
    client_id="plane",
    secret="s3cret",
    require_verified="1",
    auto_join_slug="",
    auto_join_role="5",
):
    for key, value, encrypted in (
        ("IS_KEYCLOAK_ENABLED", enabled, False),
        ("KEYCLOAK_HOST", host, False),
        ("KEYCLOAK_CLIENT_ID", client_id, False),
        ("KEYCLOAK_CLIENT_SECRET", secret, True),
        ("KEYCLOAK_REQUIRE_VERIFIED_EMAIL", require_verified, False),
        ("KEYCLOAK_AUTO_JOIN_WORKSPACE_SLUG", auto_join_slug, False),
        ("KEYCLOAK_AUTO_JOIN_ROLE", auto_join_role, False),
    ):
        obj, _ = InstanceConfiguration.objects.get_or_create(key=key)
        obj.category = "KEYCLOAK"
        obj.is_encrypted = encrypted
        if encrypted:
            from plane.license.utils.encryption import encrypt_data

            obj.value = encrypt_data(value)
        else:
            obj.value = value
        obj.save()


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


@pytest.fixture
def instance(db):
    Instance.objects.all().delete()
    return Instance.objects.create(
        instance_name="thm",
        instance_id="thm-test",
        current_version="test",
        is_setup_done=True,
        last_checked_at=timezone.now(),
    )


@pytest.mark.contract
@pytest.mark.django_db
class TestKeycloakLogin:
    def test_instance_endpoint_advertises_keycloak(self, instance):
        cache.clear()  # /api/instances/ is cached for 2h
        _configure(enabled="1")
        response = Client().get("/api/instances/")
        assert response.status_code == 200
        assert response.json()["config"]["is_keycloak_enabled"] is True

        cache.clear()
        _configure(enabled="0")
        response = Client().get("/api/instances/")
        assert response.json()["config"]["is_keycloak_enabled"] is False

    def test_initiate_redirects_to_realm_with_state(self, instance):
        _configure()
        client = Client(HTTP_USER_AGENT=UA)
        response = client.get(reverse("keycloak-initiate"), HTTP_HOST="qtda.example.test")
        assert response.status_code == 302
        target = urlparse(response["Location"])
        qs = parse_qs(target.query)
        assert f"{target.scheme}://{target.netloc}{target.path}" == f"{KEYCLOAK_HOST}/protocol/openid-connect/auth"
        assert qs["client_id"] == ["plane"]
        assert qs["response_type"] == ["code"]
        assert qs["scope"] == ["openid email profile"]
        assert qs["redirect_uri"] == ["http://qtda.example.test/auth/keycloak/callback/"]
        assert qs["state"] == [client.session["state"]]

    def test_space_initiate_uses_auth_prefixed_callback(self, instance):
        _configure()
        response = Client().get(reverse("space-keycloak-initiate"), HTTP_HOST="qtda.example.test")
        assert response.status_code == 302
        qs = parse_qs(urlparse(response["Location"]).query)
        assert qs["redirect_uri"] == ["http://qtda.example.test/auth/spaces/keycloak/callback/"]

    def test_initiate_fails_cleanly_when_not_configured(self, instance):
        _configure(host="", client_id="", secret="")
        response = Client().get(reverse("keycloak-initiate"), HTTP_HOST="qtda.example.test")
        assert response.status_code == 302
        assert "error_code=5113" in response["Location"]  # KEYCLOAK_NOT_CONFIGURED

    def test_callback_creates_user_links_account_and_logs_in(self, instance):
        _configure()
        client = Client(HTTP_USER_AGENT=UA)
        client.get(reverse("keycloak-initiate"), HTTP_HOST="qtda.example.test")
        state = client.session["state"]

        userinfo = {
            "sub": "kc-sub-123",
            "email": "quynd@tanhoangminh.com.vn",
            "email_verified": True,
            "preferred_username": "quynd",
            "given_name": "Duc",
            "family_name": "Quy",
        }
        posted = {}

        def fake_post(url, data=None, headers=None, **kwargs):
            posted["url"] = url
            posted["data"] = data
            return _Resp({"access_token": "at", "refresh_token": "rt", "expires_in": 300, "id_token": "idt"})

        def fake_get(url, headers=None, **kwargs):
            assert url == f"{KEYCLOAK_HOST}/protocol/openid-connect/userinfo"
            assert headers["Authorization"] == "Bearer at"
            return _Resp(userinfo)

        with patch("plane.authentication.adapter.oauth.requests.post", side_effect=fake_post), patch(
            "plane.authentication.adapter.oauth.requests.get", side_effect=fake_get
        ):
            response = client.get(
                reverse("keycloak-callback"), {"code": "abc", "state": state}, HTTP_HOST="qtda.example.test"
            )

        assert response.status_code == 302, response["Location"]
        assert "error_code" not in response["Location"]
        assert posted["url"] == f"{KEYCLOAK_HOST}/protocol/openid-connect/token"
        assert posted["data"]["grant_type"] == "authorization_code"
        assert posted["data"]["redirect_uri"] == "http://qtda.example.test/auth/keycloak/callback/"

        user = User.objects.get(email="quynd@tanhoangminh.com.vn")
        assert user.first_name == "Duc" and user.last_name == "Quy"
        assert user.is_password_autoset is True
        account = Account.objects.get(user=user, provider="keycloak")
        assert account.provider_account_id == "kc-sub-123"
        assert client.session.get("_auth_user_id") == str(user.id)
        assert parse_qs(urlparse(response["Location"]).query)["next_path"] == ["/onboarding"]

    def test_callback_rejects_bad_state(self, instance):
        _configure()
        client = Client(HTTP_USER_AGENT=UA)
        client.get(reverse("keycloak-initiate"), HTTP_HOST="qtda.example.test")
        response = client.get(
            reverse("keycloak-callback"), {"code": "abc", "state": "wrong"}, HTTP_HOST="qtda.example.test"
        )
        assert response.status_code == 302
        assert "error_code=5126" in response["Location"]  # KEYCLOAK_OAUTH_PROVIDER_ERROR
        assert "_auth_user_id" not in client.session

    def test_callback_rejects_unverified_email(self, instance):
        _configure()
        client = Client(HTTP_USER_AGENT=UA)
        client.get(reverse("keycloak-initiate"), HTTP_HOST="qtda.example.test")
        state = client.session["state"]
        with patch(
            "plane.authentication.adapter.oauth.requests.post",
            return_value=_Resp({"access_token": "at", "expires_in": 300}),
        ), patch(
            "plane.authentication.adapter.oauth.requests.get",
            return_value=_Resp({"sub": "x", "email": "u@thm.vn", "email_verified": False}),
        ):
            response = client.get(
                reverse("keycloak-callback"), {"code": "abc", "state": state}, HTTP_HOST="qtda.example.test"
            )
        assert "error_code=5124" in response["Location"]  # OAUTH_PROVIDER_UNVERIFIED_EMAIL
        assert not User.objects.filter(email="u@thm.vn").exists()

    def test_unverified_email_accepted_when_check_disabled(self, instance):
        _configure(require_verified="0")
        client = Client(HTTP_USER_AGENT=UA)
        client.get(reverse("keycloak-initiate"), HTTP_HOST="qtda.example.test")
        state = client.session["state"]
        with patch(
            "plane.authentication.adapter.oauth.requests.post",
            return_value=_Resp({"access_token": "at", "expires_in": 300}),
        ), patch(
            "plane.authentication.adapter.oauth.requests.get",
            return_value=_Resp({"sub": "ldap-1", "email": "ldap@thm.vn", "email_verified": False}),
        ):
            response = client.get(
                reverse("keycloak-callback"), {"code": "abc", "state": state}, HTTP_HOST="qtda.example.test"
            )
        assert "error_code" not in response["Location"]
        assert User.objects.filter(email="ldap@thm.vn").exists()

    def test_provider_failure_is_logged_with_reason(self, instance, caplog):
        import requests as _requests

        _configure()
        client = Client(HTTP_USER_AGENT=UA)
        client.get(reverse("keycloak-initiate"), HTTP_HOST="qtda.example.test")
        state = client.session["state"]

        class _Err(_Resp):
            def raise_for_status(self):
                err = _requests.HTTPError("400 Client Error")
                err.response = self
                raise err

        failing = _Err({"error": "invalid_grant", "error_description": "Incorrect redirect_uri"}, status=400)
        failing.text = '{"error":"invalid_grant","error_description":"Incorrect redirect_uri"}'
        with patch("plane.authentication.adapter.oauth.requests.post", return_value=failing), caplog.at_level(
            "WARNING", logger="plane.authentication"
        ):
            response = client.get(
                reverse("keycloak-callback"), {"code": "abc", "state": state}, HTTP_HOST="qtda.example.test"
            )
        assert "error_code=5126" in response["Location"]
        assert "Incorrect redirect_uri" in caplog.text
        assert "status=400" in caplog.text


def _login_via_keycloak(client, email, sub="kc-1", next_path=None):
    params = {"next_path": next_path} if next_path else {}
    client.get(reverse("keycloak-initiate"), params, HTTP_HOST="qtda.example.test")
    state = client.session["state"]
    with patch(
        "plane.authentication.adapter.oauth.requests.post",
        return_value=_Resp({"access_token": "at", "expires_in": 300}),
    ), patch(
        "plane.authentication.adapter.oauth.requests.get",
        return_value=_Resp({"sub": sub, "email": email, "email_verified": True, "given_name": "A", "family_name": "B"}),
    ):
        return client.get(reverse("keycloak-callback"), {"code": "abc", "state": state}, HTTP_HOST="qtda.example.test")


@pytest.mark.contract
@pytest.mark.django_db
class TestKeycloakAutoJoin:
    @pytest.fixture
    def thm_workspace(self, db, create_user):
        return Workspace.objects.create(name="Tân Hoàng Minh", slug="thm", owner=create_user)

    def test_new_user_is_added_to_configured_workspace_as_guest(self, instance, thm_workspace):
        _configure(auto_join_slug="thm", auto_join_role="5")
        response = _login_via_keycloak(Client(HTTP_USER_AGENT=UA), "staff@thm.vn")
        assert "error_code" not in response["Location"]
        member = WorkspaceMember.objects.get(workspace=thm_workspace, member__email="staff@thm.vn")
        assert member.role == 5
        assert member.is_active is True

    def test_onboarded_user_keeps_workspace_destination(self, instance, thm_workspace, create_user):
        _configure(auto_join_slug="thm")
        profile, _ = Profile.objects.get_or_create(user=create_user)
        profile.is_onboarded = True
        profile.save()

        response = _login_via_keycloak(Client(HTTP_USER_AGENT=UA), create_user.email)

        assert response.status_code == 302
        assert parse_qs(urlparse(response["Location"]).query)["next_path"] == ["/thm"]

    def test_callback_preserves_explicit_destination(self, instance, thm_workspace):
        _configure(auto_join_slug="thm")
        response = _login_via_keycloak(
            Client(HTTP_USER_AGENT=UA), "staff@thm.vn", next_path="/thm/projects/"
        )

        assert response.status_code == 302
        assert parse_qs(urlparse(response["Location"]).query)["next_path"] == ["/thm/projects/"]

    def test_role_member_and_idempotent_on_second_login(self, instance, thm_workspace):
        _configure(auto_join_slug="thm", auto_join_role="15")
        _login_via_keycloak(Client(HTTP_USER_AGENT=UA), "staff@thm.vn")
        _login_via_keycloak(Client(HTTP_USER_AGENT=UA), "staff@thm.vn")
        rows = WorkspaceMember.objects.filter(workspace=thm_workspace, member__email="staff@thm.vn")
        assert rows.count() == 1
        assert rows.first().role == 15

    def test_removed_member_is_not_re_added(self, instance, thm_workspace):
        _configure(auto_join_slug="thm")
        _login_via_keycloak(Client(HTTP_USER_AGENT=UA), "staff@thm.vn")
        WorkspaceMember.objects.get(workspace=thm_workspace, member__email="staff@thm.vn").delete()  # soft delete
        _login_via_keycloak(Client(HTTP_USER_AGENT=UA), "staff@thm.vn")
        assert not WorkspaceMember.objects.filter(workspace=thm_workspace, member__email="staff@thm.vn").exists()

    def test_admin_role_is_never_granted(self, instance, thm_workspace):
        _configure(auto_join_slug="thm", auto_join_role="20")
        _login_via_keycloak(Client(HTTP_USER_AGENT=UA), "staff@thm.vn")
        assert WorkspaceMember.objects.get(workspace=thm_workspace, member__email="staff@thm.vn").role == 5

    def test_disabled_or_unknown_slug_logs_in_without_membership(self, instance, thm_workspace):
        _configure(auto_join_slug="")
        assert "error_code" not in _login_via_keycloak(Client(HTTP_USER_AGENT=UA), "a@thm.vn")["Location"]
        assert not WorkspaceMember.objects.filter(member__email="a@thm.vn").exists()

        _configure(auto_join_slug="does-not-exist")
        assert "error_code" not in _login_via_keycloak(Client(HTTP_USER_AGENT=UA), "b@thm.vn", sub="kc-2")["Location"]
        assert not WorkspaceMember.objects.filter(member__email="b@thm.vn").exists()

    def test_existing_different_workspace_is_not_added_to_default(self, instance, thm_workspace, create_user):
        _configure(auto_join_slug="thm", auto_join_role="15")
        other = Workspace.objects.create(name="Existing", slug="existing", owner=create_user)
        membership = WorkspaceMember.objects.create(workspace=other, member=create_user, role=20)
        response = _login_via_keycloak(Client(HTTP_USER_AGENT=UA), create_user.email)
        assert "error_code" not in response["Location"]
        assert not WorkspaceMember.objects.filter(workspace=thm_workspace, member=create_user).exists()
        membership.refresh_from_db()
        assert membership.role == 20

    def test_inactive_default_membership_stays_inactive(self, instance, thm_workspace, create_user):
        _configure(auto_join_slug="thm")
        membership = WorkspaceMember.objects.create(workspace=thm_workspace, member=create_user, is_active=False)
        response = _login_via_keycloak(Client(HTTP_USER_AGENT=UA), create_user.email)
        assert "error_code" not in response["Location"]
        membership.refresh_from_db()
        assert membership.is_active is False
        assert WorkspaceMember.all_objects.filter(workspace=thm_workspace, member=create_user).count() == 1

    @pytest.mark.parametrize("accepted", [True, False])
    def test_invitations_are_processed_before_fallback(self, instance, thm_workspace, create_user, accepted):
        _configure(auto_join_slug="thm")
        other = Workspace.objects.create(name="Invited", slug="invited", owner=create_user)
        invite = WorkspaceMemberInvite.objects.create(
            workspace=other, email=create_user.email, role=15, accepted=accepted, token="invitation-token"
        )
        response = _login_via_keycloak(Client(HTTP_USER_AGENT=UA), create_user.email)
        assert "error_code" not in response["Location"]
        assert WorkspaceMember.objects.filter(workspace=thm_workspace, member=create_user).exists() is not accepted
        assert WorkspaceMember.objects.filter(workspace=other, member=create_user, role=15).exists() is accepted
        assert WorkspaceMemberInvite.objects.filter(pk=invite.pk).exists() is not accepted

    def test_auto_join_does_not_complete_profile_or_grant_project_access(self, instance, thm_workspace):
        _configure(auto_join_slug="thm", auto_join_role="15")
        response = _login_via_keycloak(Client(HTTP_USER_AGENT=UA), "new-staff@thm.vn")
        assert "error_code" not in response["Location"]
        user = User.objects.get(email="new-staff@thm.vn")
        assert Profile.objects.get(user=user).is_onboarded is False
        assert not ProjectMember.objects.filter(member=user).exists()

    def test_deleted_default_does_not_block_login(self, instance, thm_workspace):
        _configure(auto_join_slug="thm")
        Workspace.objects.filter(pk=thm_workspace.pk).update(deleted_at=timezone.now())
        response = _login_via_keycloak(Client(HTTP_USER_AGENT=UA), "staff@thm.vn")
        assert "error_code" not in response["Location"]
        assert not WorkspaceMember.objects.filter(member__email="staff@thm.vn").exists()
