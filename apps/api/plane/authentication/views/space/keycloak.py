import uuid
from urllib.parse import urlencode

from django.http import HttpResponseRedirect
from django.views import View

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES, AuthenticationException
from plane.authentication.provider.oauth.keycloak import KeycloakOAuthProvider
from plane.authentication.utils.host import base_host
from plane.authentication.utils.login import user_login
from plane.license.models import Instance
from plane.utils.path_validator import validate_next_path


class KeycloakOauthInitiateSpaceEndpoint(View):
    def get(self, request):
        request.session["host"] = base_host(request=request, is_space=True)
        next_path = request.GET.get("next_path")
        if next_path:
            request.session["next_path"] = str(validate_next_path(next_path))

        if (instance := Instance.objects.first()) is None or not instance.is_setup_done:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["INSTANCE_NOT_CONFIGURED"],
                error_message="INSTANCE_NOT_CONFIGURED",
            )
            return HttpResponseRedirect(
                f"{base_host(request=request, is_space=True)}?{urlencode(exc.get_error_dict())}"
            )

        try:
            state = uuid.uuid4().hex
            provider = KeycloakOAuthProvider(request=request, state=state, is_space=True)
            request.session["state"] = state
            return HttpResponseRedirect(provider.get_auth_url())
        except AuthenticationException as exc:
            return HttpResponseRedirect(
                f"{base_host(request=request, is_space=True)}?{urlencode(exc.get_error_dict())}"
            )


class KeycloakCallbackSpaceEndpoint(View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        next_path = request.session.get("next_path")
        error = "KEYCLOAK_OAUTH_PROVIDER_ERROR"

        if state != request.session.get("state", "") or not code:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES[error],
                error_message=error,
            )
            return HttpResponseRedirect(
                f"{base_host(request=request, is_space=True)}?{urlencode(exc.get_error_dict())}"
            )

        try:
            provider = KeycloakOAuthProvider(request=request, code=code, is_space=True)
            user = provider.authenticate()
            user_login(request=request, user=user, is_space=True)
            path = str(validate_next_path(next_path)) if next_path else ""
            return HttpResponseRedirect(f"{base_host(request=request, is_space=True)}{path}")
        except AuthenticationException as exc:
            return HttpResponseRedirect(
                f"{base_host(request=request, is_space=True)}?{urlencode(exc.get_error_dict())}"
            )
