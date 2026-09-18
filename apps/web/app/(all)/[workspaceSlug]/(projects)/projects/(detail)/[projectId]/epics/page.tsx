/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * THM: project epics — large work items with progress rolled up from
 * their children. Opening an epic uses the normal work item page.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { Link } from "react-router";
import { ChevronDownOutline, ChevronRightOutline, EpicOutline } from "@makeplane/propel/icons";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TThmEpic, TThmEpicInput } from "@plane/types";
import { AlertModalCore } from "@plane/ui";
import { cn } from "@plane/utils";
// components
import { AppHeader } from "@/components/core/app-header";
import { PageHead } from "@/components/core/page-title";
import { ThmAttachWorkItemsModal } from "@/components/thm-epics/attach-work-items-modal";
import { ThmEpicModal } from "@/components/thm-epics/epic-modal";
import { ThmRollupBar } from "@/components/thm-epics/rollup-bar";
// hooks
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
import { useProjectState } from "@/hooks/store/use-project-state";
import { useUserPermissions } from "@/hooks/store/user";
// services
import { thmEpicService } from "@/services/project/epic.service";
// local imports
import type { Route } from "./+types/page";
import { ProjectEpicsHeader } from "./header";

const STATE_GROUP_FILTERS = ["", "backlog", "unstarted", "started", "completed", "cancelled"];

function ProjectEpicsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { t } = useTranslation();
  // store hooks
  const { currentProjectDetails } = useProject();
  const { getStateById } = useProjectState();
  const { getUserDetails } = useMember();
  const { allowPermissions } = useUserPermissions();
  // state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [attachFor, setAttachFor] = useState<TThmEpic | null>(null);
  const [demoting, setDemoting] = useState<TThmEpic | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [stateGroup, setStateGroup] = useState("");
  const [busy, setBusy] = useState(false);
  // derived values
  const canEdit = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug,
    projectId
  );
  const isEnabled = Boolean(currentProjectDetails?.is_epic_enabled);
  const identifier = currentProjectDetails?.identifier ?? "";

  const { data: epics, mutate } = useSWR(`THM_EPICS_${projectId}_${stateGroup}`, () =>
    thmEpicService.list(workspaceSlug, projectId, stateGroup || undefined)
  );
  const { data: expandedEpic, mutate: mutateExpanded } = useSWR(expanded ? `THM_EPIC_${expanded}` : null, () =>
    expanded ? thmEpicService.retrieve(workspaceSlug, projectId, expanded) : null
  );

  const refresh = async () => {
    await Promise.all([mutate(), mutateExpanded()]);
  };

  const create = async (data: TThmEpicInput) => {
    await thmEpicService.create(workspaceSlug, projectId, data);
    await mutate();
  };

  const attach = async (issueIds: string[]) => {
    if (!attachFor) return;
    await thmEpicService.attach(workspaceSlug, projectId, attachFor.id, issueIds);
    await refresh();
  };

  const detach = async (epicId: string, issueId: string) => {
    try {
      await thmEpicService.detach(workspaceSlug, projectId, epicId, [issueId]);
      await refresh();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("toast.error"), message: t("something_went_wrong") });
    }
  };

  const demote = async () => {
    if (!demoting) return;
    setBusy(true);
    try {
      await thmEpicService.demote(workspaceSlug, projectId, demoting.id);
      setDemoting(null);
      if (expanded === demoting.id) setExpanded(null);
      await mutate();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("toast.error"), message: t("something_went_wrong") });
    } finally {
      setBusy(false);
    }
  };

  const workItemLink = (sequenceId: number) => `/${workspaceSlug}/browse/${identifier}-${sequenceId}/`;

  return (
    <>
      <AppHeader
        header={
          <ProjectEpicsHeader
            workspaceSlug={workspaceSlug}
            projectId={projectId}
            rightItem={
              canEdit &&
              isEnabled && (
                <Button variant="primary" size="sm" onClick={() => setIsCreateOpen(true)}>
                  {t("thm_epics.create")}
                </Button>
              )
            }
          />
        }
      />
      <PageHead
        title={currentProjectDetails?.name ? `${currentProjectDetails.name} - ${t("sidebar.epics")}` : undefined}
      />
      <ThmEpicModal
        isOpen={isCreateOpen}
        projectId={projectId}
        onClose={() => setIsCreateOpen(false)}
        onSubmit={create}
      />
      {attachFor && (
        <ThmAttachWorkItemsModal
          isOpen
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          epicId={attachFor.id}
          onClose={() => setAttachFor(null)}
          onAttach={attach}
        />
      )}
      <AlertModalCore
        isOpen={!!demoting}
        handleClose={() => setDemoting(null)}
        handleSubmit={() => void demote()}
        isSubmitting={busy}
        variant="danger"
        title={t("thm_epics.demote")}
        content={t("thm_epics.demote_confirm", { name: demoting?.name ?? "" })}
      />

      <div className="flex h-full w-full flex-col gap-4 overflow-y-auto px-6 py-5 md:px-10">
        {!isEnabled && (
          <p className="rounded-md border border-subtle px-4 py-3 text-13 text-tertiary">{t("thm_epics.disabled")}</p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {STATE_GROUP_FILTERS.map((g) => (
            <button
              key={g || "all"}
              type="button"
              onClick={() => setStateGroup(g)}
              className={cn(
                "text-caption rounded-full border px-3 py-1",
                stateGroup === g
                  ? "border-accent-strong bg-accent-primary/10 text-accent-primary"
                  : "border-subtle text-tertiary"
              )}
            >
              {g ? t(`thm_epics.state_group.${g}`) : t("common.all")}
            </button>
          ))}
        </div>

        {epics && epics.length === 0 && (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-subtle py-16 text-center">
            <EpicOutline className="size-8 text-placeholder" />
            <p className="text-14 font-medium text-primary">{t("thm_epics.empty.title")}</p>
            <p className="max-w-md text-13 text-tertiary">{t("thm_epics.empty.description")}</p>
          </div>
        )}

        <div className="flex flex-col divide-y divide-subtle rounded-lg border border-subtle bg-surface-1">
          {epics?.map((epic) => {
            const state = getStateById(epic.state_id);
            const isOpen = expanded === epic.id;
            return (
              <div key={epic.id} className="flex flex-col">
                <div className="flex items-center gap-3 px-4 py-3">
                  <button
                    type="button"
                    className="shrink-0 rounded p-0.5 text-tertiary hover:bg-layer-transparent-hover"
                    onClick={() => setExpanded(isOpen ? null : epic.id)}
                    aria-label={isOpen ? t("thm_epics.collapse") : t("thm_epics.expand")}
                  >
                    {isOpen ? (
                      <ChevronDownOutline className="size-3.5" />
                    ) : (
                      <ChevronRightOutline className="size-3.5" />
                    )}
                  </button>
                  <EpicOutline className="size-4 shrink-0 text-tertiary" />
                  <span className="text-caption shrink-0 text-tertiary">
                    {identifier}-{epic.sequence_id}
                  </span>
                  <Link
                    to={workItemLink(epic.sequence_id)}
                    className="min-w-0 flex-1 truncate text-13 font-medium text-primary hover:underline"
                  >
                    {epic.name}
                  </Link>
                  {state && (
                    <span className="text-caption flex shrink-0 items-center gap-1 text-tertiary">
                      <span className="size-2 rounded-full" style={{ backgroundColor: state.color }} />
                      {state.name}
                    </span>
                  )}
                  {epic.target_date && <span className="text-caption shrink-0 text-tertiary">{epic.target_date}</span>}
                  {epic.assignee_ids.length > 0 && (
                    <span className="text-caption hidden shrink-0 truncate text-tertiary md:inline">
                      {epic.assignee_ids
                        .map((id) => getUserDetails(id)?.display_name ?? "")
                        .filter(Boolean)
                        .join(", ")}
                    </span>
                  )}
                  <ThmRollupBar rollup={epic.rollup} className="w-56 shrink-0" />
                  {canEdit && (
                    <div className="flex shrink-0 items-center gap-1">
                      <Button variant="secondary" size="sm" onClick={() => setAttachFor(epic)}>
                        {t("thm_epics.attach.action")}
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => setDemoting(epic)}>
                        {t("thm_epics.demote")}
                      </Button>
                    </div>
                  )}
                </div>
                {isOpen && (
                  <div className="border-t border-subtle bg-layer-1 px-4 py-2 pl-12">
                    {expandedEpic?.id === epic.id ? (
                      expandedEpic.work_items.length === 0 ? (
                        <p className="py-2 text-13 text-tertiary">{t("thm_epics.no_children")}</p>
                      ) : (
                        expandedEpic.work_items.map((child) => {
                          const childState = getStateById(child.state_id);
                          return (
                            <div key={child.id} className="flex items-center gap-3 py-1.5 text-13">
                              <span
                                className="size-2 shrink-0 rounded-full"
                                style={{ backgroundColor: childState?.color }}
                              />
                              <span className="text-caption shrink-0 text-tertiary">
                                {identifier}-{child.sequence_id}
                              </span>
                              <Link
                                to={workItemLink(child.sequence_id)}
                                className="min-w-0 flex-1 truncate hover:underline"
                              >
                                {child.name}
                              </Link>
                              <span className="text-caption shrink-0 text-tertiary">{childState?.name}</span>
                              {child.target_date && (
                                <span className="text-caption shrink-0 text-tertiary">{child.target_date}</span>
                              )}
                              {canEdit && (
                                <button
                                  type="button"
                                  className="text-caption shrink-0 text-tertiary hover:text-danger-primary"
                                  onClick={() => void detach(epic.id, child.id)}
                                >
                                  {t("thm_epics.detach")}
                                </button>
                              )}
                            </div>
                          );
                        })
                      )
                    ) : (
                      <p className="py-2 text-13 text-tertiary">{t("loading")}</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

export default observer(ProjectEpicsPage);
