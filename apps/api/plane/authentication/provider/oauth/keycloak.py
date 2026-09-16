# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse

import pytz

from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)
from plane.authentication.adapter.oauth import OauthAdapter
from plane.license.utils.instance_value import get_configuration_value


class KeycloakOAuthProvider(OauthAdapter):
    provider = "keycloak"
    scope = "openid email profile"

    def __init__(self, request, code=None, state=None, callback=None, is_space=False):
        KEYCLOAK_CLIENT_ID, KEYCLOAK_CLIENT_SECRET, KEYCLOAK_HOST = get_configuration_value(
            [
                {"key": "KEYCLOAK_CLIENT_ID", "default": os.environ.get("KEYCLOAK_CLIENT_ID")},
                {"key": "KEYCLOAK_CLIENT_SECRET", "default": os.environ.get("KEYCLOAK_CLIENT_SECRET")},
                {"key": "KEYCLOAK_HOST", "default": os.environ.get("KEYCLOAK_HOST")},
            ]
        )

        if not (KEYCLOAK_CLIENT_ID and KEYCLOAK_CLIENT_SECRET and KEYCLOAK_HOST):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["KEYCLOAK_NOT_CONFIGURED"],
                error_message="KEYCLOAK_NOT_CONFIGURED",
            )

        parsed_host = urlparse(KEYCLOAK_HOST)
        if parsed_host.scheme not in ("http", "https") or not parsed_host.netloc:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["KEYCLOAK_NOT_CONFIGURED"],
                error_message="KEYCLOAK_NOT_CONFIGURED",
            )

        host = KEYCLOAK_HOST.rstrip("/")
        self.token_url = f"{host}/protocol/openid-connect/token"
        self.userinfo_url = f"{host}/protocol/openid-connect/userinfo"
        callback_path = "/spaces/keycloak/callback/" if is_space else "/auth/keycloak/callback/"
        redirect_uri = f"{'https' if request.is_secure() else 'http'}://{request.get_host()}{callback_path}"
        auth_params = {
            "client_id": KEYCLOAK_CLIENT_ID,
            "scope": self.scope,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        auth_url = f"{host}/protocol/openid-connect/auth?{urlencode(auth_params)}"

        super().__init__(
            request,
            self.provider,
            KEYCLOAK_CLIENT_ID,
            self.scope,
            redirect_uri,
            auth_url,
            self.token_url,
            self.userinfo_url,
            KEYCLOAK_CLIENT_SECRET,
            code,
            callback=callback,
        )

    def set_token_data(self):
        token_response = self.get_user_token(
            data={
                "code": self.code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        super().set_token_data(
            {
                "access_token": token_response.get("access_token"),
                "refresh_token": token_response.get("refresh_token"),
                "access_token_expired_at": (
                    datetime.now(tz=pytz.utc) + timedelta(seconds=token_response["expires_in"])
                    if token_response.get("expires_in")
                    else None
                ),
                "refresh_token_expired_at": None,
                "id_token": token_response.get("id_token", ""),
            }
        )

    def set_user_data(self):
        user_info_response = self.get_user_response()
        if user_info_response.get("email_verified") is not True:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OAUTH_PROVIDER_UNVERIFIED_EMAIL"],
                error_message="OAUTH_PROVIDER_UNVERIFIED_EMAIL",
            )

        email = user_info_response.get("email")
        provider_id = user_info_response.get("sub")
        if not email or not provider_id:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["KEYCLOAK_OAUTH_PROVIDER_ERROR"],
                error_message="KEYCLOAK_OAUTH_PROVIDER_ERROR",
            )

        super().set_user_data(
            {
                "email": email,
                "user": {
                    "provider_id": provider_id,
                    "email": email,
                    "first_name": user_info_response.get("given_name"),
                    "last_name": user_info_response.get("family_name"),
                    "is_password_autoset": True,
                },
            }
        )
