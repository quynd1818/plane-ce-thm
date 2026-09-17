/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { ChevronLeftOutline } from "@makeplane/propel/icons";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import type { TOnboardingStep } from "@plane/types";
import { EOnboardingSteps } from "@plane/types";
import { cn } from "@plane/utils";
// components
import { ThmLogo } from "@/components/thm";
// hooks
import { useInstance } from "@/hooks/store/use-instance";
import { useUser } from "@/hooks/store/user";
// local imports
import { SwitchAccountDropdown } from "./switch-account-dropdown";

type OnboardingHeaderProps = {
  currentStep: EOnboardingSteps;
  updateCurrentStep: (step: EOnboardingSteps) => void;
  hasInvitations: boolean;
};

export const OnboardingHeader = observer(function OnboardingHeader(props: OnboardingHeaderProps) {
  const { currentStep, updateCurrentStep, hasInvitations } = props;
  // store hooks
  const { data: user } = useUser();
  const { config: instanceConfig } = useInstance();
  const isSelfManaged = instanceConfig?.is_self_managed;

  // handle step back
  const handleStepBack = () => {
    switch (currentStep) {
      case EOnboardingSteps.ROLE_SETUP:
        updateCurrentStep(EOnboardingSteps.PROFILE_SETUP);
        break;
      case EOnboardingSteps.USE_CASE_SETUP:
        updateCurrentStep(EOnboardingSteps.ROLE_SETUP);
        break;
      case EOnboardingSteps.WORKSPACE_CREATE_OR_JOIN:
        updateCurrentStep(isSelfManaged ? EOnboardingSteps.PROFILE_SETUP : EOnboardingSteps.USE_CASE_SETUP);
        break;
    }
  };

  // can go back
  const canGoBack = ![EOnboardingSteps.PROFILE_SETUP, EOnboardingSteps.INVITE_MEMBERS].includes(currentStep);

  // step order for progress tracking — include INVITE_MEMBERS if user is currently on it
  const showInviteStep = !hasInvitations || currentStep === EOnboardingSteps.INVITE_MEMBERS;
  const stepOrder: TOnboardingStep[] = [
    EOnboardingSteps.PROFILE_SETUP,
    ...(isSelfManaged ? [] : [EOnboardingSteps.ROLE_SETUP, EOnboardingSteps.USE_CASE_SETUP]),
    EOnboardingSteps.WORKSPACE_CREATE_OR_JOIN,
    ...(showInviteStep ? [EOnboardingSteps.INVITE_MEMBERS] : []),
  ];

  // derived values
  const currentStepNumber = stepOrder.indexOf(currentStep) + 1;
  const totalSteps = stepOrder.length;
  const userName = user?.display_name
    ? user?.display_name
    : user?.first_name
      ? `${user?.first_name} ${user?.last_name ?? ""}`
      : user?.email;

  return (
    <div className="sticky top-0 z-10 flex flex-col gap-5">
      {/* gold progress line */}
      <div className="h-1 w-full overflow-hidden rounded-t-[28px]" style={{ background: "rgba(201,162,76,0.18)" }}>
        <Tooltip label={`${currentStepNumber}/${totalSteps}`} side="bottom" align="end">
          <div
            className="h-full transition-all duration-700 ease-out"
            style={{
              width: `${(currentStepNumber / totalSteps) * 100}%`,
              background: "linear-gradient(90deg, #C9A24C, #E3CB84)",
            }}
          />
        </Tooltip>
      </div>
      <div className={cn("flex w-full items-center justify-between gap-6 px-8", canGoBack && "pl-6")}>
        <div className="flex items-center gap-3">
          {canGoBack && (
            <button
              onClick={handleStepBack}
              className="cursor-pointer rounded-full p-1 transition-colors hover:bg-layer-1"
              type="button"
              disabled={!canGoBack}
              aria-label="Quay lại bước trước"
            >
              <ChevronLeftOutline className="size-5 text-placeholder" />
            </button>
          )}
          {/* logo only on small screens — on lg+ the brand panel carries it */}
          <ThmLogo height={36} className="lg:hidden" />
          <span
            className="text-[11px] font-bold tracking-[2px] uppercase"
            style={{ color: "#8C6B1F", fontFamily: '"Be Vietnam Pro", system-ui, sans-serif' }}
          >
            Bước {currentStepNumber} / {totalSteps}
          </span>
        </div>
        <SwitchAccountDropdown fullName={userName} />
      </div>
    </div>
  );
});
