/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";

// components
import { LogoSpinner } from "@/components/common/logo-spinner";
import { OnboardingRoot } from "@/components/onboarding";
import { ThmBrandPanel } from "@/components/thm";
// constants
import { USER_WORKSPACES_LIST } from "@plane/constants";
// helpers
import { EPageTypes } from "@/helpers/authentication.helper";
// hooks
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUser } from "@/hooks/store/user";
// wrappers
import { AuthenticationWrapper } from "@/lib/wrappers/authentication-wrapper";
// services
import { WorkspaceService } from "@/services/workspace.service";

const workspaceService = new WorkspaceService();

function OnboardingPage() {
  // store hooks
  const { data: user } = useUser();
  const { fetchWorkspaces } = useWorkspace();

  // Wait for authenticated, user-scoped requests before interpreting an empty list.
  const {
    data: workspaces,
    error: workspacesError,
    mutate: retryWorkspaces,
  } = useSWR(user?.id ? [USER_WORKSPACES_LIST, user.id] : null, () => fetchWorkspaces());

  const {
    data: invitations,
    error: invitationsError,
    mutate: retryInvitations,
  } = useSWR(user?.id ? ["USER_WORKSPACE_INVITATIONS_LIST", user.id] : null, () =>
    workspaceService.userWorkspaceInvitations()
  );
  const hasLoadError = workspacesError || invitationsError;

  return (
    <AuthenticationWrapper pageType={EPageTypes.ONBOARDING}>
      {/* THM: two-column layout matching the login screen — navy brand panel + ivory content card */}
      <div
        className="relative flex size-full gap-[22px] overflow-hidden p-[22px]"
        style={{
          background:
            "radial-gradient(900px 600px at 100% 100%, rgba(201,162,76,0.10), transparent 60%), var(--bg-canvas, #5E0C19)",
        }}
      >
        <ThmBrandPanel
          title="Không gian làm việc"
          accent="của những người chế tác."
          description="Hệ thống quản lý công việc và tri thức nội bộ của Tập đoàn Tân Hoàng Minh — một nơi cho kế hoạch, bàn giao, pháp lý và vận hành dự án."
          footer="D'. Palais Louis  ·  D'. Le Roi Soleil  ·  D'. Capitale  ·  D'. El Dorado"
        />
        <div
          className="relative flex h-full min-w-0 flex-1 flex-col overflow-hidden rounded-[28px] bg-surface-1"
          style={{ boxShadow: "0 12px 40px rgba(11,30,60,0.08), inset 0 0 0 1px rgba(201,162,76,0.22)" }}
        >
          {hasLoadError ? (
            <div role="alert" className="grid h-full place-content-center gap-4 p-8 text-center">
              <p>Không thể tải workspace và lời mời. Vui lòng thử lại.</p>
              <button
                type="button"
                onClick={() => {
                  void retryWorkspaces();
                  void retryInvitations();
                }}
              >
                Thử lại
              </button>
            </div>
          ) : user && workspaces !== undefined && invitations !== undefined ? (
            <OnboardingRoot invitations={invitations ?? []} />
          ) : (
            <div className="grid h-full w-full place-items-center">
              <LogoSpinner />
            </div>
          )}
        </div>
      </div>
    </AuthenticationWrapper>
  );
}

export default observer(OnboardingPage);
