import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

export type TCustomProperty = {
  id: string;
  name: string;
  key: string;
  property_type: "text" | "number" | "boolean" | "date" | "select" | "multi_select";
  options: string[];
  is_required: boolean;
  is_active: boolean;
};

export type TWorkItemTemplate = {
  id: string;
  name: string;
  description: string;
  defaults: Record<string, unknown>;
  is_active: boolean;
};

export type TWorkItemType = {
  id: string;
  issue_type_id: string;
  name: string;
  description: string;
  level: number;
  is_default: boolean;
};

export type TAvailableWorkItemType = {
  id: string;
  name: string;
  description: string;
};

export class ProjectCustomizationService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async listProperties(workspaceSlug: string, projectId: string): Promise<TCustomProperty[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/custom-properties/`).then(
      (response) => response.data
    );
  }

  async createProperty(workspaceSlug: string, projectId: string, data: Omit<TCustomProperty, "id">) {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/custom-properties/`, data).then(
      (response) => response.data
    );
  }

  async deleteProperty(workspaceSlug: string, projectId: string, propertyId: string) {
    await this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/custom-properties/${propertyId}/`);
  }

  async listTemplates(workspaceSlug: string, projectId: string): Promise<TWorkItemTemplate[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-templates/`).then(
      (response) => response.data
    );
  }

  async createTemplate(workspaceSlug: string, projectId: string, data: Omit<TWorkItemTemplate, "id">) {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-templates/`, data).then(
      (response) => response.data
    );
  }

  async deleteTemplate(workspaceSlug: string, projectId: string, templateId: string) {
    await this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-templates/${templateId}/`);
  }

  async listWorkItemTypes(workspaceSlug: string, projectId: string): Promise<TWorkItemType[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/`).then(
      (response) => response.data
    );
  }

  async listAvailableWorkItemTypes(
    workspaceSlug: string,
    projectId: string
  ): Promise<TAvailableWorkItemType[]> {
    return this.get(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/?available=true`
    ).then((response) => response.data);
  }

  async addWorkItemType(workspaceSlug: string, projectId: string, issueTypeId: string) {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/`, {
      issue_type_id: issueTypeId,
    }).then((response) => response.data);
  }

  async deleteWorkItemType(workspaceSlug: string, projectId: string, typeId: string) {
    await this.delete(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/${typeId}/`);
  }
}

export const projectCustomizationService = new ProjectCustomizationService();
