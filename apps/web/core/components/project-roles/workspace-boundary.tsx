import { observer } from "mobx-react";
import type { ReactNode } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUser } from "@/hooks/store/user";
import { projectRolesService } from "@/services/project/roles.service";
import { RestrictedProjectPanel } from "./restricted-panel";

/** Avoid mounting aggregate workspace queries for users with restricted roles. */
export const WorkspaceRoleBoundary = observer(function WorkspaceRoleBoundary({
  workspaceSlug,
  children,
}: {
  workspaceSlug: string;
  children: ReactNode;
}) {
  const { projectId } = useParams();
  const { workspaces } = useWorkspace();
  const { data: user, signOut } = useUser();
  const { data, error, mutate } = useSWR(
    user?.id ? ["workspace-role-access", user.id, workspaceSlug] : null,
    () => projectRolesService.workspace(workspaceSlug),
    { refreshInterval: 30000, shouldRetryOnError: false }
  );
  // Let the standard workspace wrapper handle nonmembership / missing workspaces.
  if (error?.response?.status === 403 || error?.response?.status === 404) return <>{children}</>;
  if (error)
    return (
      <div role="alert" className="p-6">
        Unable to verify workspace access.{" "}
        <button type="button" onClick={() => void mutate()}>
          Retry
        </button>
      </div>
    );
  if (!data)
    return (
      <div role="status" className="p-6">
        Loading workspace access…
      </div>
    );
  if (!data.restricted) return <>{children}</>;
  const selected = data.projects.find((p) => p.id === projectId);
  const current = selected ?? data.projects.find((p) => p.role);
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
        Your custom role limits access to project tools. Only projects with an assigned custom role are available.
        Workspace-wide reports and search are unavailable.
      </p>
      {!current && (
        <p role="status" className="p-6">
          No active project membership. Ask an administrator to review your assignments.
        </p>
      )}
      {current && !current.role && (
        <p role="status" className="p-6">
          Ask an administrator to assign a custom role for this project.
        </p>
      )}
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
