/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { Checkbox } from "@makeplane/propel/components/checkbox";
import { Input, InputGroup } from "@makeplane/propel/components/input";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { ISearchIssueResponse } from "@plane/types";
import { ModalCore } from "@plane/ui";
// services
import { ProjectService } from "@/services/project/project.service";

const projectService = new ProjectService();

type Props = {
  isOpen: boolean;
  workspaceSlug: string;
  projectId: string;
  epicId: string;
  onClose: () => void;
  onAttach: (issueIds: string[]) => Promise<void>;
};

/** THM: pick work items of the project to put under an epic. */
export const ThmAttachWorkItemsModal = observer(function ThmAttachWorkItemsModal(props: Props) {
  const { isOpen, workspaceSlug, projectId, epicId, onClose, onAttach } = props;
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ISearchIssueResponse[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setQuery("");
    setSelected([]);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setIsSearching(true);
    const timer = window.setTimeout(async () => {
      try {
        const rows = await projectService.projectIssuesSearch(workspaceSlug, projectId, {
          search: query,
          sub_issue: true,
          issue_id: epicId,
          workspace_search: false,
        });
        // the search endpoint returns epics too; an epic cannot hold another epic
        if (!cancelled) setResults(rows.filter((r) => r.id !== epicId));
      } catch {
        if (!cancelled) setResults([]);
      } finally {
        if (!cancelled) setIsSearching(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [isOpen, query, workspaceSlug, projectId, epicId]);

  const toggle = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const submit = async () => {
    if (selected.length === 0) return;
    setIsSubmitting(true);
    try {
      await onAttach(selected);
      onClose();
    } catch (error) {
      const data = (error as { data?: { issue_ids?: string[] } })?.data;
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("toast.error"),
        message: data?.issue_ids?.[0] ?? t("something_went_wrong"),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={onClose}>
      <div className="space-y-3 p-5">
        <h3 className="text-18 font-medium text-secondary">{t("thm_epics.attach.title")}</h3>
        <InputGroup size="xl">
          <Input
            size="xl"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("thm_epics.attach.search_placeholder")}
            aria-label={t("thm_epics.attach.search_placeholder")}
          />
        </InputGroup>
        <div className="max-h-72 overflow-y-auto rounded-md border border-subtle">
          {results.length === 0 && (
            <p className="px-3 py-4 text-13 text-tertiary">
              {isSearching ? t("loading") : t("thm_epics.attach.empty")}
            </p>
          )}
          {results.map((row) => (
            <label
              key={row.id}
              className="flex cursor-pointer items-center gap-2 border-b border-subtle px-3 py-2 text-13 last:border-b-0 hover:bg-layer-transparent-hover"
            >
              <Checkbox
                checked={selected.includes(row.id)}
                onCheckedChange={() => toggle(row.id)}
                aria-label={row.name}
              />
              <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: row.state__color }} />
              <span className="shrink-0 text-tertiary">
                {row.project__identifier}-{row.sequence_id}
              </span>
              <span className="truncate">{row.name}</span>
            </label>
          ))}
        </div>
      </div>
      <div className="flex items-center justify-end gap-2 border-t-[0.5px] border-subtle px-5 py-4">
        <Button variant="secondary" size="lg" onClick={onClose} type="button">
          {t("cancel")}
        </Button>
        <Button
          variant="primary"
          size="lg"
          onClick={() => void submit()}
          loading={isSubmitting}
          disabled={selected.length === 0}
        >
          {t("thm_epics.attach.submit", { count: selected.length })}
        </Button>
      </div>
    </ModalCore>
  );
});
