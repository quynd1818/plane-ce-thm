/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Controller, useFormContext } from "react-hook-form";
import useSWR from "swr";
import { TemplatesOutline } from "@makeplane/propel/icons";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { IProject, TProjectTemplateLite } from "@plane/types";
import { CustomSelect } from "@plane/ui";
// services
import { projectTemplateService } from "@/services/project/project-template.service";

type Props = { workspaceSlug: string };

const summaryLine = (tpl: TProjectTemplateLite, t: (key: string, opts?: Record<string, unknown>) => string) => {
  const parts: string[] = [];
  if (tpl.summary.states) parts.push(t("project_templates.summary.states", { count: tpl.summary.states }));
  if (tpl.summary.labels) parts.push(t("project_templates.summary.labels", { count: tpl.summary.labels }));
  if (tpl.summary.modules) parts.push(t("project_templates.summary.modules", { count: tpl.summary.modules }));
  if (tpl.summary.workflow_rules)
    parts.push(t("project_templates.summary.workflow_rules", { count: tpl.summary.workflow_rules }));
  if (tpl.summary.work_items) parts.push(t("project_templates.summary.work_items", { count: tpl.summary.work_items }));
  return parts.join(" · ");
};

/**
 * THM: "Start from template" picker in the create-project form. Hidden when
 * the workspace has no templates so the stock form is unchanged.
 */
export function ProjectTemplateSelect({ workspaceSlug }: Props) {
  const { t } = useTranslation();
  const { control } = useFormContext<IProject>();
  const { data: templates } = useSWR(workspaceSlug ? `PROJECT_TEMPLATES_LITE_${workspaceSlug}` : null, () =>
    projectTemplateService.listLite(workspaceSlug)
  );

  if (!templates || templates.length === 0) return null;

  return (
    <Controller
      name="template_id"
      control={control}
      render={({ field: { onChange, value } }) => {
        const current = templates.find((tpl) => tpl.id === value);
        return (
          <div className="h-7 flex-shrink-0">
            <CustomSelect
              value={value ?? null}
              onChange={onChange}
              label={
                <div className="flex h-full items-center gap-1">
                  <TemplatesOutline className="size-3.5" />
                  {current ? current.name : <span>{t("project_templates.picker.placeholder")}</span>}
                </div>
              }
              placement="bottom-start"
              className="h-full"
              buttonClassName="h-full"
              noChevron
            >
              <CustomSelect.Option value={null}>{t("project_templates.picker.blank")}</CustomSelect.Option>
              {templates.map((tpl) => (
                <CustomSelect.Option key={tpl.id} value={tpl.id}>
                  <div className="flex flex-col">
                    <span>{tpl.name}</span>
                    <span className="text-caption text-tertiary">{summaryLine(tpl, t)}</span>
                  </div>
                </CustomSelect.Option>
              ))}
            </CustomSelect>
          </div>
        );
      }}
    />
  );
}
