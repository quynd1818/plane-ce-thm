/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TThmDashboard, TThmDashboardDetail, TThmWidget, TThmWidgetData, TThmWidgetInput } from "@plane/types";
import { APIService } from "@/services/api.service";

/** THM custom dashboards. */
export class ThmDashboardService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private base(workspaceSlug: string) {
    return `/api/workspaces/${workspaceSlug}/dashboards/`;
  }

  async list(workspaceSlug: string): Promise<TThmDashboard[]> {
    return this.get(this.base(workspaceSlug)).then((response) => response.data);
  }

  async retrieve(workspaceSlug: string, dashboardId: string): Promise<TThmDashboardDetail> {
    return this.get(`${this.base(workspaceSlug)}${dashboardId}/`).then((response) => response.data);
  }

  async create(
    workspaceSlug: string,
    data: Partial<Pick<TThmDashboard, "name" | "description" | "project" | "is_shared" | "logo_props">>
  ): Promise<TThmDashboard> {
    return this.post(this.base(workspaceSlug), data).then((response) => response.data);
  }

  async update(
    workspaceSlug: string,
    dashboardId: string,
    data: Partial<Pick<TThmDashboard, "name" | "description" | "project" | "is_shared" | "logo_props">>
  ): Promise<TThmDashboard> {
    return this.patch(`${this.base(workspaceSlug)}${dashboardId}/`, data).then((response) => response.data);
  }

  async remove(workspaceSlug: string, dashboardId: string): Promise<void> {
    await this.delete(`${this.base(workspaceSlug)}${dashboardId}/`);
  }

  async createWidget(workspaceSlug: string, dashboardId: string, data: TThmWidgetInput): Promise<TThmWidget> {
    return this.post(`${this.base(workspaceSlug)}${dashboardId}/widgets/`, data).then((response) => response.data);
  }

  async updateWidget(
    workspaceSlug: string,
    dashboardId: string,
    widgetId: string,
    data: TThmWidgetInput
  ): Promise<TThmWidget> {
    return this.patch(`${this.base(workspaceSlug)}${dashboardId}/widgets/${widgetId}/`, data).then(
      (response) => response.data
    );
  }

  async removeWidget(workspaceSlug: string, dashboardId: string, widgetId: string): Promise<void> {
    await this.delete(`${this.base(workspaceSlug)}${dashboardId}/widgets/${widgetId}/`);
  }

  async reorderWidgets(
    workspaceSlug: string,
    dashboardId: string,
    widgets: { id: string; sort_order: number; width?: number; height?: number }[]
  ): Promise<TThmWidget[]> {
    return this.post(`${this.base(workspaceSlug)}${dashboardId}/widgets/reorder/`, { widgets }).then(
      (response) => response.data
    );
  }

  async widgetData(workspaceSlug: string, dashboardId: string, widgetId: string): Promise<TThmWidgetData> {
    return this.get(`${this.base(workspaceSlug)}${dashboardId}/widgets/${widgetId}/data/`).then(
      (response) => response.data
    );
  }

  async dashboardData(workspaceSlug: string, dashboardId: string): Promise<Record<string, TThmWidgetData>> {
    return this.get(`${this.base(workspaceSlug)}${dashboardId}/data/`).then((response) => response.data);
  }
}

export const thmDashboardService = new ThmDashboardService();
