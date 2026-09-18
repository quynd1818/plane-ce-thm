/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * Project Settings → Worklogs. Report + CSV export, and (THM) the approval
 * queue and approver list when the project requires worklog sign-off.
 */

import { observer } from "mobx-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "@plane/i18n";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
// components
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { WorklogReviewActions } from "@/components/worklog/review-actions";
import { WorklogStatusBadge } from "@/components/worklog/status-badge";
import { useWorklogApproval } from "@/components/worklog/use-worklog-approval";
// hooks
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
// services
import {
  workLogService,
  type TWorkLogPending,
  type TWorkLogReport,
  type TWorkLogReportParams,
  type TWorkLogStatusFilter,
} from "@/services/issue/worklog.service";
import type { Route } from "./+types/page";

const STATUS_FILTERS: TWorkLogStatusFilter[] = ["approved", "submitted", "rejected", "all"];

const inputClass =
  "rounded-md border border-strong bg-surface-1 px-3 py-1.5 text-13 text-secondary focus:border-transparent focus:ring-2 focus:ring-accent-strong focus:outline-none";

const hours = (seconds: number | undefined) => ((seconds ?? 0) / 3600).toFixed(2);

function WorklogsSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { t } = useTranslation();
  // store hooks
  const { currentProjectDetails, updateProject } = useProject();
  const {
    project: { getProjectMemberIds, getProjectMemberDetails, fetchProjectMembers },
  } = useMember();
  const { isApprovalEnabled, isApprover, isProjectAdmin } = useWorklogApproval(workspaceSlug, projectId);
  // state
  const [report, setReport] = useState<TWorkLogReport>();
  const [pending, setPending] = useState<TWorkLogPending>();
  const [startedAfter, setStartedAfter] = useState("");
  const [startedBefore, setStartedBefore] = useState("");
  const [issueId, setIssueId] = useState("");
  const [userId, setUserId] = useState("");
  const [status, setStatus] = useState<TWorkLogStatusFilter>("approved");
  const [savingApprovers, setSavingApprovers] = useState(false);
  // derived values
  const members = (getProjectMemberIds(projectId, false) ?? [])
    .map((id) => getProjectMemberDetails(id, projectId))
    .filter((m): m is NonNullable<typeof m> => !!m)
    .map((m) => ({ id: m.member.id, name: m.member.display_name || m.member.email }));
  const approverIds = currentProjectDetails?.worklog_approver_ids ?? [];

  // filters are only applied on "Apply" (or when approval is toggled), not on every keystroke
  const [applied, setApplied] = useState<TWorkLogReportParams>({});
  const reportParams = useCallback(
    (): TWorkLogReportParams => ({
      ...applied,
      status: isApprovalEnabled ? (applied.status ?? "approved") : undefined,
    }),
    [applied, isApprovalEnabled]
  );
  const applyFilters = () =>
    setApplied({
      issue_id: issueId || undefined,
      user_id: userId || undefined,
      started_after: startedAfter || undefined,
      started_before: startedBefore || undefined,
      status,
    });

  const loadReport = useCallback(async () => {
    try {
      setReport(await workLogService.getProjectReport(workspaceSlug, projectId, reportParams()));
    } catch {
      setToast({ title: t("common.error.label"), type: TOAST_TYPE.ERROR, message: t("worklog_review.load_failed") });
    }
  }, [workspaceSlug, projectId, reportParams, t]);

  const loadPending = useCallback(async () => {
    if (!isApprovalEnabled || !isApprover) return;
    try {
      setPending(await workLogService.getPending(workspaceSlug, projectId));
    } catch {
      setToast({ title: t("common.error.label"), type: TOAST_TYPE.ERROR, message: t("worklog_review.load_failed") });
    }
  }, [workspaceSlug, projectId, isApprovalEnabled, isApprover, t]);

  useEffect(() => {
    void loadReport();
  }, [loadReport]);

  useEffect(() => {
    void loadPending();
  }, [loadPending]);

  useEffect(() => {
    if (isProjectAdmin) void fetchProjectMembers(workspaceSlug, projectId);
  }, [workspaceSlug, projectId, isProjectAdmin, fetchProjectMembers]);

  const exportReport = async () => {
    const blob = await workLogService.exportProjectReport(workspaceSlug, projectId, reportParams());
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "plane-worklogs.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const saveApprovers = async (ids: string[]) => {
    setSavingApprovers(true);
    try {
      await updateProject(workspaceSlug, projectId, { worklog_approver_ids: ids });
    } catch {
      setToast({ title: t("common.error.label"), type: TOAST_TYPE.ERROR, message: t("worklog_review.save_failed") });
    } finally {
      setSavingApprovers(false);
    }
  };

  const afterReview = async () => {
    await Promise.all([loadPending(), loadReport()]);
  };

  return (
    <SettingsContentWrapper>
      <PageHead title={currentProjectDetails?.name ? `${currentProjectDetails.name} - Worklogs` : "Worklogs"} />
      <div className="flex flex-col gap-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">{t("common.worklogs")}</h1>
            <p className="text-sm text-tertiary">{t("worklog_review.page_description")}</p>
          </div>
          <button
            type="button"
            className="text-sm rounded bg-accent-primary px-3 py-2 text-on-color"
            onClick={() => void exportReport()}
          >
            Export CSV
          </button>
        </div>

        {isApprovalEnabled && isProjectAdmin && (
          <section className="flex flex-col gap-2">
            <h2 className="text-base font-medium">{t("worklog_review.approvers_title")}</h2>
            <p className="text-sm text-tertiary">{t("worklog_review.approvers_description")}</p>
            <select
              multiple
              className={`${inputClass} h-28 max-w-md`}
              value={approverIds}
              disabled={savingApprovers}
              aria-label={t("worklog_review.approvers_title")}
              onChange={(e) => void saveApprovers(Array.from(e.target.selectedOptions).map((o) => o.value))}
            >
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </section>
        )}

        {isApprovalEnabled && isApprover && (
          <section className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-medium">
                {t("worklog_review.pending_title")}
                <span className="text-caption ml-2 rounded-full bg-warning-subtle px-2 text-warning-primary">
                  {pending?.count ?? 0}
                </span>
              </h2>
              <span className="text-sm text-tertiary">{hours(pending?.total_seconds)}h</span>
            </div>
            <div className="rounded border border-subtle">
              {(pending?.results ?? []).length === 0 && (
                <p className="text-sm px-4 py-3 text-tertiary">{t("worklog_review.pending_empty")}</p>
              )}
              {pending?.results.map((log) => (
                <div
                  key={log.id}
                  className="text-sm flex flex-wrap items-center gap-3 border-b border-subtle px-4 py-3 last:border-b-0"
                >
                  <span className="w-48 truncate font-medium">
                    {currentProjectDetails?.identifier}-{log.issue_sequence_id} {log.issue_name}
                  </span>
                  <span className="w-40 truncate text-tertiary">
                    {log.user_detail?.display_name ?? log.user_detail?.email ?? log.user}
                  </span>
                  <span className="min-w-0 grow truncate">{log.description || "-"}</span>
                  <span className="w-16 shrink-0 text-right">{hours(log.duration_seconds)}h</span>
                  <WorklogReviewActions
                    workspaceSlug={workspaceSlug}
                    projectId={projectId}
                    log={log}
                    onReviewed={afterReview}
                    size="md"
                  />
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="flex flex-col gap-3">
          <h2 className="text-base font-medium">{t("worklog_review.report_title")}</h2>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm flex flex-col gap-1">
              Work item ID
              <input className={inputClass} value={issueId} onChange={(event) => setIssueId(event.target.value)} />
            </label>
            <label className="text-sm flex flex-col gap-1">
              User ID
              <input className={inputClass} value={userId} onChange={(event) => setUserId(event.target.value)} />
            </label>
            <label className="text-sm flex flex-col gap-1">
              From
              <input
                className={inputClass}
                type="date"
                value={startedAfter}
                onChange={(event) => setStartedAfter(event.target.value)}
              />
            </label>
            <label className="text-sm flex flex-col gap-1">
              To
              <input
                className={inputClass}
                type="date"
                value={startedBefore}
                onChange={(event) => setStartedBefore(event.target.value)}
              />
            </label>
            {isApprovalEnabled && (
              <label className="text-sm flex flex-col gap-1">
                {t("worklog_review.status_label")}
                <select
                  className={inputClass}
                  value={status}
                  onChange={(event) => setStatus(event.target.value as TWorkLogStatusFilter)}
                >
                  {STATUS_FILTERS.map((value) => (
                    <option key={value} value={value}>
                      {value === "all" ? t("common.all") : t(`worklog_review.status.${value}`)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <button type="button" className="text-sm rounded border border-subtle-1 px-3 py-2" onClick={applyFilters}>
              Apply
            </button>
          </div>
          <div className="rounded border border-subtle">
            <div className="text-xs grid grid-cols-[1.4fr_1fr_1fr_120px_120px] gap-3 border-b border-subtle px-4 py-3 font-medium text-tertiary">
              <span>Work item</span>
              <span>User</span>
              <span>Description</span>
              <span>{t("worklog_review.status_label")}</span>
              <span>Duration</span>
            </div>
            {report?.results.map((worklog) => (
              <div key={worklog.id} className="text-sm grid grid-cols-[1.4fr_1fr_1fr_120px_120px] gap-3 px-4 py-3">
                <span className="truncate">{worklog.issue_name}</span>
                <span className="truncate">{worklog.user_email}</span>
                <span className="truncate">{worklog.description || "-"}</span>
                <span>{isApprovalEnabled ? <WorklogStatusBadge log={worklog} /> : "-"}</span>
                <span>{hours(worklog.duration_seconds)}h</span>
              </div>
            ))}
            <div className="text-sm border-t border-subtle px-4 py-3 font-medium">
              Total: {hours(report?.total_seconds)}h
            </div>
          </div>
        </section>
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(WorklogsSettingsPage);
