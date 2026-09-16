import { useCallback, useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import { setToast, TOAST_TYPE } from "@plane/propel/toast";
import { workLogService, type TWorkLog } from "@/services/issue/worklog.service";

type Props = { workspaceSlug: string; projectId: string; issueId: string };

const formatDuration = (seconds: number) => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
};

const getDurationSeconds = (log: TWorkLog, currentTime: number) => {
  if (!log.is_timer || log.ended_at) return log.duration_seconds;
  return Math.max(1, Math.floor((currentTime - new Date(log.started_at).getTime()) / 1000));
};

export const IssueWorkLogPanel = observer(function IssueWorkLogPanel({ workspaceSlug, projectId, issueId }: Props) {
  const { t } = useTranslation();
  const [logs, setLogs] = useState<TWorkLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [duration, setDuration] = useState("30");
  const [description, setDescription] = useState("");
  const [editingLog, setEditingLog] = useState<TWorkLog | null>(null);
  const [editDuration, setEditDuration] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [currentTime, setCurrentTime] = useState(() => Date.now());

  const activeTimer = useMemo(() => logs.find((log) => log.is_timer && !log.ended_at), [logs]);
  const totalSeconds = useMemo(
    () => logs.reduce((total, log) => total + getDurationSeconds(log, currentTime), 0),
    [logs, currentTime]
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setLogs(await workLogService.list(workspaceSlug, projectId, issueId));
    } catch {
      setToast({ title: t("common.error.label"), type: TOAST_TYPE.ERROR, message: "Unable to load worklogs." });
    } finally {
      setLoading(false);
    }
  }, [workspaceSlug, projectId, issueId, t]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!activeTimer) return;
    const interval = window.setInterval(() => setCurrentTime(Date.now()), 30_000);
    return () => window.clearInterval(interval);
  }, [activeTimer]);

  const addLog = async () => {
    const minutes = Number(duration);
    if (!Number.isFinite(minutes) || minutes <= 0) return;
    const startedAt = new Date(Date.now() - minutes * 60 * 1000);
    try {
      await workLogService.create(workspaceSlug, projectId, issueId, {
        duration_seconds: Math.round(minutes * 60),
        started_at: startedAt.toISOString(),
        ended_at: new Date().toISOString(),
        description,
      });
      setDescription("");
      await refresh();
    } catch {
      setToast({ title: t("common.error.label"), type: TOAST_TYPE.ERROR, message: "Unable to save worklog." });
    }
  };

  const toggleTimer = async () => {
    try {
      if (activeTimer) await workLogService.stopTimer(workspaceSlug, projectId, issueId);
      else await workLogService.startTimer(workspaceSlug, projectId, issueId);
      await refresh();
    } catch {
      setToast({ title: t("common.error.label"), type: TOAST_TYPE.ERROR, message: "Unable to update timer." });
    }
  };

  const deleteLog = async (id: string) => {
    if (!window.confirm("Delete this worklog?")) return;
    try {
      await workLogService.deleteLog(workspaceSlug, projectId, issueId, id);
      await refresh();
    } catch {
      setToast({ title: t("common.error.label"), type: TOAST_TYPE.ERROR, message: "Unable to delete worklog." });
    }
  };

  const beginEdit = (log: TWorkLog) => {
    setEditingLog(log);
    setEditDuration(String(Math.max(1, Math.round(log.duration_seconds / 60))));
    setEditDescription(log.description);
  };

  const updateLog = async () => {
    if (!editingLog) return;
    const minutes = Number(editDuration);
    if (!Number.isFinite(minutes) || minutes <= 0) return;
    try {
      await workLogService.update(workspaceSlug, projectId, issueId, editingLog.id, {
        duration_seconds: Math.round(minutes * 60),
        description: editDescription,
      });
      setEditingLog(null);
      await refresh();
    } catch {
      setToast({ title: t("common.error.label"), type: TOAST_TYPE.ERROR, message: "Unable to update worklog." });
    }
  };

  return (
    <section className="mt-5 border-t border-subtle-1 pt-4">
      <div className="flex items-center justify-between">
        <h5 className="text-body-xs-medium">{t("common.worklogs")}</h5>
        <span className="text-caption text-secondary">{formatDuration(totalSeconds)}</span>
      </div>
      <div className="mt-3 space-y-2">
        <button type="button" className="h-7 w-full rounded border border-subtle-1 text-body-xs-medium" onClick={toggleTimer}>
          {activeTimer ? "Stop timer" : "Start timer"}
        </button>
        <div className="flex gap-2">
          <input
            className="h-7 w-16 rounded border border-subtle-1 px-2 text-body-xs-regular"
            type="number"
            min="1"
            value={duration}
            onChange={(event) => setDuration(event.target.value)}
            aria-label="Minutes"
          />
          <input
            className="h-7 min-w-0 grow rounded border border-subtle-1 px-2 text-body-xs-regular"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="What did you work on?"
          />
          <button type="button" className="h-7 rounded bg-accent-primary px-2 text-body-xs-medium text-on-color" onClick={addLog}>
            Add
          </button>
        </div>
        {!loading && logs.length === 0 && <p className="text-caption text-secondary">{t("common.no_worklogs")}</p>}
        {logs.slice(0, 5).map((log) => (
          <div key={log.id} className="space-y-1 text-caption">
            <div className="flex items-center justify-between">
              <span className="truncate">{log.description || (log.is_timer ? "Timer" : "Worklog")}</span>
              <span className="ml-2 shrink-0">{formatDuration(getDurationSeconds(log, currentTime))}</span>
              {!log.is_timer && (
                <div className="ml-2 flex shrink-0 gap-2">
                  <button type="button" className="text-secondary" onClick={() => beginEdit(log)}>
                    Edit
                  </button>
                  <button type="button" className="text-danger-primary" onClick={() => void deleteLog(log.id)}>
                    Delete
                  </button>
                </div>
              )}
            </div>
            {editingLog?.id === log.id && (
              <div className="flex gap-2">
                <input
                  className="h-7 w-16 rounded border border-subtle-1 px-2 text-body-xs-regular"
                  type="number"
                  min="1"
                  value={editDuration}
                  onChange={(event) => setEditDuration(event.target.value)}
                  aria-label="Edit minutes"
                />
                <input
                  className="h-7 min-w-0 grow rounded border border-subtle-1 px-2 text-body-xs-regular"
                  value={editDescription}
                  onChange={(event) => setEditDescription(event.target.value)}
                  aria-label="Edit worklog description"
                />
                <button type="button" className="text-accent-primary" onClick={() => void updateLog()}>
                  Save
                </button>
                <button type="button" className="text-secondary" onClick={() => setEditingLog(null)}>
                  Cancel
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
});
