/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IWorkspaceMemberInvitation, TOnboardingStep, TOnboardingSteps, TUserProfile } from "@plane/types";
import { EOnboardingSteps } from "@plane/types";
// hooks
import { useInstance } from "@/hooks/store/use-instance";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUser, useUserProfile } from "@/hooks/store/user";
// local components
import { LogoSpinner } from "@/components/common/logo-spinner";
import { OnboardingHeader } from "./header";
import { OnboardingStepRoot } from "./steps";

type Props = {
  invitations?: IWorkspaceMemberInvitation[];
};

export const OnboardingRoot = observer(function OnboardingRoot({ invitations = [] }: Props) {
  const [currentStep, setCurrentStep] = useState<TOnboardingStep>(EOnboardingSteps.PROFILE_SETUP);
  // store hooks
  const { data: user } = useUser();
  const { data: userProfile, updateUserProfile, finishUserOnboarding } = useUserProfile();
  const { workspaces } = useWorkspace();
  const { config: instanceConfig } = useInstance();

  const workspacesList = Object.values(workspaces ?? {});
  const isSelfManaged = instanceConfig?.is_self_managed;
  const autoFinishRef = useRef(false);
  const [isFinishing, setIsFinishing] = useState(false);
  const [finishFailed, setFinishFailed] = useState(false);

  // Calculate total steps based on whether invitations are available
  const hasInvitations = invitations.length > 0;

  // complete onboarding
  const finishOnboarding = useCallback(async () => {
    if (!user || autoFinishRef.current) return;
    autoFinishRef.current = true;
    setIsFinishing(true);
    setFinishFailed(false);
    try {
      await finishUserOnboarding();
    } catch (_error) {
      autoFinishRef.current = false;
      setIsFinishing(false);
      setFinishFailed(true);
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Failed",
        message: "Failed to finish onboarding, Please try again later.",
      });
    }
  }, [user, finishUserOnboarding]);

  // handle step change
  const stepChange = useCallback(
    async (steps: Partial<TOnboardingSteps>) => {
      if (!user) return;

      const payload: Partial<TUserProfile> = {
        onboarding_step: {
          ...userProfile.onboarding_step,
          ...steps,
        },
      };

      try {
        const updated = await updateUserProfile(payload);
        if (updated) return true;
      } catch {
        // Keep the current step available for retry.
      }
      setToast({ type: TOAST_TYPE.ERROR, title: "Failed", message: "Failed to save onboarding. Please try again." });
      return false;
    },
    [user, userProfile, updateUserProfile]
  );

  const handleStepChange = useCallback(
    async (step: EOnboardingSteps, skipInvites?: boolean) => {
      switch (step) {
        case EOnboardingSteps.PROFILE_SETUP:
          if (isSelfManaged) {
            // Skip role & use case steps for self-hosted
            if (!(await stepChange({ profile_complete: true }))) return;
            if (workspacesList.length > 0) finishOnboarding();
            else setCurrentStep(EOnboardingSteps.WORKSPACE_CREATE_OR_JOIN);
          } else {
            setCurrentStep(EOnboardingSteps.ROLE_SETUP);
          }
          break;
        case EOnboardingSteps.ROLE_SETUP:
          setCurrentStep(EOnboardingSteps.USE_CASE_SETUP);
          break;
        case EOnboardingSteps.USE_CASE_SETUP:
          if (!(await stepChange({ profile_complete: true }))) return;
          if (workspacesList.length > 0) finishOnboarding();
          else setCurrentStep(EOnboardingSteps.WORKSPACE_CREATE_OR_JOIN);
          break;
        case EOnboardingSteps.WORKSPACE_CREATE_OR_JOIN:
          if (skipInvites) finishOnboarding();
          else {
            if (!(await stepChange({ workspace_create: true }))) return;
            setCurrentStep(EOnboardingSteps.INVITE_MEMBERS);
          }
          break;
        case EOnboardingSteps.INVITE_MEMBERS:
          if (!(await stepChange({ workspace_invite: true }))) return;
          finishOnboarding();
          break;
      }
    },
    [stepChange, finishOnboarding, workspacesList, isSelfManaged]
  );

  const updateCurrentStep = (step: EOnboardingSteps) => setCurrentStep(step);

  // THM: users added to a workspace server-side (Keycloak auto-join) have nothing
  // to create or join here. Skip the workspace step instead of showing the
  // "ask an admin to invite you" dead end.
  useEffect(() => {
    if (autoFinishRef.current || finishFailed) return;
    if (currentStep !== EOnboardingSteps.WORKSPACE_CREATE_OR_JOIN) return;
    if (workspacesList.length === 0) return;
    void finishOnboarding();
  }, [currentStep, workspacesList.length, finishOnboarding, finishFailed]);

  useEffect(() => {
    const handleInitialStep = () => {
      if (
        userProfile?.onboarding_step?.profile_complete &&
        !userProfile?.onboarding_step?.workspace_create &&
        !userProfile?.onboarding_step?.workspace_join
      ) {
        setCurrentStep(EOnboardingSteps.WORKSPACE_CREATE_OR_JOIN);
      }
      if (
        userProfile?.onboarding_step?.profile_complete &&
        userProfile?.onboarding_step?.workspace_create &&
        !userProfile?.onboarding_step?.workspace_invite
      ) {
        setCurrentStep(EOnboardingSteps.INVITE_MEMBERS);
      }
    };

    handleInitialStep();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (finishFailed) {
    return (
      <div role="alert" className="grid h-full place-content-center gap-4 p-8 text-center">
        <p>Không thể hoàn tất thiết lập tài khoản. Vui lòng thử lại.</p>
        <button type="button" onClick={() => void finishOnboarding()}>
          Thử lại
        </button>
      </div>
    );
  }

  if (isFinishing || (currentStep === EOnboardingSteps.WORKSPACE_CREATE_OR_JOIN && workspacesList.length > 0)) {
    return (
      <div className="grid h-full place-items-center">
        <LogoSpinner />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header with progress */}
      <OnboardingHeader
        currentStep={currentStep}
        updateCurrentStep={updateCurrentStep}
        hasInvitations={hasInvitations}
      />

      {/* Main content area */}
      <OnboardingStepRoot currentStep={currentStep} invitations={invitations} handleStepChange={handleStepChange} />
    </div>
  );
});
