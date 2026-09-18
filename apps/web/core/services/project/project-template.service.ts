/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TProjectTemplate, TProjectTemplateLite } from "@plane/types";
import { APIService } from "@/services/api.service";

/** THM: workspace project templates. */
export class ProjectTemplateService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async list(workspaceSlug: string): Promise<TProjectTemplate[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/project-templates/`).then((response) => response.data);
  }

  async listLite(workspaceSlug: string): Promise<TProjectTemplateLite[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/project-templates/`, { params: { lite: "true" } }).then(
      (response) => response.data
    );
  }

  async retrieve(workspaceSlug: string, templateId: string): Promise<TProjectTemplate> {
    return this.get(`/api/workspaces/${workspaceSlug}/project-templates/${templateId}/`).then(
      (response) => response.data
    );
  }

  async create(
    workspaceSlug: string,
    data: Pick<TProjectTemplate, "name" | "description" | "template_data">
  ): Promise<TProjectTemplate> {
    return this.post(`/api/workspaces/${workspaceSlug}/project-templates/`, data).then((response) => response.data);
  }

  async update(
    workspaceSlug: string,
    templateId: string,
    data: Partial<Pick<TProjectTemplate, "name" | "description" | "template_data">>
  ): Promise<TProjectTemplate> {
    return this.patch(`/api/workspaces/${workspaceSlug}/project-templates/${templateId}/`, data).then(
      (response) => response.data
    );
  }

  async remove(workspaceSlug: string, templateId: string): Promise<void> {
    await this.delete(`/api/workspaces/${workspaceSlug}/project-templates/${templateId}/`);
  }

  /** Snapshot an existing project into a new template (project admins). */
  async saveProjectAsTemplate(
    workspaceSlug: string,
    projectId: string,
    data: { name: string; description?: string; include_work_items?: boolean }
  ): Promise<TProjectTemplate> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/save-as-template/`, data).then(
      (response) => response.data
    );
  }
}

export const projectTemplateService = new ProjectTemplateService();
