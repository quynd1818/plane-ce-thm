/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * THM: one dashboard — a 3-column grid of widgets. Owners / workspace
 * admins can add, edit, resize, reorder and delete widgets.
 */

import { useCallback, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import {
  ArrowNarrowLeftOutline,
  ArrowNarrowRightOutline,
  DeleteOutline,
  EditOutline,
  RefreshOutline,
} from "@makeplane/propel/icons";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TThmWidget, TThmWidgetInput } from "@plane/types";
import { AlertModalCore } from "@plane/ui";
import { cn } from "@plane/utils";
// components
import { AppHeader } from "@/components/core/app-header";
import { PageHead } from "@/components/core/page-title";
import { ThmDashboardModal, type TThmDashboardForm } from "@/components/thm-dashboards/dashboard-modal";
import { ThmWidgetChart } from "@/components/thm-dashboards/widget-chart";
import { ThmWidgetModal } from "@/components/thm-dashboards/widget-modal";
// hooks
import { useAppRouter } from "@/hooks/use-app-router";
// services
import { thmDashboardService } from "@/services/workspace/thm-dashboard.service";
// local imports
import type { Route } from "./+types/page";
import { ThmDashboardsHeader } from "../header";

const WIDTH_CLASS: Record<number, string> = { 1: "md:col-span-1", 2: "md:col-span-2", 3: "md:col-span-3" };
const HEIGHT_CLASS: Record<number, string> = { 1: "h-72", 2: "h-[36rem]" };

function ThmDashboardPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, dashboardId } = params;
  const { t } = useTranslation();
  const router = useAppRouter();
  // state
  const [editMode, setEditMode] = useState(false);
  const [isDashboardModalOpen, setIsDashboardModalOpen] = useState(false);
  const [widgetModal, setWidgetModal] = useState<{ open: boolean; widget: TThmWidget | null }>({
    open: false,
    widget: null,
  });
  const [deletingWidget, setDeletingWidget] = useState<TThmWidget | null>(null);
  const [deletingDashboard, setDeletingDashboard] = useState(false);
  const [busy, setBusy] = useState(false);

  const {
    data: dashboard,
    mutate: mutateDashboard,
    error,
  } = useSWR(`THM_DASHBOARD_${dashboardId}`, () => thmDashboardService.retrieve(workspaceSlug, dashboardId));
  const { data: widgetData, mutate: mutateData } = useSWR(
    dashboard ? `THM_DASHBOARD_DATA_${dashboardId}` : null,
    () => thmDashboardService.dashboardData(workspaceSlug, dashboardId),
    { refreshInterval: 5 * 60 * 1000 }
  );

  const refreshAll = useCallback(async () => {
    await Promise.all([mutateDashboard(), mutateData()]);
  }, [mutateDashboard, mutateData]);

  const fail = (message?: string) =>
    setToast({ type: TOAST_TYPE.ERROR, title: t("toast.error"), message: message ?? t("something_went_wrong") });

  const saveWidget = async (data: TThmWidgetInput) => {
    if (widgetModal.widget)
      await thmDashboardService.updateWidget(workspaceSlug, dashboardId, widgetModal.widget.id, data);
    else await thmDashboardService.createWidget(workspaceSlug, dashboardId, data);
    await refreshAll();
  };

  const deleteWidget = async () => {
    if (!deletingWidget) return;
    setBusy(true);
    try {
      await thmDashboardService.removeWidget(workspaceSlug, dashboardId, deletingWidget.id);
      setDeletingWidget(null);
      await refreshAll();
    } catch {
      fail();
    } finally {
      setBusy(false);
    }
  };

  const move = async (widget: TThmWidget, direction: -1 | 1) => {
    if (!dashboard) return;
    const ordered = [...dashboard.widgets];
    const index = ordered.findIndex((w) => w.id === widget.id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= ordered.length) return;
    [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
    try {
      await thmDashboardService.reorderWidgets(
        workspaceSlug,
        dashboardId,
        ordered.map((w, i) => ({ id: w.id, sort_order: (i + 1) * 10000 }))
      );
      await mutateDashboard();
    } catch {
      fail();
    }
  };

  const resize = async (widget: TThmWidget) => {
    const width = ((widget.width % 3) + 1) as 1 | 2 | 3;
    try {
      await thmDashboardService.updateWidget(workspaceSlug, dashboardId, widget.id, { width });
      await mutateDashboard();
    } catch {
      fail();
    }
  };

  const updateDashboard = async (data: TThmDashboardForm) => {
    await thmDashboardService.update(workspaceSlug, dashboardId, data);
    await refreshAll();
  };

  const deleteDashboard = async () => {
    setBusy(true);
    try {
      await thmDashboardService.remove(workspaceSlug, dashboardId);
      router.push(`/${workspaceSlug}/dashboards/`);
    } catch {
      fail();
      setBusy(false);
    }
  };

  if (error) {
    return (
      <>
        <AppHeader header={<ThmDashboardsHeader workspaceSlug={workspaceSlug} />} />
        <div className="flex h-full items-center justify-center text-13 text-tertiary">
          {t("thm_dashboards.not_found")}
        </div>
      </>
    );
  }

  const canEdit = Boolean(dashboard?.can_edit);

  return (
    <>
      <AppHeader
        header={
          <ThmDashboardsHeader
            workspaceSlug={workspaceSlug}
            dashboardName={dashboard?.name ?? "…"}
            rightItem={
              <>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void mutateData()}
                  prependIcon={<RefreshOutline className="size-3.5" />}
                >
                  {t("thm_dashboards.refresh")}
                </Button>
                {canEdit && (
                  <>
                    <Button variant="secondary" size="sm" onClick={() => setEditMode((v) => !v)}>
                      {editMode ? t("thm_dashboards.done_editing") : t("thm_dashboards.edit_layout")}
                    </Button>
                    <Button variant="primary" size="sm" onClick={() => setWidgetModal({ open: true, widget: null })}>
                      {t("thm_dashboards.widget.add")}
                    </Button>
                  </>
                )}
              </>
            }
          />
        }
      />
      <PageHead title={dashboard?.name} />
      <ThmWidgetModal
        isOpen={widgetModal.open}
        widget={widgetModal.widget}
        lockedProjectId={dashboard?.project}
        onClose={() => setWidgetModal({ open: false, widget: null })}
        onSubmit={saveWidget}
      />
      <ThmDashboardModal
        isOpen={isDashboardModalOpen}
        dashboard={dashboard}
        onClose={() => setIsDashboardModalOpen(false)}
        onSubmit={updateDashboard}
      />
      <AlertModalCore
        isOpen={!!deletingWidget}
        handleClose={() => setDeletingWidget(null)}
        handleSubmit={() => void deleteWidget()}
        isSubmitting={busy}
        variant="danger"
        title={t("thm_dashboards.widget.delete")}
        content={t("thm_dashboards.widget.delete_confirm", { title: deletingWidget?.title ?? "" })}
      />
      <AlertModalCore
        isOpen={deletingDashboard}
        handleClose={() => setDeletingDashboard(false)}
        handleSubmit={() => void deleteDashboard()}
        isSubmitting={busy}
        variant="danger"
        title={t("thm_dashboards.delete")}
        content={t("thm_dashboards.delete_confirm", { name: dashboard?.name ?? "" })}
      />

      <div className="flex h-full w-full flex-col gap-4 overflow-y-auto px-6 py-5 md:px-10">
        {dashboard && (
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              {dashboard.description && <p className="text-13 text-tertiary">{dashboard.description}</p>}
            </div>
            {canEdit && editMode && (
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => setIsDashboardModalOpen(true)}>
                  {t("thm_dashboards.edit")}
                </Button>
                <Button variant="error-outline" size="sm" onClick={() => setDeletingDashboard(true)}>
                  {t("thm_dashboards.delete")}
                </Button>
              </div>
            )}
          </div>
        )}

        {dashboard && dashboard.widgets.length === 0 && (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-subtle py-16 text-center">
            <p className="text-14 font-medium text-primary">{t("thm_dashboards.widget.empty_title")}</p>
            <p className="max-w-md text-13 text-tertiary">{t("thm_dashboards.widget.empty_description")}</p>
            {canEdit && (
              <Button variant="primary" size="sm" onClick={() => setWidgetModal({ open: true, widget: null })}>
                {t("thm_dashboards.widget.add")}
              </Button>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {dashboard?.widgets.map((widget, index) => (
            <section
              key={widget.id}
              className={cn(
                "flex flex-col rounded-lg border border-subtle bg-surface-1 p-4",
                WIDTH_CLASS[widget.width] ?? WIDTH_CLASS[1],
                HEIGHT_CLASS[widget.height] ?? HEIGHT_CLASS[1]
              )}
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className="truncate text-13 font-medium text-primary">{widget.title}</h3>
                {canEdit && editMode && (
                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      type="button"
                      className="rounded p-1 text-tertiary hover:bg-layer-transparent-hover disabled:opacity-30"
                      disabled={index === 0}
                      onClick={() => void move(widget, -1)}
                      aria-label={t("thm_dashboards.widget.move_left")}
                    >
                      <ArrowNarrowLeftOutline className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      className="rounded p-1 text-tertiary hover:bg-layer-transparent-hover disabled:opacity-30"
                      disabled={index === dashboard.widgets.length - 1}
                      onClick={() => void move(widget, 1)}
                      aria-label={t("thm_dashboards.widget.move_right")}
                    >
                      <ArrowNarrowRightOutline className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      className="text-caption rounded px-1.5 py-0.5 text-tertiary hover:bg-layer-transparent-hover"
                      onClick={() => void resize(widget)}
                      aria-label={t("thm_dashboards.widget.width")}
                    >
                      {widget.width}/3
                    </button>
                    <button
                      type="button"
                      className="rounded p-1 text-tertiary hover:bg-layer-transparent-hover"
                      onClick={() => setWidgetModal({ open: true, widget })}
                      aria-label={t("thm_dashboards.widget.edit")}
                    >
                      <EditOutline className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      className="rounded p-1 text-danger-primary hover:bg-layer-transparent-hover"
                      onClick={() => setDeletingWidget(widget)}
                      aria-label={t("thm_dashboards.widget.delete")}
                    >
                      <DeleteOutline className="size-3.5" />
                    </button>
                  </div>
                )}
              </div>
              <div className="min-h-0 flex-1">
                <ThmWidgetChart widget={widget} data={widgetData?.[widget.id]} className="h-full" />
              </div>
            </section>
          ))}
        </div>
      </div>
    </>
  );
}

export default observer(ThmDashboardPage);
