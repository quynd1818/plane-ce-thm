import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

export type TWorkLog = {
  id: string;
  issue: string;
  user: string;
  user_detail?: { id: string; display_name?: string; email?: string };
  description: string;
  duration_seconds: number;
  started_at: string;
  ended_at: string | null;
  is_timer: boolean;
  // THM approval flow
  status: TWorkLogStatus;
  reviewed_by: string | null;
  reviewed_by_detail?: { id: string; display_name?: string; email?: string } | null;
  reviewed_at: string | null;
  review_note: string;
};

export type TWorkLogStatus = "submitted" | "approved" | "rejected";
export type TWorkLogStatusFilter = TWorkLogStatus | "all";
export type TWorkLogReviewAction = "approve" | "reject" | "reopen";

export type TWorkLogPendingItem = TWorkLog & { issue_name: string; issue_sequence_id: number };

export type TWorkLogPending = {
  results: TWorkLogPendingItem[];
  count: number;
  total_seconds: number;
};

export type TWorkLogReportParams = {
  issue_id?: string;
  user_id?: string;
  started_after?: string;
  started_before?: string;
  status?: TWorkLogStatusFilter;
};

export type TWorkLogSummary = {
  total_seconds: number;
  total_hours: number;
  group_by: "issue" | "user" | "day" | null;
  groups: Array<{ issue_id?: string; user_id?: string; day?: string; total_seconds: number }>;
};

export type TWorkLogReport = {
  results: Array<TWorkLog & { issue_name: string; user_email: string }>;
  total_seconds: number;
};

export type TWorkLogInput = {
  duration_seconds: number;
  started_at: string;
  ended_at: string;
  description?: string;
};

export class WorkLogService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async list(workspaceSlug: string, projectId: string, issueId: string): Promise<TWorkLog[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/worklogs/`).then(
      (response) => response.data
    );
  }

  async create(workspaceSlug: string, projectId: string, issueId: string, data: TWorkLogInput): Promise<TWorkLog> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/worklogs/`, data).then(
      (response) => response.data
    );
  }

  async update(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    worklogId: string,
    data: Partial<TWorkLogInput>
  ): Promise<TWorkLog> {
    return this.patch(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/worklogs/${worklogId}/`,
      data
    ).then((response) => response.data);
  }

  async startTimer(workspaceSlug: string, projectId: string, issueId: string): Promise<TWorkLog> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/timer/`).then(
      (response) => response.data
    );
  }

  async stopTimer(workspaceSlug: string, projectId: string, issueId: string): Promise<TWorkLog> {
    return this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/timer/`).then(
      (response) => response.data
    );
  }

  async deleteLog(workspaceSlug: string, projectId: string, issueId: string, worklogId: string): Promise<void> {
    await this.delete(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/worklogs/${worklogId}/`
    );
  }

  async getProjectSummary(
    workspaceSlug: string,
    projectId: string,
    groupBy?: "issue" | "user" | "day",
    status?: TWorkLogStatusFilter
  ): Promise<TWorkLogSummary> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/worklogs/summary/`, {
      params: { ...(groupBy ? { group_by: groupBy } : {}), ...(status ? { status } : {}) },
    }).then((response) => response.data);
  }

  async getProjectReport(
    workspaceSlug: string,
    projectId: string,
    params: TWorkLogReportParams = {}
  ): Promise<TWorkLogReport> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/worklogs/report/`, { params }).then(
      (response) => response.data
    );
  }

  async exportProjectReport(
    workspaceSlug: string,
    projectId: string,
    params: TWorkLogReportParams = {}
  ): Promise<Blob> {
    const response = await this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/worklogs/report/`, {
      params: { ...params, format: "csv" },
      responseType: "blob",
    });
    return response.data;
  }

  /** Worklogs waiting for approval in a project (approvers only). */
  async getPending(workspaceSlug: string, projectId: string): Promise<TWorkLogPending> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/worklogs/pending/`).then(
      (response) => response.data
    );
  }

  /** Approve / reject / reopen a worklog. Reject requires a note. */
  async review(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    worklogId: string,
    data: { action: TWorkLogReviewAction; note?: string }
  ): Promise<TWorkLog> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/worklogs/${worklogId}/review/`,
      data
    ).then((response) => response.data);
  }
}

export const workLogService = new WorkLogService();
