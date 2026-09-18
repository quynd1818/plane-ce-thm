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
import type { TThmDashboard } from "@plane/types";
import { ModalCore } from "@plane/ui";
// hooks
import { useProject } from "@/hooks/store/use-project";

export type TThmDashboardForm = Pick<TThmDashboard, "name" | "description" | "project" | "is_shared">;

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: TThmDashboardForm) => Promise<void>;
  dashboard?: TThmDashboard | null;
};

const selectClass =
  "w-full rounded-md border border-strong bg-surface-1 px-2 py-1.5 text-13 text-secondary focus:border-transparent focus:ring-2 focus:ring-accent-strong focus:outline-none";

/** THM: create / edit a dashboard. */
export const ThmDashboardModal = observer(function ThmDashboardModal({ isOpen, onClose, onSubmit, dashboard }: Props) {
  const { t } = useTranslation();
  const { joinedProjectIds, getProjectById } = useProject();
  const [form, setForm] = useState<TThmDashboardForm>({ name: "", description: "", project: null, is_shared: true });
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setForm(
      dashboard
        ? {
            name: dashboard.name,
            description: dashboard.description,
            project: dashboard.project,
            is_shared: dashboard.is_shared,
          }
        : { name: "", description: "", project: null, is_shared: true }
    );
  }, [isOpen, dashboard]);

  const submit = async () => {
    if (!form.name.trim()) return;
    setIsSubmitting(true);
    try {
      await onSubmit({ ...form, name: form.name.trim(), description: form.description.trim() });
      onClose();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: t("toast.error"), message: t("something_went_wrong") });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <div className="space-y-4 p-5">
          <h3 className="text-18 font-medium text-secondary">
            {dashboard ? t("thm_dashboards.edit") : t("thm_dashboards.create")}
          </h3>
          <div>
            <label htmlFor="thm-dashboard-name" className="mb-1 block text-13 text-tertiary">
              {t("thm_dashboards.form.name")}
            </label>
            <InputGroup size="xl">
              <Input
                size="xl"
                id="thm-dashboard-name"
                value={form.name}
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                placeholder={t("thm_dashboards.form.name_placeholder")}
                maxLength={255}
              />
            </InputGroup>
          </div>
          <div>
            <label htmlFor="thm-dashboard-description" className="mb-1 block text-13 text-tertiary">
              {t("thm_dashboards.form.description")}
            </label>
            <TextAreaGroup resize="none">
              <TextArea
                size="lg"
                surface="field"
                id="thm-dashboard-description"
                value={form.description}
                onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                rows={2}
              />
            </TextAreaGroup>
          </div>
          <label className="flex flex-col gap-1 text-13 text-tertiary">
            {t("thm_dashboards.form.project_scope")}
            <select
              className={selectClass}
              value={form.project ?? ""}
              onChange={(e) => setForm((p) => ({ ...p, project: e.target.value || null }))}
            >
              <option value="">{t("thm_dashboards.form.project_scope_all")}</option>
              {joinedProjectIds.map((id) => {
                const p = getProjectById(id);
                return p ? (
                  <option key={id} value={id}>
                    {p.identifier} · {p.name}
                  </option>
                ) : null;
              })}
            </select>
          </label>
          <label className="flex items-start gap-2 text-13 text-secondary">
            <Checkbox
              checked={form.is_shared}
              onCheckedChange={(c) => setForm((p) => ({ ...p, is_shared: c === true }))}
              aria-label={t("thm_dashboards.form.shared")}
            />
            <span>
              {t("thm_dashboards.form.shared")}
              <span className="text-caption block text-tertiary">{t("thm_dashboards.form.shared_hint")}</span>
            </span>
          </label>
        </div>
        <div className="flex items-center justify-end gap-2 border-t-[0.5px] border-subtle px-5 py-4">
          <Button variant="secondary" size="lg" onClick={onClose} type="button">
            {t("cancel")}
          </Button>
          <Button variant="primary" size="lg" type="submit" loading={isSubmitting} disabled={!form.name.trim()}>
            {dashboard ? t("save") : t("thm_dashboards.create")}
          </Button>
        </div>
      </form>
    </ModalCore>
  );
});
