/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Checkbox } from "@makeplane/propel/components/checkbox";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { TextArea, TextAreaGroup } from "@makeplane/propel/components/text-area";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TProjectTemplate } from "@plane/types";
import { CustomSelect, ModalCore } from "@plane/ui";
// hooks
import { useProject } from "@/hooks/store/use-project";
// services
import { projectTemplateService } from "@/services/project/project-template.service";

type Props = {
  isOpen: boolean;
  workspaceSlug: string;
  /** When given, the project is fixed; otherwise the user picks one they administer. */
  projectId?: string;
  onClose: () => void;
  onCreated?: (template: TProjectTemplate) => void;
};

/**
 * THM: snapshot a project into a workspace project template.
 */
export const SaveProjectAsTemplateModal = observer(function SaveProjectAsTemplateModal(props: Props) {
  const { isOpen, workspaceSlug, projectId: fixedProjectId, onClose, onCreated } = props;
  const { t } = useTranslation();
  const { joinedProjectIds, getProjectById } = useProject();
  const [projectId, setProjectId] = useState<string | null>(fixedProjectId ?? null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [includeWorkItems, setIncludeWorkItems] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const project = getProjectById(projectId);

  useEffect(() => {
    if (!isOpen) return;
    setProjectId(fixedProjectId ?? null);
    setName(fixedProjectId ? (getProjectById(fixedProjectId)?.name ?? "") : "");
    setDescription("");
    setIncludeWorkItems(false);
  }, [isOpen, fixedProjectId, getProjectById]);

  const handleSubmit = async () => {
    if (!projectId || !name.trim()) return;
    setIsSubmitting(true);
    try {
      const template = await projectTemplateService.saveProjectAsTemplate(workspaceSlug, projectId, {
        name: name.trim(),
        description: description.trim(),
        include_work_items: includeWorkItems,
      });
      setToast({ type: TOAST_TYPE.SUCCESS, title: t("success"), message: t("project_templates.toast.saved") });
      onCreated?.(template);
      onClose();
    } catch (error) {
      const data = (error as { data?: { name?: string[] } })?.data;
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("toast.error"),
        message: data?.name?.[0] ?? t("project_templates.toast.save_failed"),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void handleSubmit();
        }}
      >
        <div className="space-y-5 p-5">
          <h3 className="text-18 font-medium text-secondary">{t("project_templates.save_modal.title")}</h3>
          <div className="space-y-3">
            {!fixedProjectId && (
              <div>
                <label className="mb-2 block text-secondary">{t("project_templates.save_modal.project")}</label>
                <CustomSelect
                  value={projectId}
                  onChange={(value: string) => {
                    setProjectId(value);
                    if (!name) setName(getProjectById(value)?.name ?? "");
                  }}
                  label={project ? project.name : t("project_templates.save_modal.project_placeholder")}
                  buttonClassName="w-full"
                  className="w-full"
                  input
                >
                  {joinedProjectIds.map((id) => {
                    const details = getProjectById(id);
                    if (!details) return null;
                    return (
                      <CustomSelect.Option key={id} value={id}>
                        {details.identifier} · {details.name}
                      </CustomSelect.Option>
                    );
                  })}
                </CustomSelect>
              </div>
            )}
            <div>
              <label htmlFor="template-name" className="mb-2 block text-secondary">
                {t("project_templates.save_modal.name")}
              </label>
              <InputGroup size="2xl">
                <Input
                  size="2xl"
                  id="template-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder={t("project_templates.save_modal.name_placeholder")}
                  maxLength={255}
                />
              </InputGroup>
            </div>
            <div>
              <label htmlFor="template-description" className="mb-2 block text-secondary">
                {t("project_templates.save_modal.description")}
              </label>
              <TextAreaGroup resize="none">
                <TextArea
                  size="lg"
                  surface="field"
                  id="template-description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder={t("project_templates.save_modal.description_placeholder")}
                  rows={3}
                />
              </TextAreaGroup>
            </div>
            <label className="flex cursor-pointer items-start gap-2 text-13 text-secondary">
              <Checkbox
                checked={includeWorkItems}
                onCheckedChange={(checked) => setIncludeWorkItems(checked === true)}
                aria-label={t("project_templates.save_modal.include_work_items")}
              />
              <span>
                {t("project_templates.save_modal.include_work_items")}
                <span className="text-caption block text-tertiary">
                  {t("project_templates.save_modal.include_work_items_hint")}
                </span>
              </span>
            </label>
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t-[0.5px] border-subtle px-5 py-4">
          <Button variant="secondary" size="lg" onClick={onClose} type="button">
            {t("cancel")}
          </Button>
          <Button
            variant="primary"
            size="lg"
            type="submit"
            loading={isSubmitting}
            disabled={!projectId || !name.trim()}
          >
            {t("project_templates.save_modal.submit")}
          </Button>
        </div>
      </form>
    </ModalCore>
  );
});
