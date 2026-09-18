/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "@plane/i18n";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { cn } from "@plane/utils";
import { workLogService, type TWorkLog, type TWorkLogReviewAction } from "@/services/issue/worklog.service";

type Props = {
  workspaceSlug: string;
  projectId: string;
  log: Pick<TWorkLog, "id" | "issue" | "status" | "is_timer" | "ended_at">;
  onReviewed: (log: TWorkLog) => void | Promise<void>;
  size?: "sm" | "md";
};

/**
 * THM: approve / reject / reopen buttons for approvers. Reject asks for a
 * note inline (the server refuses a rejection without one).
 */
export function WorklogReviewActions({ workspaceSlug, projectId, log, onReviewed, size = "sm" }: Props) {
  const { t } = useTranslation();
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const noteRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (rejecting) noteRef.current?.focus();
  }, [rejecting]);

  const isRunningTimer = log.is_timer && !log.ended_at;
  if (isRunningTimer) return null;

  const run = async (action: TWorkLogReviewAction) => {
    if (action === "reject" && !note.trim()) return;
    setBusy(true);
    try {
      const updated = await workLogService.review(workspaceSlug, projectId, log.issue, log.id, {
        action,
        note: action === "reject" ? note.trim() : undefined,
      });
      setRejecting(false);
      setNote("");
      await onReviewed(updated);
    } catch (error) {
      const message = (error as { error?: string })?.error ?? t("worklog_review.review_failed");
      setToast({ title: t("common.error.label"), type: TOAST_TYPE.ERROR, message });
    } finally {
      setBusy(false);
    }
  };

  const btn = cn(
    "rounded border border-subtle-1 px-2 font-medium disabled:opacity-50",
    size === "sm" ? "text-caption h-6" : "h-7 text-body-xs-medium"
  );

  if (rejecting) {
    return (
      <div className="flex min-w-0 grow items-center gap-2">
        <input
          className={cn(
            "min-w-0 grow rounded border border-subtle-1 px-2",
            size === "sm" ? "text-caption h-6" : "h-7 text-body-xs-regular"
          )}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder={t("worklog_review.reject_note_placeholder")}
          aria-label={t("worklog_review.reject_note_placeholder")}
          ref={noteRef}
          onKeyDown={(event) => {
            if (event.key === "Enter") void run("reject");
            if (event.key === "Escape") setRejecting(false);
          }}
        />
        <button
          type="button"
          className={cn(btn, "text-danger-primary")}
          disabled={busy || !note.trim()}
          onClick={() => void run("reject")}
        >
          {t("worklog_review.actions.reject")}
        </button>
        <button type="button" className={btn} disabled={busy} onClick={() => setRejecting(false)}>
          {t("common.cancel")}
        </button>
      </div>
    );
  }

  return (
    <div className="flex shrink-0 items-center gap-1.5">
      {log.status !== "approved" && (
        <button
          type="button"
          className={cn(btn, "text-success-primary")}
          disabled={busy}
          onClick={() => void run("approve")}
        >
          {t("worklog_review.actions.approve")}
        </button>
      )}
      {log.status !== "rejected" && (
        <button
          type="button"
          className={cn(btn, "text-danger-primary")}
          disabled={busy}
          onClick={() => setRejecting(true)}
        >
          {t("worklog_review.actions.reject")}
        </button>
      )}
      {log.status !== "submitted" && (
        <button type="button" className={cn(btn, "text-secondary")} disabled={busy} onClick={() => void run("reopen")}>
          {t("worklog_review.actions.reopen")}
        </button>
      )}
    </div>
  );
}
