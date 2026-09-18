/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * THM: one initiative — progress rollup, linked projects and epics.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { Link } from "react-router";
import { EpicOutline } from "@makeplane/propel/icons";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TThmInitiativeInput } from "@plane/types";
import { AlertModalCore } from "@plane/ui";
import { cn } from "@plane/utils";
// components
import { Logo } from "@plane/propel/emoji-icon-picker";
import { AppHeader } from "@/components/core/app-header";
import { PageHead } from "@/components/core/page-title";
import { ThmInitiativeModal, htmlToText } from "@/components/thm-epics/initiative-modal";
import { ThmRollupBar } from "@/components/thm-epics/rollup-bar";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useAppRouter } from "@/hooks/use-app-router";
// services
import { thmEpicService } from "@/services/project/epic.service";
import { thmInitiativeService } from "@/services/workspace/initiative.service";
// local imports
import type { Route } from "./+types/page";
import { ThmInitiativesHeader } from "../header";

const selectClass =
  "rounded-md border border-strong bg-surface-1 px-2 py-1.5 text-13 text-secondary focus:border-transparent focus:ring-2 focus:ring-accent-strong focus:outline-none";

const STAT_KEYS = ["total", "completed", "started", "unstarted", "backlog", "overdue"] as const;

function ThmInitiativePage({ params }: Route.ComponentProps) {
  const { workspaceSlug, initiativeId } = params;
  const { t } = useTranslation();
  const router = useAppRouter();
  const { joinedProjectIds, getProjectById } = useProject();
  // state
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [projectToAdd, setProjectToAdd] = useState("");
  const [epicToAdd, setEpicToAdd] = useState("");

  const {
    data: initiative,
    mutate,
    error,
  } = useSWR(`THM_INITIATIVE_${initiativeId}`, () => thmInitiativeService.retrieve(workspaceSlug, initiativeId));
  const { data: allEpics } = useSWR(initiative?.can_edit ? `THM_WORKSPACE_EPICS_${workspaceSlug}` : null, () =>
    thmEpicService.listWorkspace(workspaceSlug)
  );

  const fail = () => setToast({ type: TOAST_TYPE.ERROR, title: t("toast.error"), message: t("something_went_wrong") });
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      await mutate();
    } catch {
      fail();
    } finally {
      setBusy(false);
    }
  };

  const update = async (data: TThmInitiativeInput) => {
    await thmInitiativeService.update(workspaceSlug, initiativeId, data);
    await mutate();
  };

  const remove = async () => {
    setBusy(true);
    try {
      await thmInitiativeService.remove(workspaceSlug, initiativeId);
      router.push(`/${workspaceSlug}/initiatives/`);
    } catch {
      fail();
      setBusy(false);
    }
  };

  const addableProjects = useMemo(
    () => joinedProjectIds.filter((id) => !initiative?.project_ids.includes(id)),
    [joinedProjectIds, initiative]
  );
  const addableEpics = useMemo(
    () => (allEpics ?? []).filter((e) => !initiative?.epic_ids.includes(e.id)),
    [allEpics, initiative]
  );

  if (error) {
    return (
      <>
        <AppHeader header={<ThmInitiativesHeader workspaceSlug={workspaceSlug} />} />
        <div className="flex h-full items-center justify-center text-13 text-tertiary">
          {t("thm_initiatives.not_found")}
        </div>
      </>
    );
  }

  const canEdit = Boolean(initiative?.can_edit);

  return (
    <>
      <AppHeader
        header={
          <ThmInitiativesHeader
            workspaceSlug={workspaceSlug}
            initiativeName={initiative?.name ?? "…"}
            rightItem={
              canEdit && (
                <>
                  <Button variant="secondary" size="sm" onClick={() => setIsEditOpen(true)}>
                    {t("thm_initiatives.edit")}
                  </Button>
                  <Button variant="error-outline" size="sm" onClick={() => setIsDeleting(true)}>
                    {t("thm_initiatives.delete")}
                  </Button>
                </>
              )
            }
          />
        }
      />
      <PageHead title={initiative?.name} />
      <ThmInitiativeModal
        isOpen={isEditOpen}
        initiative={initiative}
        onClose={() => setIsEditOpen(false)}
        onSubmit={update}
      />
      <AlertModalCore
        isOpen={isDeleting}
        handleClose={() => setIsDeleting(false)}
        handleSubmit={() => void remove()}
        isSubmitting={busy}
        variant="danger"
        title={t("thm_initiatives.delete")}
        content={t("thm_initiatives.delete_confirm", { name: initiative?.name ?? "" })}
      />

      {initiative && (
        <div className="flex h-full w-full flex-col gap-6 overflow-y-auto px-6 py-5 md:px-10">
          <section className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-3 text-13 text-tertiary">
              <span className="text-caption rounded-full bg-layer-2 px-2 py-0.5 text-secondary">
                {t(`thm_initiatives.status.${initiative.status}`)}
              </span>
              {initiative.lead_detail && (
                <span>
                  {t("thm_initiatives.form.lead")}:{" "}
                  {initiative.lead_detail.display_name ?? initiative.lead_detail.email}
                </span>
              )}
              {(initiative.start_date || initiative.end_date) && (
                <span>
                  {initiative.start_date ?? "…"} → {initiative.end_date ?? "…"}
                </span>
              )}
            </div>
            {initiative.description_html && initiative.description_html !== "<p></p>" && (
              <p className="max-w-3xl text-13 whitespace-pre-line text-secondary">
                {htmlToText(initiative.description_html)}
              </p>
            )}
            <ThmRollupBar rollup={initiative.analytics} className="max-w-xl" />
            <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
              {STAT_KEYS.map((key) => (
                <div key={key} className="rounded-lg border border-subtle bg-surface-1 px-3 py-2">
                  <p className="text-caption text-tertiary">{t(`thm_initiatives.stats.${key}`)}</p>
                  <p
                    className={cn(
                      "text-18 font-semibold text-primary",
                      key === "overdue" && initiative.analytics.overdue > 0 && "text-danger-primary"
                    )}
                  >
                    {initiative.analytics[key]}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section className="flex flex-col gap-2">
            <h2 className="text-14 font-medium text-primary">{t("thm_initiatives.projects")}</h2>
            <div className="flex flex-col divide-y divide-subtle rounded-lg border border-subtle bg-surface-1">
              {initiative.projects.length === 0 && (
                <p className="px-4 py-3 text-13 text-tertiary">{t("thm_initiatives.no_projects")}</p>
              )}
              {initiative.projects.map((project) => (
                <div key={project.id} className="flex items-center gap-3 px-4 py-2.5 text-13">
                  <Logo logo={project.logo_props as never} size={16} />
                  <span className="text-caption shrink-0 text-tertiary">{project.identifier}</span>
                  {project.is_member ? (
                    <Link
                      to={`/${workspaceSlug}/projects/${project.id}/issues/`}
                      className="min-w-0 flex-1 truncate hover:underline"
                    >
                      {project.name}
                    </Link>
                  ) : (
                    <span className="min-w-0 flex-1 truncate text-tertiary">
                      {project.name} · {t("thm_initiatives.not_a_member")}
                    </span>
                  )}
                  {canEdit && (
                    <button
                      type="button"
                      className="text-caption text-tertiary hover:text-danger-primary"
                      disabled={busy}
                      onClick={() =>
                        void run(() => thmInitiativeService.removeProjects(workspaceSlug, initiativeId, [project.id]))
                      }
                    >
                      {t("thm_initiatives.unlink")}
                    </button>
                  )}
                </div>
              ))}
              {canEdit && addableProjects.length > 0 && (
                <div className="flex items-center gap-2 px-4 py-2.5">
                  <select
                    className={selectClass}
                    value={projectToAdd}
                    onChange={(e) => setProjectToAdd(e.target.value)}
                  >
                    <option value="">{t("thm_initiatives.pick_project")}</option>
                    {addableProjects.map((id) => {
                      const p = getProjectById(id);
                      return p ? (
                        <option key={id} value={id}>
                          {p.identifier} · {p.name}
                        </option>
                      ) : null;
                    })}
                  </select>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={!projectToAdd || busy}
                    onClick={() =>
                      void run(async () => {
                        await thmInitiativeService.addProjects(workspaceSlug, initiativeId, [projectToAdd]);
                        setProjectToAdd("");
                      })
                    }
                  >
                    {t("thm_initiatives.link")}
                  </Button>
                </div>
              )}
            </div>
          </section>

          <section className="flex flex-col gap-2">
            <h2 className="text-14 font-medium text-primary">{t("thm_initiatives.epics")}</h2>
            <div className="flex flex-col divide-y divide-subtle rounded-lg border border-subtle bg-surface-1">
              {initiative.epics.length === 0 && (
                <p className="px-4 py-3 text-13 text-tertiary">{t("thm_initiatives.no_epics")}</p>
              )}
              {initiative.epics.map((epic) => {
                const project = getProjectById(epic.project_id);
                return (
                  <div key={epic.id} className="flex items-center gap-3 px-4 py-2.5 text-13">
                    <EpicOutline className="size-4 shrink-0 text-tertiary" />
                    <span className="text-caption shrink-0 text-tertiary">
                      {project?.identifier}-{epic.sequence_id}
                    </span>
                    <Link
                      to={`/${workspaceSlug}/browse/${project?.identifier}-${epic.sequence_id}/`}
                      className="min-w-0 flex-1 truncate hover:underline"
                    >
                      {epic.name}
                    </Link>
                    <ThmRollupBar rollup={epic.rollup} className="w-56 shrink-0" />
                    {canEdit && (
                      <button
                        type="button"
                        className="text-caption text-tertiary hover:text-danger-primary"
                        disabled={busy}
                        onClick={() =>
                          void run(() => thmInitiativeService.removeEpics(workspaceSlug, initiativeId, [epic.id]))
                        }
                      >
                        {t("thm_initiatives.unlink")}
                      </button>
                    )}
                  </div>
                );
              })}
              {canEdit && addableEpics.length > 0 && (
                <div className="flex items-center gap-2 px-4 py-2.5">
                  <select className={selectClass} value={epicToAdd} onChange={(e) => setEpicToAdd(e.target.value)}>
                    <option value="">{t("thm_initiatives.pick_epic")}</option>
                    {addableEpics.map((epic) => (
                      <option key={epic.id} value={epic.id}>
                        {getProjectById(epic.project_id)?.identifier}-{epic.sequence_id} · {epic.name}
                      </option>
                    ))}
                  </select>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={!epicToAdd || busy}
                    onClick={() =>
                      void run(async () => {
                        await thmInitiativeService.addEpics(workspaceSlug, initiativeId, [epicToAdd]);
                        setEpicToAdd("");
                      })
                    }
                  >
                    {t("thm_initiatives.link")}
                  </Button>
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </>
  );
}

export default observer(ThmInitiativePage);
