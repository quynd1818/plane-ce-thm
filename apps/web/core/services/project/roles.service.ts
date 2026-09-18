import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";
import type { TCustomProperty } from "./customization.service";

export type TProjectCustomRole = {
  id: string;
  name: string;
  permissions: string[];
  property_keys: string[];
  is_active: boolean;
};
export type TProjectRoleAccess = { restricted: boolean; role: TProjectCustomRole | null };
export type TRoleManagement = {
  roles: TProjectCustomRole[];
  capabilities: Record<string, string>;
  members: { id: string; name: string; eligible: boolean; custom_role_id: string | null }[];
};
export type TRoleIssue = { id: string; name: string; sequence_id: number; custom_properties: Record<string, unknown> };
export type TRoleIssues = { count: number; results: TRoleIssue[]; properties: TCustomProperty[] };
const base = (slug: string, project: string) => `/api/workspaces/${slug}/projects/${project}`;
class ProjectRolesService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }
  async workspace(
    slug: string
  ): Promise<{ restricted: boolean; projects: { id: string; name: string; role: TProjectCustomRole | null }[] }> {
    return this.get(`/api/workspaces/${slug}/role-access/`).then((r) => r.data);
  }
  async me(slug: string, project: string): Promise<TProjectRoleAccess> {
    return this.get(`${base(slug, project)}/custom-role/me/`).then((r) => r.data);
  }
  async list(slug: string, project: string): Promise<TRoleManagement> {
    return this.get(`${base(slug, project)}/custom-roles/`).then((r) => r.data);
  }
  async save(slug: string, project: string, role: Omit<TProjectCustomRole, "id">, id?: string) {
    const url = `${base(slug, project)}/custom-roles/${id ? `${id}/` : ""}`;
    return (id ? this.patch(url, role) : this.post(url, role)).then((r) => r.data);
  }
  async remove(slug: string, project: string, id: string) {
    return this.delete(`${base(slug, project)}/custom-roles/${id}/`);
  }
  async assign(slug: string, project: string, membership: string, role: string | null) {
    return this.put(`${base(slug, project)}/role-assignments/${membership}/`, { custom_role_id: role });
  }
  async issues(slug: string, project: string, search: string, offset: number): Promise<TRoleIssues> {
    return this.get(`${base(slug, project)}/role-issues/`, { params: { search, offset } }).then((r) => r.data);
  }
  async updateProperties(slug: string, project: string, issue: string, changes: Record<string, unknown>) {
    return this.patch(`${base(slug, project)}/role-issues/${issue}/`, { custom_properties: changes });
  }
}
export const projectRolesService = new ProjectRolesService();

export function roleError(error: unknown): string {
  const data = (error as { response?: { data?: unknown }; data?: unknown })?.response?.data;
  if (data && typeof data === "object") {
    const message = Object.values(data)
      .map((value) => (typeof value === "string" ? value : JSON.stringify(value)))
      .join(" ");
    if (message) return message;
  }
  return "Unable to complete this request. Check your connection and permissions, then retry.";
}
