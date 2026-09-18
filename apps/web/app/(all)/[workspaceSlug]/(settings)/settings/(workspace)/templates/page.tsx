/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * THM: Workspace Settings → Templates. Project templates captured from
 * existing projects; applied from the "Create project" form.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { TextArea, TextAreaGroup } from "@makeplane/propel/components/text-area";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TProjectTemplate, TProjectTemplateSummary } from "@plane/types";
import { AlertModalCore } from "@plane/ui";
// components
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SaveProjectAsTemplateModal } from "@/components/project/save-as-template-modal";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
// hooks
import { useUser, useUserPermissions } from "@/hooks/store/user";
import { useWorkspace } from "@/hooks/store/use-workspace";
// services
import { projectTemplateService } from "@/services/project/project-template.service";
// local imports
import type { Route } from "./+types/page";
import { TemplatesWorkspaceSettingsHeader } from "./header";

const SUMMARY_KEYS: (keyof TProjectTemplateSummary)[] = [
  "states",
  "labels",
  "modules",
  "workflow_rules",
  "custom_properties",
  "work_items",
];

function TemplatesPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const { t } = useTranslation();
  // store hooks
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const { currentWorkspace } = useWorkspace();
  const { data: currentUser } = useUser();
  // state
  const [isSaveModalOpen, setIsSaveModalOpen] = useState(false);
  const [editing, setEditing] = useState<TProjectTemplate | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [deleting, setDeleting] = useState<TProjectTemplate | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  // derived values
  const canView = allowPermissions([EUserPermissions.ADMIN, EUserPermissions.MEMBER], EUserPermissionsLevel.WORKSPACE);
  const isWorkspaceAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);
  const pageTitle = currentWorkspace?.name
    ? `${currentWorkspace.name} - ${t("workspace_settings.settings.templates.title")}`
    : undefined;

  const {
    data: templates,
    mutate,
    isLoading,
  } = useSWR(canView ? `PROJECT_TEMPLATES_${workspaceSlug}` : null, () => projectTemplateService.list(workspaceSlug));

  const canManage = (tpl: TProjectTemplate) => isWorkspaceAdmin || tpl.owner === currentUser?.id;

  const beginEdit = (tpl: TProjectTemplate) => {
    setEditing(tpl);
    setEditName(tpl.name);
    setEditDescription(tpl.description);
  };

  const saveEdit = async () => {
    if (!editing || !editName.trim()) return;
    setIsBusy(true);
    try {
      await projectTemplateService.update(workspaceSlug, editing.id, {
        name: editName.trim(),
        description: editDescription.trim(),
      });
      setEditing(null);
      await mutate();
    } catch (error) {
      const data = (error as { data?: { name?: string[] } })?.data;
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("toast.error"),
        message: data?.name?.[0] ?? t("project_templates.toast.save_failed"),
      });
    } finally {
      setIsBusy(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleting) return;
    setIsBusy(true);
    try {
      await projectTemplateService.remove(workspaceSlug, deleting.id);
      setDeleting(null);
      await mutate();
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("toast.error"),
        message: t("project_templates.toast.delete_failed"),
      });
    } finally {
      setIsBusy(false);
    }
  };

  if (workspaceUserInfo && !canView) {
    return <NotAuthorizedView section="settings" className="h-auto" />;
  }

  return (
    <SettingsContentWrapper header={<TemplatesWorkspaceSettingsHeader />}>
      <PageHead title={pageTitle} />
      <SaveProjectAsTemplateModal
        isOpen={isSaveModalOpen}
        workspaceSlug={workspaceSlug}
        onClose={() => setIsSaveModalOpen(false)}
        onCreated={() => void mutate()}
      />
      <AlertModalCore
        isOpen={!!deleting}
        handleClose={() => setDeleting(null)}
        handleSubmit={() => void confirmDelete()}
        isSubmitting={isBusy}
        variant="danger"
        title={t("project_templates.delete_modal.title")}
        content={t("project_templates.delete_modal.content", { name: deleting?.name ?? "" })}
      />
      <div className="flex w-full flex-col gap-y-6">
        <SettingsHeading
          title={t("workspace_settings.settings.templates.heading")}
          description={t("project_templates.page_description")}
          control={
            <Button variant="primary" size="lg" onClick={() => setIsSaveModalOpen(true)}>
              {t("project_templates.actions.new_from_project")}
            </Button>
          }
        />

        {!isLoading && (templates?.length ?? 0) === 0 && (
          <p className="text-sm rounded-md border border-subtle px-4 py-6 text-center text-tertiary">
            {t("project_templates.empty")}
          </p>
        )}

        <div className="flex flex-col divide-y divide-subtle rounded-md border border-subtle">
          {templates?.map((tpl) => (
            <div key={tpl.id} className="flex flex-col gap-2 px-4 py-3">
              {editing?.id === tpl.id ? (
                <div className="flex flex-col gap-2">
                  <InputGroup size="lg">
                    <Input
                      size="lg"
                      value={editName}
                      onChange={(event) => setEditName(event.target.value)}
                      maxLength={255}
                      aria-label={t("project_templates.save_modal.name")}
                    />
                  </InputGroup>
                  <TextAreaGroup resize="none">
                    <TextArea
                      size="lg"
                      surface="field"
                      value={editDescription}
                      onChange={(event) => setEditDescription(event.target.value)}
                      rows={2}
                      aria-label={t("project_templates.save_modal.description")}
                    />
                  </TextAreaGroup>
                  <div className="flex gap-2">
                    <Button variant="primary" size="sm" onClick={() => void saveEdit()} loading={isBusy}>
                      {t("save")}
                    </Button>
                    <Button variant="secondary" size="sm" onClick={() => setEditing(null)}>
                      {t("cancel")}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="truncate text-14 font-medium text-primary">{tpl.name}</p>
                    {tpl.description && <p className="mt-0.5 text-13 text-tertiary">{tpl.description}</p>}
                    <p className="text-caption mt-1 flex flex-wrap gap-x-3 text-tertiary">
                      {SUMMARY_KEYS.filter((key) => tpl.summary[key] > 0).map((key) => (
                        <span key={key}>{t(`project_templates.summary.${key}`, { count: tpl.summary[key] })}</span>
                      ))}
                      <span>{t("project_templates.used_count", { count: tpl.usage_count })}</span>
                      {tpl.owner_detail && <span>{tpl.owner_detail.display_name ?? tpl.owner_detail.email}</span>}
                    </p>
                  </div>
                  {canManage(tpl) && (
                    <div className="flex shrink-0 gap-2">
                      <Button variant="secondary" size="sm" onClick={() => beginEdit(tpl)}>
                        {t("common.edit")}
                      </Button>
                      <Button variant="error-outline" size="sm" onClick={() => setDeleting(tpl)}>
                        {t("common.delete")}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(TemplatesPage);
