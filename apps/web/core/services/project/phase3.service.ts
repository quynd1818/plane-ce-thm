import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

export type TIntakeForm = {
  id: string;
  name: string;
  slug: string;
  description: string;
  fields: Array<Record<string, unknown>>;
  default_values: Record<string, unknown>;
  is_active: boolean;
  public_key: string;
  intake: string;
};

export type TRecurringIssue = {
  id: string;
  name: string;
  description_html: string;
  frequency: "daily" | "weekly" | "monthly";
  interval: number;
  next_run_at: string;
  last_run_at: string | null;
  is_active: boolean;
  priority: string;
  state: string | null;
  issue_type: string | null;
  assignee_ids: string[];
  label_ids: string[];
  custom_properties: Record<string, unknown>;
};

export class ProjectPhase3Service extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async listIntakeForms(workspaceSlug: string, projectId: string): Promise<TIntakeForm[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/intake-forms/`).then(
      (response) => response.data
    );
  }

  async createIntakeForm(workspaceSlug: string, projectId: string, data: Partial<TIntakeForm>) {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/intake-forms/`, data).then(
      (response) => response.data
    );
  }

  async updateIntakeForm(workspaceSlug: string, projectId: string, formId: string, data: Partial<TIntakeForm>) {
    return this.patch(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/intake-forms/${formId}/`,
      data
    ).then((response) => response.data);
  }

  async deleteIntakeForm(workspaceSlug: string, projectId: string, formId: string) {
    await this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/intake-forms/${formId}/`);
  }

  async listRecurringIssues(workspaceSlug: string, projectId: string): Promise<TRecurringIssue[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/recurring-issues/`).then(
      (response) => response.data
    );
  }

  async createRecurringIssue(workspaceSlug: string, projectId: string, data: Partial<TRecurringIssue>) {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/recurring-issues/`, data).then(
      (response) => response.data
    );
  }

  async updateRecurringIssue(
    workspaceSlug: string,
    projectId: string,
    recurringId: string,
    data: Partial<TRecurringIssue>
  ) {
    return this.patch(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/recurring-issues/${recurringId}/`,
      data
    ).then((response) => response.data);
  }

  async deleteRecurringIssue(workspaceSlug: string, projectId: string, recurringId: string) {
    await this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/recurring-issues/${recurringId}/`);
  }

  async getDashboardSummary(workspaceSlug: string, projectId: string) {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/dashboard-summary/`).then(
      (response) => response.data
    );
  }

  async getPublicIntakeForm(publicKey: string): Promise<TIntakeForm> {
    return this.get(`/api/public/intake-forms/${publicKey}/`).then((response) => response.data);
  }

  async submitPublicIntakeForm(publicKey: string, values: Record<string, unknown>) {
    return this.post(`/api/public/intake-forms/${publicKey}/`, values).then((response) => response.data);
  }
}

export const projectPhase3Service = new ProjectPhase3Service();
