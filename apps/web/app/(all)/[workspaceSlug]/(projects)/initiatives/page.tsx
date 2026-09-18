/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * THM: workspace initiatives list.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { Link } from "react-router";
import { InitiativeOutline } from "@makeplane/propel/icons";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import type { TThmInitiativeInput, TThmInitiativeStatus } from "@plane/types";
import { cn } from "@plane/utils";
// components
import { AppHeader } from "@/components/core/app-header";
import { PageHead } from "@/components/core/page-title";
import { ThmInitiativeModal, INITIATIVE_STATUSES } from "@/components/thm-epics/initiative-modal";
import { ThmRollupBar } from "@/components/thm-epics/rollup-bar";
// hooks
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUserPermissions } from "@/hooks/store/user";
// services
import { thmInitiativeService } from "@/services/workspace/initiative.service";
// local imports
import type { Route } from "./+types/page";
import { ThmInitiativesHeader } from "./header";

const STATUS_CLASS: Record<TThmInitiativeStatus, string> = {
  planned: "bg-layer-2 text-secondary",
  in_progress: "bg-warning-subtle text-warning-primary",
  completed: "bg-success-subtle text-success-primary",
  cancelled: "bg-danger-subtle text-danger-primary",
};

function ThmInitiativesListPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const { t } = useTranslation();
  const { currentWorkspace } = useWorkspace();
  const { allowPermissions } = useUserPermissions();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<TThmInitiativeStatus | "">("");
  const canCreate = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE
  );

  const { data: initiatives, mutate } = useSWR(`THM_INITIATIVES_${workspaceSlug}`, () =>
    thmInitiativeService.list(workspaceSlug)
  );

  const create = async (data: TThmInitiativeInput) => {
    await thmInitiativeService.create(workspaceSlug, data);
    await mutate();
  };

  const visible = (initiatives ?? []).filter((i) => !statusFilter || i.status === statusFilter);

  return (
    <>
      <AppHeader
        header={
          <ThmInitiativesHeader
            rightItem={
              canCreate && (
                <Button variant="primary" size="sm" onClick={() => setIsCreateOpen(true)}>
                  {t("thm_initiatives.create")}
                </Button>
              )
            }
          />
        }
      />
      <PageHead
        title={currentWorkspace?.name ? `${currentWorkspace.name} - ${t("thm_initiatives.label")}` : undefined}
      />
      <ThmInitiativeModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} onSubmit={create} />
      <div className="flex h-full w-full flex-col gap-4 overflow-y-auto px-6 py-5 md:px-10">
        <div className="flex flex-wrap items-center gap-2">
          {(["", ...INITIATIVE_STATUSES] as (TThmInitiativeStatus | "")[]).map((s) => (
            <button
              key={s || "all"}
              type="button"
              onClick={() => setStatusFilter(s)}
              className={cn(
                "text-caption rounded-full border px-3 py-1",
                statusFilter === s
                  ? "border-accent-strong bg-accent-primary/10 text-accent-primary"
                  : "border-subtle text-tertiary"
              )}
            >
              {s ? t(`thm_initiatives.status.${s}`) : t("common.all")}
            </button>
          ))}
        </div>

        {initiatives && visible.length === 0 && (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-subtle py-16 text-center">
            <InitiativeOutline className="size-8 text-placeholder" />
            <p className="text-14 font-medium text-primary">{t("thm_initiatives.empty.title")}</p>
            <p className="max-w-md text-13 text-tertiary">{t("thm_initiatives.empty.description")}</p>
            {canCreate && !statusFilter && (
              <Button variant="primary" size="sm" onClick={() => setIsCreateOpen(true)}>
                {t("thm_initiatives.create")}
              </Button>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((initiative) => (
            <Link
              key={initiative.id}
              to={`/${workspaceSlug}/initiatives/${initiative.id}/`}
              className="flex flex-col gap-3 rounded-lg border border-subtle bg-surface-1 p-4 transition-colors hover:border-strong hover:bg-layer-transparent-hover"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <InitiativeOutline className="size-4 shrink-0 text-tertiary" />
                  <span className="truncate text-14 font-medium text-primary">{initiative.name}</span>
                </div>
                <span className={cn("text-caption shrink-0 rounded-full px-2 py-0.5", STATUS_CLASS[initiative.status])}>
                  {t(`thm_initiatives.status.${initiative.status}`)}
                </span>
              </div>
              {initiative.analytics && <ThmRollupBar rollup={initiative.analytics} />}
              <div className="text-caption flex flex-wrap gap-x-3 text-tertiary">
                <span>{t("thm_initiatives.project_count", { count: initiative.project_ids.length })}</span>
                <span>{t("thm_initiatives.epic_count", { count: initiative.epic_ids.length })}</span>
                {initiative.lead_detail && (
                  <span>{initiative.lead_detail.display_name ?? initiative.lead_detail.email}</span>
                )}
                {(initiative.start_date || initiative.end_date) && (
                  <span>
                    {initiative.start_date ?? "…"} → {initiative.end_date ?? "…"}
                  </span>
                )}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}

export default observer(ThmInitiativesListPage);
