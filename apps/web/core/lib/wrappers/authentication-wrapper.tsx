/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, type ReactNode } from "react";
import { observer } from "mobx-react";
import { useSearchParams, usePathname } from "next/navigation";
import useSWR from "swr";
// components
import { LogoSpinner } from "@/components/common/logo-spinner";
// helpers
import { EPageTypes } from "@/helpers/authentication.helper";
// hooks
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUser, useUserProfile, useUserSettings } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";

type TPageType = EPageTypes;

type TAuthenticationWrapper = {
  children: ReactNode;
  pageType?: TPageType;
};

const isValidURL = (url: string): boolean => {
  const disallowedSchemes = /^(https?|ftp):\/\//i;
  return !disallowedSchemes.test(url);
};

export const AuthenticationWrapper = observer(function AuthenticationWrapper(props: TAuthenticationWrapper) {
  const pathname = usePathname();
  const router = useAppRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next_path");
  // props
  const { children, pageType = EPageTypes.AUTHENTICATED } = props;
  // hooks
  const { isLoading: isUserLoading, data: currentUser, fetchCurrentUser } = useUser();
  const { data: currentUserProfile } = useUserProfile();
  const { data: currentUserSettings } = useUserSettings();
  const { loader: workspacesLoader, workspaces } = useWorkspace();

  const { isLoading: isUserSWRLoading } = useSWR("USER_INFORMATION", async () => await fetchCurrentUser(), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });

  const isUserProfilePending = Boolean(currentUser?.id) && !currentUserProfile?.id;

  const isUserOnboard =
    currentUserProfile?.is_onboarded ||
    (currentUserProfile?.onboarding_step?.profile_complete &&
      currentUserProfile?.onboarding_step?.workspace_create &&
      currentUserProfile?.onboarding_step?.workspace_invite &&
      currentUserProfile?.onboarding_step?.workspace_join) ||
    false;

  const getWorkspaceRedirectionUrl = (): string => {
    let redirectionRoute = "/create-workspace";

    // validating the nextPath from the router query
    if (nextPath && isValidURL(nextPath.toString())) {
      redirectionRoute = nextPath.toString();
      return redirectionRoute;
    }

    // validate the last and fallback workspace_slug
    const currentWorkspaceSlug =
      currentUserSettings?.workspace?.last_workspace_slug || currentUserSettings?.workspace?.fallback_workspace_slug;

    // Settings may still reference a removed workspace or lag behind a new membership.
    const availableWorkspaces = Object.values(workspaces || {});
    const destination =
      availableWorkspaces.find((workspace) => workspace.slug === currentWorkspaceSlug) ?? availableWorkspaces[0];
    if (destination) redirectionRoute = `/${destination.slug}`;

    return redirectionRoute;
  };

  const shouldShowInitialLoader =
    isUserProfilePending || (!currentUser?.id && (isUserSWRLoading || isUserLoading || workspacesLoader));

  // Keep rendering a loader until navigation commits, not just until the user
  // profile is ready. Route modules can still be loading after authentication.
  let redirectTo: string | undefined;
  if (!shouldShowInitialLoader && pageType !== EPageTypes.PUBLIC) {
    if (!currentUser?.id) {
      if (pageType !== EPageTypes.NON_AUTHENTICATED) {
        redirectTo = pathname ? `/?${new URLSearchParams({ next_path: pathname })}` : "/";
      }
    } else if (pageType === EPageTypes.NON_AUTHENTICATED) {
      redirectTo = isUserOnboard ? getWorkspaceRedirectionUrl() : "/onboarding";
    } else if (pageType === EPageTypes.ONBOARDING && isUserOnboard) {
      redirectTo = getWorkspaceRedirectionUrl();
    } else if (pageType === EPageTypes.SET_PASSWORD && !currentUser.is_password_autoset && isUserOnboard) {
      redirectTo = getWorkspaceRedirectionUrl();
    } else if (pageType === EPageTypes.AUTHENTICATED && !isUserOnboard) {
      redirectTo = "/onboarding";
    }
  }

  useEffect(() => {
    if (redirectTo) router.replace(redirectTo);
  }, [redirectTo, router]);

  if (shouldShowInitialLoader || redirectTo) {
    return (
      <div className="relative flex h-screen w-full items-center justify-center">
        <LogoSpinner />
      </div>
    );
  }

  return <>{children}</>;
});
