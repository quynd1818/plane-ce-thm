/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TThmEpic, TThmEpicDetail, TThmEpicInput } from "@plane/types";
import { APIService } from "@/services/api.service";

/** THM epics: work items typed as "Epic" with rolled-up child progress. */
export class ThmEpicService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(workspaceSlug: string, projectId: string) {
    return `/api/workspaces/${workspaceSlug}/projects/${projectId}/epics/`;
  }

  async list(workspaceSlug: string, projectId: string, stateGroup?: string): Promise<TThmEpic[]> {
    return this.get(this.base(workspaceSlug, projectId), {
      params: stateGroup ? { state_group: stateGroup } : undefined,
    }).then((response) => response.data);
  }

  async listWorkspace(workspaceSlug: string, projectId?: string): Promise<TThmEpic[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/epics/`, {
      params: projectId ? { project_id: projectId } : undefined,
    }).then((response) => response.data);
  }

  async retrieve(workspaceSlug: string, projectId: string, epicId: string): Promise<TThmEpicDetail> {
    return this.get(`${this.base(workspaceSlug, projectId)}${epicId}/`).then((response) => response.data);
  }

  async create(workspaceSlug: string, projectId: string, data: TThmEpicInput): Promise<TThmEpic> {
    return this.post(this.base(workspaceSlug, projectId), data).then((response) => response.data);
  }

  /** Demote the epic back to a normal work item (children are released). */
  async demote(workspaceSlug: string, projectId: string, epicId: string): Promise<void> {
    await this.delete(`${this.base(workspaceSlug, projectId)}${epicId}/`);
  }

  async convert(workspaceSlug: string, projectId: string, issueId: string): Promise<TThmEpic> {
    return this.post(`${this.base(workspaceSlug, projectId)}convert/`, { issue_id: issueId }).then(
      (response) => response.data
    );
  }

  async attach(workspaceSlug: string, projectId: string, epicId: string, issueIds: string[]): Promise<TThmEpic> {
    return this.post(`${this.base(workspaceSlug, projectId)}${epicId}/work-items/`, { issue_ids: issueIds }).then(
      (response) => response.data
    );
  }

  async detach(workspaceSlug: string, projectId: string, epicId: string, issueIds: string[]): Promise<TThmEpic> {
    return this.delete(`${this.base(workspaceSlug, projectId)}${epicId}/work-items/`, { issue_ids: issueIds }).then(
      (response) => response.data
    );
  }
}

export const thmEpicService = new ThmEpicService();
