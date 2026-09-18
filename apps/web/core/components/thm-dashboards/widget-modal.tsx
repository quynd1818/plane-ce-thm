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
import type {
  TThmChartType,
  TThmDateField,
  TThmDateRange,
  TThmGroupBy,
  TThmMetric,
  TThmWidget,
  TThmWidgetFilters,
  TThmWidgetInput,
} from "@plane/types";
import { EModalWidth, ModalCore } from "@plane/ui";
// hooks
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
// local imports
import {
  CHART_TYPES,
  DATE_FIELDS,
  DATE_RANGES,
  GROUP_BYS,
  METRICS,
  PRIORITY_KEYS,
  STATE_GROUP_KEYS,
  needsGroupBy,
} from "./constants";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: TThmWidgetInput) => Promise<void>;
  widget?: TThmWidget | null;
  /** When the dashboard is pinned to a project, project filter is hidden. */
  lockedProjectId?: string | null;
};

const selectClass =
  "w-full rounded-md border border-strong bg-surface-1 px-2 py-1.5 text-13 text-secondary focus:border-transparent focus:ring-2 focus:ring-accent-strong focus:outline-none";

const EMPTY: TThmWidgetInput = {
  title: "",
  chart_type: "bar",
  metric: "count",
  group_by: "state",
  filters: {},
  width: 1,
  height: 1,
  config: {},
};

const multi = (event: React.ChangeEvent<HTMLSelectElement>) =>
  Array.from(event.target.selectedOptions).map((o) => o.value);

/** THM: create / edit a dashboard widget. */
export const ThmWidgetModal = observer(function ThmWidgetModal(props: Props) {
  const { isOpen, onClose, onSubmit, widget, lockedProjectId } = props;
  const { t } = useTranslation();
  const { joinedProjectIds, getProjectById } = useProject();
  const {
    workspace: { workspaceMemberIds, getWorkspaceMemberDetails },
  } = useMember();
  const [form, setForm] = useState<TThmWidgetInput>(EMPTY);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setForm(
      widget
        ? {
            title: widget.title,
            chart_type: widget.chart_type,
            metric: widget.metric,
            group_by: widget.group_by,
            filters: { ...widget.filters },
            width: widget.width,
            height: widget.height,
            config: { ...widget.config },
          }
        : { ...EMPTY, filters: {} }
    );
  }, [isOpen, widget]);

  const filters = form.filters ?? {};
  const setFilter = <K extends keyof TThmWidgetFilters>(key: K, value: TThmWidgetFilters[K] | undefined) =>
    setForm((prev) => {
      const next = { ...prev.filters };
      if (value === undefined || value === "" || (Array.isArray(value) && value.length === 0) || value === false)
        delete next[key];
      else next[key] = value;
      return { ...prev, filters: next };
    });

  const groupRequired = needsGroupBy(form.chart_type as TThmChartType);
  const valid = Boolean(form.title?.trim()) && (!groupRequired || Boolean(form.group_by));

  const submit = async () => {
    if (!valid) return;
    setIsSubmitting(true);
    try {
      await onSubmit({ ...form, title: form.title?.trim() });
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
    <ModalCore isOpen={isOpen} handleClose={onClose} width={EModalWidth.XXL}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <div className="space-y-4 p-5">
          <h3 className="text-18 font-medium text-secondary">
            {widget ? t("thm_dashboards.widget.edit") : t("thm_dashboards.widget.add")}
          </h3>

          <div>
            <label htmlFor="thm-widget-title" className="mb-1 block text-13 text-tertiary">
              {t("thm_dashboards.widget.title")}
            </label>
            <InputGroup size="xl">
              <Input
                size="xl"
                id="thm-widget-title"
                value={form.title ?? ""}
                onChange={(event) => setForm((p) => ({ ...p, title: event.target.value }))}
                placeholder={t("thm_dashboards.widget.title_placeholder")}
                maxLength={255}
              />
            </InputGroup>
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_dashboards.widget.chart_type")}
              <select
                className={selectClass}
                value={form.chart_type}
                onChange={(e) => {
                  const chart = e.target.value as TThmChartType;
                  setForm((p) => ({
                    ...p,
                    chart_type: chart,
                    group_by: needsGroupBy(chart) && !p.group_by ? "state" : p.group_by,
                  }));
                }}
              >
                {CHART_TYPES.map((c) => (
                  <option key={c} value={c}>
                    {t(`thm_dashboards.chart.${c}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_dashboards.widget.metric")}
              <select
                className={selectClass}
                value={form.metric}
                onChange={(e) => setForm((p) => ({ ...p, metric: e.target.value as TThmMetric }))}
              >
                {METRICS.map((m) => (
                  <option key={m} value={m}>
                    {t(`thm_dashboards.metric.${m}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_dashboards.widget.group_by")}
              <select
                className={selectClass}
                value={form.group_by ?? ""}
                onChange={(e) => setForm((p) => ({ ...p, group_by: e.target.value as TThmGroupBy }))}
              >
                {GROUP_BYS.filter((g) => g !== "" || !groupRequired).map((g) => (
                  <option key={g} value={g}>
                    {t(`thm_dashboards.group_by.${g || "none"}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_dashboards.widget.width")}
              <select
                className={selectClass}
                value={form.width}
                onChange={(e) => setForm((p) => ({ ...p, width: Number(e.target.value) as 1 | 2 | 3 }))}
              >
                {[1, 2, 3].map((w) => (
                  <option key={w} value={w}>
                    {t("thm_dashboards.widget.width_columns", { count: w })}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <h4 className="pt-2 text-13 font-medium text-secondary">{t("thm_dashboards.widget.filters")}</h4>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {!lockedProjectId && (
              <label className="flex flex-col gap-1 text-13 text-tertiary">
                {t("thm_dashboards.filters.projects")}
                <select
                  multiple
                  className={`${selectClass} h-28`}
                  value={filters.project_ids ?? []}
                  onChange={(e) => setFilter("project_ids", multi(e))}
                >
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
            )}
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_dashboards.filters.state_groups")}
              <select
                multiple
                className={`${selectClass} h-28`}
                value={filters.state_groups ?? []}
                onChange={(e) => setFilter("state_groups", multi(e))}
              >
                {STATE_GROUP_KEYS.map((g) => (
                  <option key={g} value={g}>
                    {t(`thm_dashboards.state_group.${g}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_dashboards.filters.priorities")}
              <select
                multiple
                className={`${selectClass} h-28`}
                value={filters.priorities ?? []}
                onChange={(e) => setFilter("priorities", multi(e))}
              >
                {PRIORITY_KEYS.map((p) => (
                  <option key={p} value={p}>
                    {t(`thm_dashboards.priority.${p}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_dashboards.filters.assignees")}
              <select
                multiple
                className={`${selectClass} h-28`}
                value={filters.assignee_ids ?? []}
                onChange={(e) => setFilter("assignee_ids", multi(e))}
              >
                {(workspaceMemberIds ?? []).map((id) => {
                  const m = getWorkspaceMemberDetails(id);
                  return m ? (
                    <option key={id} value={id}>
                      {m.member.display_name || m.member.email}
                    </option>
                  ) : null;
                })}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-13 text-tertiary">
              {t("thm_dashboards.filters.date_range")}
              <select
                className={selectClass}
                value={filters.date_range ?? ""}
                onChange={(e) => setFilter("date_range", e.target.value as TThmDateRange)}
              >
                {DATE_RANGES.map((r) => (
                  <option key={r} value={r}>
                    {t(`thm_dashboards.date_range.${r || "any"}`)}
                  </option>
                ))}
              </select>
              <select
                className={selectClass}
                value={filters.date_field ?? "created_at"}
                disabled={!filters.date_range}
                aria-label={t("thm_dashboards.filters.date_field")}
                onChange={(e) => setFilter("date_field", e.target.value as TThmDateField)}
              >
                {DATE_FIELDS.map((f) => (
                  <option key={f} value={f}>
                    {t(`thm_dashboards.date_field.${f}`)}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex flex-col gap-2 pt-5 text-13 text-secondary">
              <label className="flex items-center gap-2">
                <Checkbox
                  checked={Boolean(filters.overdue_only)}
                  onCheckedChange={(c) => setFilter("overdue_only", c === true)}
                  aria-label={t("thm_dashboards.filters.overdue_only")}
                />
                {t("thm_dashboards.filters.overdue_only")}
              </label>
              <label className="flex items-center gap-2">
                <Checkbox
                  checked={Boolean(filters.unassigned_only)}
                  onCheckedChange={(c) => setFilter("unassigned_only", c === true)}
                  aria-label={t("thm_dashboards.filters.unassigned_only")}
                />
                {t("thm_dashboards.filters.unassigned_only")}
              </label>
              <label className="flex items-center gap-2">
                <Checkbox
                  checked={filters.include_sub_issues !== false}
                  onCheckedChange={(c) =>
                    setForm((p) => ({ ...p, filters: { ...p.filters, include_sub_issues: c === true } }))
                  }
                  aria-label={t("thm_dashboards.filters.include_sub_issues")}
                />
                {t("thm_dashboards.filters.include_sub_issues")}
              </label>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 border-t-[0.5px] border-subtle px-5 py-4">
          <Button variant="secondary" size="lg" onClick={onClose} type="button">
            {t("cancel")}
          </Button>
          <Button variant="primary" size="lg" type="submit" loading={isSubmitting} disabled={!valid}>
            {widget ? t("save") : t("thm_dashboards.widget.add")}
          </Button>
        </div>
      </form>
    </ModalCore>
  );
});
