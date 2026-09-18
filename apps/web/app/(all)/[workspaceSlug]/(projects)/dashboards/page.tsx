/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * THM: list of custom dashboards in the workspace.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { Link } from "react-router";
import { DashboardsOutline } from "@makeplane/propel/icons";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import type { TThmDashboard } from "@plane/types";
// components
import { AppHeader } from "@/components/core/app-header";
import { PageHead } from "@/components/core/page-title";
import { ThmDashboardModal, type TThmDashboardForm } from "@/components/thm-dashboards/dashboard-modal";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUserPermissions } from "@/hooks/store/user";
// services
import { thmDashboardService } from "@/services/workspace/thm-dashboard.service";
// local imports
import type { Route } from "./+types/page";
import { ThmDashboardsHeader } from "./header";

function ThmDashboardsListPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const { t } = useTranslation();
  const { currentWorkspace } = useWorkspace();
  const { allowPermissions } = useUserPermissions();
  const { getProjectById } = useProject();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const canCreate = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE
  );

  const { data: dashboards, mutate } = useSWR(`THM_DASHBOARDS_${workspaceSlug}`, () =>
    thmDashboardService.list(workspaceSlug)
  );

  const create = async (data: TThmDashboardForm) => {
    await thmDashboardService.create(workspaceSlug, data);
    await mutate();
  };

  const scopeLabel = (d: TThmDashboard) =>
    d.project ? (getProjectById(d.project)?.name ?? "") : t("thm_dashboards.form.project_scope_all");

  return (
    <>
      <AppHeader
        header={
          <ThmDashboardsHeader
            rightItem={
              canCreate && (
                <Button variant="primary" size="sm" onClick={() => setIsCreateOpen(true)}>
                  {t("thm_dashboards.create")}
                </Button>
              )
            }
          />
        }
      />
      <PageHead
        title={currentWorkspace?.name ? `${currentWorkspace.name} - ${t("thm_dashboards.label")}` : undefined}
      />
      <ThmDashboardModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} onSubmit={create} />
      <div className="flex h-full w-full flex-col gap-4 overflow-y-auto px-6 py-6 md:px-10">
        {dashboards && dashboards.length === 0 && (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-subtle py-16 text-center">
            <DashboardsOutline className="size-8 text-placeholder" />
            <p className="text-14 font-medium text-primary">{t("thm_dashboards.empty.title")}</p>
            <p className="max-w-md text-13 text-tertiary">{t("thm_dashboards.empty.description")}</p>
            {canCreate && (
              <Button variant="primary" size="sm" onClick={() => setIsCreateOpen(true)}>
                {t("thm_dashboards.create")}
              </Button>
            )}
          </div>
        )}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {dashboards?.map((d) => (
            <Link
              key={d.id}
              to={`/${workspaceSlug}/dashboards/${d.id}/`}
              className="flex flex-col gap-2 rounded-lg border border-subtle bg-surface-1 p-4 transition-colors hover:border-strong hover:bg-layer-transparent-hover"
            >
              <div className="flex items-center gap-2">
                <DashboardsOutline className="size-4 shrink-0 text-tertiary" />
                <span className="truncate text-14 font-medium text-primary">{d.name}</span>
              </div>
              {d.description && <p className="line-clamp-2 text-13 text-tertiary">{d.description}</p>}
              <div className="text-caption mt-auto flex flex-wrap gap-x-3 pt-1 text-tertiary">
                <span>{t("thm_dashboards.widget_count", { count: d.widget_count })}</span>
                <span>{scopeLabel(d)}</span>
                {!d.is_shared && <span>{t("thm_dashboards.private")}</span>}
                {d.owner_detail && <span>{d.owner_detail.display_name ?? d.owner_detail.email}</span>}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}

export default observer(ThmDashboardsListPage);
