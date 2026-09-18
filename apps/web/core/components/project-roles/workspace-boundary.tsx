import { observer } from "mobx-react";
import { useLayoutEffect, type ReactNode } from "react";
import { usePathname, useParams } from "next/navigation";
import useSWR from "swr";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUser, useUserPermissions } from "@/hooks/store/user";
import { projectRolesService } from "@/services/project/roles.service";
import { ProjectRoleContext } from "./access";
import { RestrictedProjectPanel } from "./restricted-panel";

/** Apply custom roles only to the selected project; workspace queries are row-scoped by the API. */
export const WorkspaceRoleBoundary = observer(function WorkspaceRoleBoundary({
  workspaceSlug,
  children,
}: {
  workspaceSlug: string;
  children: ReactNode;
}) {
  const { projectId } = useParams();
  const pathname = usePathname();
  const { setCustomProjectRoles } = useUserPermissions();
  const { workspaces } = useWorkspace();
  const { data: user, signOut } = useUser();
  const { data, error } = useSWR(
    user?.id ? ["workspace-role-access", user.id, workspaceSlug] : null,
    () => projectRolesService.workspace(workspaceSlug),
    { refreshInterval: 30000, shouldRetryOnError: false }
  );
  useLayoutEffect(() => {
    if (data) setCustomProjectRoles(workspaceSlug, Object.fromEntries(data.projects.map((p) => [p.id, p.role])));
  }, [data, workspaceSlug, setCustomProjectRoles]);
  // Never block the workspace on this lookup: the API enforces custom roles on
  // every request anyway, so while it loads (or if it fails, or the API has no
  // such route yet) the normal workspace renders. The panel below only replaces
  // the UI once we positively know the viewer is restricted here.
  if (!data || error || !data.restricted) return <>{children}</>;
  const selected = data.projects.find((p) => p.id === projectId);
  const roles = Object.fromEntries(data.projects.map((p) => [p.id, p.role]));
  if (!selected?.role) return <ProjectRoleContext.Provider value={roles}>{children}</ProjectRoleContext.Provider>;
  const current = selected;
  const focused = selected.role.permissions.every(
    (p) => p.startsWith("worklogs.") || p === "properties.read" || p === "properties.edit"
  );
  if (!focused && selected.role.is_active) {
    const suffix = pathname.split(`${projectId}/`)[1] ?? "";
    const section = suffix.split("/")[0];
    const resource = (
      {
        issues: "issues",
        cycles: "cycles",
        modules: "modules",
        pages: "pages",
        views: "views",
        intake: "intake",
        epics: "issues",
        worklogs: "worklogs",
        members: "members",
        states: "states",
        labels: "labels",
        estimates: "estimates",
        workflow: "workflow",
        automations: "automation",
        customization: "properties",
      } as Record<string, string>
    )[section];
    const hasFeature =
      resource === "properties"
        ? ["properties", "templates", "types"].some((r) => selected.role?.permissions.includes(`${r}.read`))
        : !resource || selected.role.permissions.includes(`${resource}.read`);
    if (hasFeature) {
      return <ProjectRoleContext.Provider value={roles}>{children}</ProjectRoleContext.Provider>;
    }
    return (
      <div role="status" className="space-y-3 p-6">
        <h1 className="text-xl">Access not granted</h1>
        <p>Your role does not include this project feature.</p>
        <nav className="flex gap-3">
          {["issues", "cycles", "modules", "pages", "views", "intake"]
            .filter((r) => selected.role?.permissions.includes(`${r}.read`))
            .map((r) => (
              <a key={r} className="underline" href={`/${workspaceSlug}/projects/${projectId}/${r}/`}>
                {r}
              </a>
            ))}
          <a href={`/${workspaceSlug}/`} className="underline">
            Workspace
          </a>
        </nav>
      </div>
    );
  }
  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-4 border-b border-subtle-1 p-4">
        <span className="font-medium">Project access</span>
        <nav aria-label="Accessible projects" className="flex flex-wrap gap-3">
          {data.projects.map((project) => (
            <a
              key={project.id}
              className="text-sm underline"
              aria-current={project.id === current?.id ? "page" : undefined}
              href={`/${workspaceSlug}/projects/${project.id}/issues/`}
            >
              {project.name}
            </a>
          ))}
        </nav>
        <nav aria-label="Other workspaces" className="flex gap-3">
          {Object.values(workspaces ?? {})
            .filter((workspace) => workspace.slug !== workspaceSlug)
            .map((workspace) => (
              <a key={workspace.id} className="text-sm underline" href={`/${workspace.slug}/`}>
                {workspace.name}
              </a>
            ))}
        </nav>
        <button className="text-sm" type="button" onClick={() => void signOut()}>
          Sign out
        </button>
      </header>
      <p className="text-sm px-6 pt-4 text-tertiary">
        These permissions apply only to this project. Other projects keep their own permissions.
      </p>
      {current?.role && (
        <RestrictedProjectPanel
          key={current.id}
          workspaceSlug={workspaceSlug}
          projectId={current.id}
          role={current.role}
        />
      )}
    </div>
  );
});
