/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TThmInitiative, TThmInitiativeAnalytics, TThmInitiativeDetail, TThmInitiativeInput } from "@plane/types";
import { APIService } from "@/services/api.service";

/** THM initiatives: workspace-level containers for projects and epics. */
export class ThmInitiativeService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(workspaceSlug: string) {
    return `/api/workspaces/${workspaceSlug}/initiatives/`;
  }

  async list(workspaceSlug: string, withAnalytics = true): Promise<TThmInitiative[]> {
    return this.get(this.base(workspaceSlug), { params: withAnalytics ? { analytics: "true" } : undefined }).then(
      (response) => response.data
    );
  }

  async retrieve(workspaceSlug: string, initiativeId: string): Promise<TThmInitiativeDetail> {
    return this.get(`${this.base(workspaceSlug)}${initiativeId}/`).then((response) => response.data);
  }

  async create(workspaceSlug: string, data: TThmInitiativeInput): Promise<TThmInitiative> {
    return this.post(this.base(workspaceSlug), data).then((response) => response.data);
  }

  async update(workspaceSlug: string, initiativeId: string, data: TThmInitiativeInput): Promise<TThmInitiative> {
    return this.patch(`${this.base(workspaceSlug)}${initiativeId}/`, data).then((response) => response.data);
  }

  async remove(workspaceSlug: string, initiativeId: string): Promise<void> {
    await this.delete(`${this.base(workspaceSlug)}${initiativeId}/`);
  }

  async analytics(workspaceSlug: string, initiativeId: string): Promise<TThmInitiativeAnalytics> {
    return this.get(`${this.base(workspaceSlug)}${initiativeId}/analytics/`).then((response) => response.data);
  }

  async addProjects(workspaceSlug: string, initiativeId: string, projectIds: string[]): Promise<TThmInitiative> {
    return this.post(`${this.base(workspaceSlug)}${initiativeId}/projects/`, { project_ids: projectIds }).then(
      (response) => response.data
    );
  }

  async removeProjects(workspaceSlug: string, initiativeId: string, projectIds: string[]): Promise<TThmInitiative> {
    return this.delete(`${this.base(workspaceSlug)}${initiativeId}/projects/`, { project_ids: projectIds }).then(
      (response) => response.data
    );
  }

  async addEpics(workspaceSlug: string, initiativeId: string, epicIds: string[]): Promise<TThmInitiative> {
    return this.post(`${this.base(workspaceSlug)}${initiativeId}/epics/`, { epic_ids: epicIds }).then(
      (response) => response.data
    );
  }

  async removeEpics(workspaceSlug: string, initiativeId: string, epicIds: string[]): Promise<TThmInitiative> {
    return this.delete(`${this.base(workspaceSlug)}${initiativeId}/epics/`, { epic_ids: epicIds }).then(
      (response) => response.data
    );
  }
}

export const thmInitiativeService = new ThmInitiativeService();
