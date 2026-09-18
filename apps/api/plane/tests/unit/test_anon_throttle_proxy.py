# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""THM: anonymous throttles key on the real client behind the reverse proxies."""

import pytest
from django.test import RequestFactory
from rest_framework.request import Request
from rest_framework.throttling import AnonRateThrottle


@pytest.mark.unit
def test_anon_throttle_uses_forwarded_client_ip(settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 2}
    from rest_framework.settings import api_settings

    api_settings.reload()
    try:
        throttle = AnonRateThrottle()
        # client -> THM nginx -> Caddy -> api: the api sees Caddy as REMOTE_ADDR
        # and "client, nginx" in X-Forwarded-For.
        request = Request(
            RequestFactory().get(
                "/api/instances/", REMOTE_ADDR="10.0.0.9", HTTP_X_FORWARDED_FOR="203.0.113.7, 10.0.0.5"
            )
        )
        assert throttle.get_ident(request) == "203.0.113.7"
    finally:
        api_settings.reload()
