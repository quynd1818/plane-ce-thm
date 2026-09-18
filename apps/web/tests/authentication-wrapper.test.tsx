import { act, StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EPageTypes } from "@/helpers/authentication.helper";
import { AuthenticationWrapper } from "@/lib/wrappers/authentication-wrapper";

const state = vi.hoisted(() => ({
  user: {
    data: { id: "user", is_password_autoset: true } as { id: string; is_password_autoset: boolean } | undefined,
    isLoading: false,
    fetchCurrentUser: vi.fn(),
  },
  profile: { data: { id: "profile" as string | undefined, is_onboarded: true } },
  settings: { data: { workspace: { last_workspace_slug: "thm", fallback_workspace_slug: "thm" } } },
  workspace: { loader: false, workspaces: { thm: { slug: "thm" } } },
  swr: { isLoading: false },
}));

vi.mock("swr", () => ({ default: () => state.swr }));
vi.mock("@/hooks/store/user", () => ({
  useUser: () => state.user,
  useUserProfile: () => state.profile,
  useUserSettings: () => state.settings,
}));
vi.mock("@/hooks/store/use-workspace", () => ({ useWorkspace: () => state.workspace }));
vi.mock("@/components/common/logo-spinner", () => ({
  LogoSpinner: () => <div role="status">Loading</div>,
}));
// Avoid importing the unrelated authentication error UI from this helper.
vi.mock("@/helpers/authentication.helper", () => ({
  EPageTypes: {
    PUBLIC: "PUBLIC",
    NON_AUTHENTICATED: "NON_AUTHENTICATED",
    AUTHENTICATED: "AUTHENTICATED",
    ONBOARDING: "ONBOARDING",
    SET_PASSWORD: "SET_PASSWORD",
  },
}));

describe("AuthenticationWrapper navigation", () => {
  let container: HTMLDivElement;
  let root: Root;
  let router: ReturnType<typeof createMemoryRouter>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    state.user.data = { id: "user", is_password_autoset: true };
    state.user.isLoading = false;
    state.profile.data = { id: "profile", is_onboarded: true };
    state.workspace.loader = false;
    state.settings.data.workspace = { last_workspace_slug: "thm", fallback_workspace_slug: "thm" };
    state.swr.isLoading = false;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    router?.dispose();
    container.remove();
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  const render = async (
    pageType = EPageTypes.NON_AUTHENTICATED,
    initialEntry = "/",
    workspaceLazy?: () => Promise<{ Component: () => React.JSX.Element }>
  ) => {
    router = createMemoryRouter(
      [
        {
          path: "/",
          element: <AuthenticationWrapper pageType={pageType}>Page content</AuthenticationWrapper>,
        },
        { path: "/thm/", ...(workspaceLazy ? { lazy: workspaceLazy } : { element: <div>Workspace</div> }) },
        { path: "/onboarding/", element: <div>Onboarding</div> },
        { path: "/thm/issues/", element: <div>Issues</div> },
      ],
      { initialEntries: [initialEntry] }
    );
    await act(async () => root.render(<RouterProvider router={router} />));
  };

  const flushNavigation = async () => {
    await act(async () => vi.runOnlyPendingTimersAsync());
  };

  it("uses an existing workspace when profile settings do not have its slug yet", async () => {
    state.settings.data.workspace = { last_workspace_slug: "", fallback_workspace_slug: "" };
    await render();
    await flushNavigation();
    expect(router.state.location.pathname).toBe("/thm/");
    expect(container.textContent).toBe("Workspace");
  });

  it("keeps a spinner visible while the destination module is loading", async () => {
    let finishLoading!: (value: { Component: () => React.JSX.Element }) => void;
    const module = new Promise<{ Component: () => React.JSX.Element }>((resolve) => {
      finishLoading = resolve;
    });
    await render(EPageTypes.NON_AUTHENTICATED, "/", () => module);
    await flushNavigation();

    expect(router.state.location.pathname).toBe("/");
    expect(router.state.navigation.state).toBe("loading");
    expect(container.querySelector('[role="status"]')?.textContent).toBe("Loading");

    // Re-rendering the guard while a transition is pending must not restart it.
    const navigate = vi.spyOn(router, "navigate");
    await act(async () => root.render(<RouterProvider router={router} />));
    await flushNavigation();
    expect(navigate).not.toHaveBeenCalled();

    await act(async () => finishLoading({ Component: () => <div>Workspace</div> }));
    expect(router.state.location.pathname).toBe("/thm/");
    expect(container.textContent).toBe("Workspace");
    expect(router.state.historyAction).toBe("REPLACE");
  });

  it("waits for a profile before redirecting an authenticated user", async () => {
    state.profile.data.id = undefined;
    await render();
    await flushNavigation();
    expect(router.state.location.pathname).toBe("/");
    expect(container.querySelector('[role="status"]')).not.toBeNull();

    state.profile.data = { id: "profile", is_onboarded: true };
    await act(async () =>
      root.render(
        <RouterProvider
          router={router}
          // Changing the key simulates remounting with the now-loaded store.
          key="profile-ready"
        />
      )
    );
    await flushNavigation();
    expect(router.state.location.pathname).toBe("/thm/");
  });

  it("waits for initial authentication instead of redirecting to sign-in", async () => {
    state.user.data = undefined;
    state.user.isLoading = true;
    await render(EPageTypes.AUTHENTICATED);
    await flushNavigation();
    expect(router.state.location.search).toBe("");
    expect(container.querySelector('[role="status"]')).not.toBeNull();
  });

  it("sends new SSO users to onboarding", async () => {
    state.profile.data.is_onboarded = false;
    await render();
    await flushNavigation();
    expect(router.state.location.pathname).toBe("/onboarding/");
    expect(container.textContent).toBe("Onboarding");
  });

  it("preserves an explicit post-login destination", async () => {
    await render(EPageTypes.NON_AUTHENTICATED, "/?next_path=%2Fthm%2Fissues%2F");
    await flushNavigation();
    expect(router.state.location.pathname).toBe("/thm/issues/");
  });

  it("renders the sign-in form for an unauthenticated visitor", async () => {
    state.user.data = undefined;
    await render();
    await flushNavigation();
    expect(container.textContent).toBe("Page content");
  });

  it.each([EPageTypes.PUBLIC, EPageTypes.AUTHENTICATED, EPageTypes.SET_PASSWORD])(
    "renders permitted content for %s",
    async (pageType) => {
      await render(pageType);
      await flushNavigation();
      expect(container.textContent).toBe("Page content");
    }
  );

  it("completes redirects under StrictMode", async () => {
    await render();
    await act(async () =>
      root.render(
        <StrictMode>
          <RouterProvider router={router} />
        </StrictMode>
      )
    );
    await flushNavigation();
    expect(router.state.location.pathname).toBe("/thm/");
    expect(container.textContent).toBe("Workspace");
  });
});
