import { observer } from "mobx-react";
import { useEffect, useState } from "react";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { useProject } from "@/hooks/store/use-project";
import { workLogService, type TWorkLogReport } from "@/services/issue/worklog.service";
import type { Route } from "./+types/page";

function WorklogsSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { currentProjectDetails } = useProject();
  const [report, setReport] = useState<TWorkLogReport>();
  const [startedAfter, setStartedAfter] = useState("");
  const [startedBefore, setStartedBefore] = useState("");
  const [issueId, setIssueId] = useState("");
  const [userId, setUserId] = useState("");

  const loadReport = async () => {
    const nextReport = await workLogService.getProjectReport(workspaceSlug, projectId, {
      issue_id: issueId || undefined,
      user_id: userId || undefined,
      started_after: startedAfter || undefined,
      started_before: startedBefore || undefined,
    });
    setReport(nextReport);
  };

  useEffect(() => {
    void loadReport();
  }, [workspaceSlug, projectId]);

  const exportReport = async () => {
    const blob = await workLogService.exportProjectReport(workspaceSlug, projectId, {
      issue_id: issueId || undefined,
      user_id: userId || undefined,
      started_after: startedAfter || undefined,
      started_before: startedBefore || undefined,
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "plane-worklogs.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <SettingsContentWrapper>
      <PageHead title={currentProjectDetails?.name ? `${currentProjectDetails.name} - Worklogs` : "Worklogs"} />
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">Worklogs</h1>
            <p className="text-sm text-tertiary">Review and export time tracked in this project.</p>
          </div>
          <button type="button" className="rounded bg-accent-primary px-3 py-2 text-sm text-on-color" onClick={() => void exportReport()}>
            Export CSV
          </button>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm flex flex-col gap-1">
            Work item ID
            <input value={issueId} onChange={(event) => setIssueId(event.target.value)} />
          </label>
          <label className="text-sm flex flex-col gap-1">
            User ID
            <input value={userId} onChange={(event) => setUserId(event.target.value)} />
          </label>
          <label className="text-sm flex flex-col gap-1">
            From
            <input type="date" value={startedAfter} onChange={(event) => setStartedAfter(event.target.value)} />
          </label>
          <label className="text-sm flex flex-col gap-1">
            To
            <input type="date" value={startedBefore} onChange={(event) => setStartedBefore(event.target.value)} />
          </label>
          <button type="button" className="rounded border border-subtle-1 px-3 py-2 text-sm" onClick={() => void loadReport()}>
            Apply
          </button>
        </div>
        <div className="rounded border border-subtle">
          <div className="text-xs grid grid-cols-[1.4fr_1fr_1fr_120px] gap-3 border-b border-subtle px-4 py-3 font-medium text-tertiary">
            <span>Work item</span>
            <span>User</span>
            <span>Description</span>
            <span>Duration</span>
          </div>
          {report?.results.map((worklog) => (
            <div key={worklog.id} className="text-sm grid grid-cols-[1.4fr_1fr_1fr_120px] gap-3 px-4 py-3">
              <span>{worklog.issue_name}</span>
              <span>{worklog.user_email}</span>
              <span>{worklog.description || "-"}</span>
              <span>{(worklog.duration_seconds / 3600).toFixed(2)}h</span>
            </div>
          ))}
          <div className="text-sm border-t border-subtle px-4 py-3 font-medium">
            Total: {((report?.total_seconds ?? 0) / 3600).toFixed(2)}h
          </div>
        </div>
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(WorklogsSettingsPage);
