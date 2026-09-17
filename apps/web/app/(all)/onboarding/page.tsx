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

  // fetching workspaces list
  useSWR(USER_WORKSPACES_LIST, () => {
    if (user?.id) {
      fetchWorkspaces();
    }
  });

  // fetching user workspace invitations
  const { isLoading: invitationsLoader, data: invitations } = useSWR(
    `USER_WORKSPACE_INVITATIONS_LIST_${user?.id}`,
    () => {
      if (user?.id) return workspaceService.userWorkspaceInvitations();
    }
  );

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
          title="Chào mừng bạn đến với"
          accent="không gian làm việc THM."
          description="Chỉ vài bước để hoàn thiện hồ sơ và tham gia không gian làm việc của Tập đoàn Tân Hoàng Minh — nơi kế hoạch, bàn giao, pháp lý và vận hành dự án cùng ở một chỗ."
          footer="D'. Palais Louis  ·  D'. Le Roi Soleil  ·  D'. Capitale  ·  D'. El Dorado"
        />
        <div
          className="relative flex h-full min-w-0 flex-1 flex-col overflow-hidden rounded-[28px] bg-surface-1"
          style={{ boxShadow: "0 12px 40px rgba(11,30,60,0.08), inset 0 0 0 1px rgba(201,162,76,0.22)" }}
        >
          {user && !invitationsLoader ? (
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
