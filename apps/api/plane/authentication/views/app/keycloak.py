import uuid

from django.http import HttpResponseRedirect
from django.views import View

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES, AuthenticationException
from plane.authentication.provider.oauth.keycloak import KeycloakOAuthProvider
from plane.authentication.utils.host import base_host
from plane.authentication.utils.login import user_login
from plane.authentication.utils.redirection_path import get_redirection_path
from plane.authentication.utils.keycloak_auto_join import keycloak_post_auth_workflow
from plane.license.models import Instance
from plane.utils.path_validator import get_safe_redirect_url, validate_next_path


class KeycloakOauthInitiateEndpoint(View):
    def get(self, request):
        request.session["host"] = base_host(request=request, is_app=True)
        next_path = request.GET.get("next_path")
        if next_path:
            request.session["next_path"] = str(validate_next_path(next_path))

        if (instance := Instance.objects.first()) is None or not instance.is_setup_done:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["INSTANCE_NOT_CONFIGURED"],
                error_message="INSTANCE_NOT_CONFIGURED",
            )
            return HttpResponseRedirect(
                get_safe_redirect_url(
                    base_url=base_host(request=request, is_app=True), next_path=next_path, params=exc.get_error_dict()
                )
            )

        try:
            state = uuid.uuid4().hex
            provider = KeycloakOAuthProvider(request=request, state=state)
            request.session["state"] = state
            return HttpResponseRedirect(provider.get_auth_url())
        except AuthenticationException as exc:
            return HttpResponseRedirect(
                get_safe_redirect_url(
                    base_url=base_host(request=request, is_app=True),
                    next_path=next_path,
                    params=exc.get_error_dict(),
                )
            )


class KeycloakCallbackEndpoint(View):
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
                get_safe_redirect_url(
                    base_url=base_host(request=request, is_app=True), next_path=next_path, params=exc.get_error_dict()
                )
            )

        try:
            provider = KeycloakOAuthProvider(request=request, code=code, callback=keycloak_post_auth_workflow)
            user = provider.authenticate()
            user_login(request=request, user=user, is_app=True)
            path = next_path or get_redirection_path(user=user)
            return HttpResponseRedirect(
                get_safe_redirect_url(base_url=base_host(request=request, is_app=True), next_path=path, params={})
            )
        except AuthenticationException as exc:
            return HttpResponseRedirect(
                get_safe_redirect_url(
                    base_url=base_host(request=request, is_app=True),
                    next_path=next_path,
                    params=exc.get_error_dict(),
                )
            )
