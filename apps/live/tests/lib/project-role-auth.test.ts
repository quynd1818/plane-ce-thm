import { beforeEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ checkAccess: vi.fn(), currentUser: vi.fn() }));
vi.mock("@/services/page/handler", () => ({ getPageService: () => ({ checkAccess: mocks.checkAccess }) }));
vi.mock("@/services/user.service", () => ({
  UserService: class {
    currentUser = mocks.currentUser;
  },
}));
vi.mock("@plane/logger", () => ({ logger: { error: vi.fn() } }));
import { onAuthenticate, beforeHandleMessage } from "@/lib/auth";
import type { HocusPocusServerContext } from "@/types";
beforeEach(() => {
  vi.clearAllMocks();
  mocks.currentUser.mockResolvedValue({ id: "user", display_name: "User" });
});
const args = () => ({
  documentName: "page",
  requestHeaders: { cookie: "session=valid" },
  requestParameters: new URLSearchParams({
    documentType: "project_page",
    projectId: "project",
    workspaceSlug: "workspace",
  }),
  context: {} as HocusPocusServerContext,
  token: JSON.stringify({ id: "user" }),
  connection: { readOnly: false, isAuthenticated: false, requiresAuthentication: true },
});
it("checks every connection, even when the document is already cached", async () => {
  mocks.checkAccess.mockRejectedValue(new Error("Forbidden"));
  await expect(onAuthenticate(args())).rejects.toThrow("Forbidden");
});
it("read-only custom roles cannot submit shared document updates", async () => {
  mocks.checkAccess.mockResolvedValue({ can_edit: false });
  const input = args();
  await onAuthenticate(input);
  expect(input.connection.readOnly).toBe(true);
  expect(mocks.checkAccess).toHaveBeenCalledWith("page");
});
it("rechecks permissions before applying subsequent client messages", async () => {
  mocks.checkAccess.mockResolvedValue({ can_edit: false });
  const input = args();
  await beforeHandleMessage(input as unknown as Parameters<typeof beforeHandleMessage>[0]);
  expect(input.connection.readOnly).toBe(true);
  mocks.checkAccess.mockRejectedValue(new Error("Revoked"));
  await expect(beforeHandleMessage(input as unknown as Parameters<typeof beforeHandleMessage>[0])).rejects.toThrow(
    "Revoked"
  );
});
