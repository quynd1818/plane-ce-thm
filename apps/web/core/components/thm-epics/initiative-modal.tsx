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
import type { TThmInitiative, TThmInitiativeInput, TThmInitiativeStatus } from "@plane/types";
import { ModalCore } from "@plane/ui";
// components
import { MemberDropdown } from "@/components/dropdowns/member/dropdown";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: TThmInitiativeInput) => Promise<void>;
  initiative?: TThmInitiative | null;
};

export const INITIATIVE_STATUSES: TThmInitiativeStatus[] = ["planned", "in_progress", "completed", "cancelled"];

const selectClass =
  "w-full rounded-md border border-strong bg-surface-1 px-2 py-1.5 text-13 text-secondary focus:border-transparent focus:ring-2 focus:ring-accent-strong focus:outline-none";

const escapeHtml = (text: string) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const toHtml = (text: string) =>
  text.trim()
    ? text
        .trim()
        .split(/\n+/)
        .map((line) => `<p>${escapeHtml(line)}</p>`)
        .join("")
    : "<p></p>";
export const htmlToText = (html: string) =>
  html
    .replace(/<\/p>\s*<p>/g, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .trim();

/** THM: create / edit an initiative. */
export const ThmInitiativeModal = observer(function ThmInitiativeModal({
  isOpen,
  onClose,
  onSubmit,
  initiative,
}: Props) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<TThmInitiativeStatus>("planned");
  const [lead, setLead] = useState<string | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setName(initiative?.name ?? "");
    setDescription(initiative ? htmlToText(initiative.description_html) : "");
    setStatus(initiative?.status ?? "planned");
    setLead(initiative?.lead ?? null);
    setStartDate(initiative?.start_date ?? "");
    setEndDate(initiative?.end_date ?? "");
  }, [isOpen, initiative]);

  const submit = async () => {
    if (!name.trim()) return;
    setIsSubmitting(true);
    try {
      await onSubmit({
        name: name.trim(),
        description_html: toHtml(description),
        status,
        lead,
        start_date: startDate || null,
        end_date: endDate || null,
      });
      onClose();
    } catch (error) {
      const data = (error as { data?: Record<string, string[]> })?.data;
      const first = data ? Object.values(data)[0]?.[0] : undefined;
      setToast({ type: TOAST_TYPE.ERROR, title: t("toast.error"), message: first ?? t("something_went_wrong") });
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
            {initiative ? t("thm_initiatives.edit") : t("thm_initiatives.create")}
          </h3>
          <InputGroup size="xl">
            <Input
              size="xl"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("thm_initiatives.form.name_placeholder")}
              aria-label={t("thm_initiatives.form.name")}
              maxLength={255}
            />
          </InputGroup>
          <TextAreaGroup resize="none">
            <TextArea
              size="lg"
              surface="field"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("thm_initiatives.form.description_placeholder")}
              aria-label={t("thm_initiatives.form.description")}
              rows={3}
            />
          </TextAreaGroup>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_initiatives.form.status")}
              <select
                className={selectClass}
                value={status}
                onChange={(e) => setStatus(e.target.value as TThmInitiativeStatus)}
              >
                {INITIATIVE_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {t(`thm_initiatives.status.${s}`)}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_initiatives.form.lead")}
              <MemberDropdown
                value={lead}
                onChange={setLead}
                multiple={false}
                buttonVariant="border-with-text"
                placeholder={t("thm_initiatives.form.lead")}
              />
            </div>
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_initiatives.form.start_date")}
              <input
                type="date"
                className={selectClass}
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_initiatives.form.end_date")}
              <input type="date" className={selectClass} value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </label>
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t-[0.5px] border-subtle px-5 py-4">
          <Button variant="secondary" size="lg" onClick={onClose} type="button">
            {t("cancel")}
          </Button>
          <Button variant="primary" size="lg" type="submit" loading={isSubmitting} disabled={!name.trim()}>
            {initiative ? t("save") : t("thm_initiatives.create")}
          </Button>
        </div>
      </form>
    </ModalCore>
  );
});
