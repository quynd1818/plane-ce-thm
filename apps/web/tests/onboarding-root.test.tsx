import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { EOnboardingSteps } from "@plane/types";
import { OnboardingRoot } from "@/components/onboarding/root";

const state = vi.hoisted(() => ({
  profile: {
    data: {
      onboarding_step: {
        profile_complete: false,
        workspace_create: false,
        workspace_join: false,
        workspace_invite: false,
      },
    },
    updateUserProfile: vi.fn(),
    finishUserOnboarding: vi.fn(),
  },
  workspace: { workspaces: {} as Record<string, { id: string }> },
}));
vi.mock("@/hooks/store/user", () => ({
  useUser: () => ({ data: { id: "user" } }),
  useUserProfile: () => state.profile,
}));
vi.mock("@/hooks/store/use-workspace", () => ({ useWorkspace: () => state.workspace }));
vi.mock("@/hooks/store/use-instance", () => ({ useInstance: () => ({ config: { is_self_managed: true } }) }));
vi.mock("@plane/propel/toast", () => ({ TOAST_TYPE: { ERROR: "error" }, setToast: vi.fn() }));
vi.mock("@/components/common/logo-spinner", () => ({ LogoSpinner: () => <div role="status">Loading</div> }));
vi.mock("@/components/onboarding/header", () => ({ OnboardingHeader: () => null }));
vi.mock("@/components/onboarding/steps", () => ({
  OnboardingStepRoot: ({
    currentStep,
    handleStepChange,
  }: {
    currentStep: EOnboardingSteps;
    handleStepChange: (step: EOnboardingSteps) => void;
  }) => <button onClick={() => handleStepChange(currentStep)}>{currentStep}</button>,
}));
let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.resetAllMocks();
  state.profile.data.onboarding_step = {
    profile_complete: false,
    workspace_create: false,
    workspace_join: false,
    workspace_invite: false,
  };
  state.workspace.workspaces = {};
  state.profile.updateUserProfile.mockResolvedValue({});
  state.profile.finishUserOnboarding.mockResolvedValue(undefined);
  container = document.createElement("div");
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  vi.unstubAllGlobals();
});
const render = async () => {
  await act(async () => root.render(<OnboardingRoot />));
};

it("requires profile completion before finishing an existing member's onboarding", async () => {
  state.workspace.workspaces = { thm: { id: "thm" } };
  let resolve!: (value: object) => void;
  state.profile.updateUserProfile.mockReturnValue(
    new Promise<object>((done) => {
      resolve = done;
    })
  );
  await render();
  expect(container.textContent).toBe(EOnboardingSteps.PROFILE_SETUP);
  expect(state.profile.finishUserOnboarding).not.toHaveBeenCalled();
  await act(async () => container.querySelector("button")!.click());
  expect(state.profile.finishUserOnboarding).not.toHaveBeenCalled();
  await act(async () => resolve({}));
  expect(state.profile.finishUserOnboarding).toHaveBeenCalledTimes(1);
  expect(container.textContent).toBe("Loading");
});

it("finishes a returning member without rendering the create or join dead end", async () => {
  state.profile.data.onboarding_step.profile_complete = true;
  state.workspace.workspaces = { thm: { id: "thm" } };
  await render();
  expect(state.profile.finishUserOnboarding).toHaveBeenCalledTimes(1);
  expect(container.textContent).toBe("Loading");
});

it("keeps the workspace step for users who have no membership", async () => {
  state.profile.data.onboarding_step.profile_complete = true;
  await render();
  expect(state.profile.finishUserOnboarding).not.toHaveBeenCalled();
  expect(container.textContent).toBe(EOnboardingSteps.WORKSPACE_CREATE_OR_JOIN);
});

it("allows a failed finish to be retried instead of getting stuck", async () => {
  state.profile.data.onboarding_step.profile_complete = true;
  state.workspace.workspaces = { thm: { id: "thm" } };
  state.profile.finishUserOnboarding.mockRejectedValueOnce(new Error("offline")).mockResolvedValue(undefined);
  await render();
  expect(container.querySelector('[role="alert"]')).not.toBeNull();
  expect(state.profile.finishUserOnboarding).toHaveBeenCalledTimes(1);
  await act(async () => container.querySelector("button")!.click());
  expect(state.profile.finishUserOnboarding).toHaveBeenCalledTimes(2);
  expect(container.textContent).toBe("Loading");
});

it("does not finish onboarding when saving profile completion fails", async () => {
  state.workspace.workspaces = { thm: { id: "thm" } };
  state.profile.updateUserProfile.mockResolvedValue(undefined);
  await render();
  await act(async () => container.querySelector("button")!.click());
  expect(state.profile.finishUserOnboarding).not.toHaveBeenCalled();
  expect(container.textContent).toBe(EOnboardingSteps.PROFILE_SETUP);
});
