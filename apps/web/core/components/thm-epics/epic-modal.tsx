/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { TextArea, TextAreaGroup } from "@makeplane/propel/components/text-area";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TThmEpicInput } from "@plane/types";
import { ModalCore } from "@plane/ui";
// components
import { MemberDropdown } from "@/components/dropdowns/member/dropdown";
// hooks
import { useProjectState } from "@/hooks/store/use-project-state";

type Props = {
  isOpen: boolean;
  projectId: string;
  onClose: () => void;
  onSubmit: (data: TThmEpicInput) => Promise<void>;
};

const PRIORITIES = ["urgent", "high", "medium", "low", "none"];
const selectClass =
  "w-full rounded-md border border-strong bg-surface-1 px-2 py-1.5 text-13 text-secondary focus:border-transparent focus:ring-2 focus:ring-accent-strong focus:outline-none";

const escapeHtml = (text: string) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** THM: create an epic (a work item of the Epic type). */
export const ThmEpicModal = observer(function ThmEpicModal({ isOpen, projectId, onClose, onSubmit }: Props) {
  const { t } = useTranslation();
  const { getProjectStates } = useProjectState();
  const states = getProjectStates(projectId) ?? [];
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("none");
  const [stateId, setStateId] = useState<string>("");
  const [startDate, setStartDate] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [assigneeIds, setAssigneeIds] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setName("");
    setDescription("");
    setPriority("none");
    setStateId((getProjectStates(projectId) ?? []).find((s) => s.default)?.id ?? "");
    setStartDate("");
    setTargetDate("");
    setAssigneeIds([]);
  }, [isOpen, projectId, getProjectStates]);

  const submit = async () => {
    if (!name.trim()) return;
    setIsSubmitting(true);
    try {
      await onSubmit({
        name: name.trim(),
        description_html: description.trim()
          ? description
              .trim()
              .split(/\n+/)
              .map((line) => `<p>${escapeHtml(line)}</p>`)
              .join("")
          : "<p></p>",
        priority,
        state_id: stateId || null,
        start_date: startDate || null,
        target_date: targetDate || null,
        assignee_ids: assigneeIds,
      });
      onClose();
    } catch (error) {
      const data = (error as { data?: Record<string, unknown> })?.data;
      const message = typeof data?.error === "string" ? data.error : t("something_went_wrong");
      setToast({ type: TOAST_TYPE.ERROR, title: t("toast.error"), message });
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
          <h3 className="text-18 font-medium text-secondary">{t("thm_epics.create")}</h3>
          <InputGroup size="xl">
            <Input
              size="xl"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("thm_epics.form.name_placeholder")}
              aria-label={t("thm_epics.form.name")}
              maxLength={255}
            />
          </InputGroup>
          <TextAreaGroup resize="none">
            <TextArea
              size="lg"
              surface="field"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("thm_epics.form.description_placeholder")}
              aria-label={t("thm_epics.form.description")}
              rows={3}
            />
          </TextAreaGroup>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_epics.form.state")}
              <select className={selectClass} value={stateId} onChange={(e) => setStateId(e.target.value)}>
                {states.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_epics.form.priority")}
              <select className={selectClass} value={priority} onChange={(e) => setPriority(e.target.value)}>
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {t(`thm_dashboards.priority.${p}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_epics.form.start_date")}
              <input
                type="date"
                className={selectClass}
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_epics.form.target_date")}
              <input
                type="date"
                className={selectClass}
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
              />
            </label>
          </div>
          <div className="flex flex-col gap-1 text-13 text-tertiary">
            {t("thm_epics.form.assignees")}
            <MemberDropdown
              value={assigneeIds}
              onChange={setAssigneeIds}
              projectId={projectId}
              multiple
              buttonVariant="border-with-text"
              placeholder={t("thm_epics.form.assignees")}
            />
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t-[0.5px] border-subtle px-5 py-4">
          <Button variant="secondary" size="lg" onClick={onClose} type="button">
            {t("cancel")}
          </Button>
          <Button variant="primary" size="lg" type="submit" loading={isSubmitting} disabled={!name.trim()}>
            {t("thm_epics.create")}
          </Button>
        </div>
      </form>
    </ModalCore>
  );
});
