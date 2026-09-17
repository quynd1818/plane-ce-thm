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

from plane.db.models import Account, User
from plane.license.models import Instance, InstanceConfiguration

KEYCLOAK_HOST = "https://sso.example.test/realms/thm"
UA = "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/128.0"


def _configure(enabled="1", host=KEYCLOAK_HOST, client_id="plane", secret="s3cret"):
    for key, value, encrypted in (
        ("IS_KEYCLOAK_ENABLED", enabled, False),
        ("KEYCLOAK_HOST", host, False),
        ("KEYCLOAK_CLIENT_ID", client_id, False),
        ("KEYCLOAK_CLIENT_SECRET", secret, True),
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
