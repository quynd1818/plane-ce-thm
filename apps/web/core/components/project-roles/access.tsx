import { createContext, useContext } from "react";
import type { TProjectCustomRole } from "@/services/project/roles.service";

export type ProjectRoleMap = Record<string, TProjectCustomRole | null>;
export const ProjectRoleContext = createContext<ProjectRoleMap>({});
export function useProjectCapability(projectId: string | undefined, capability: string): boolean {
  const roles = useContext(ProjectRoleContext);
  const role = projectId ? roles[projectId] : undefined;
  return !role || (role.is_active && role.permissions.includes(capability));
}
export function useCustomProjectRole(projectId: string | undefined) {
  return useContext(ProjectRoleContext)[projectId ?? ""];
}
