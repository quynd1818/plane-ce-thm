/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * THM: Project Settings → Workflow. Rules that restrict who may move a work
 * item into a state (by project role and/or named approvers).
 */

import { observer } from "mobx-react";
import { useState } from "react";
import useSWR from "swr";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { StateGroupIcon } from "@plane/propel/icons";
import { EUserPermissions } from "@plane/constants";
// components
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
// hooks
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
import { useProjectState } from "@/hooks/store/use-project-state";
import { useWorkflowRules } from "@/hooks/store/use-workflow-rules";
import { useUserPermissions } from "@/hooks/store/user";
// services
import type { TWorkflowRole, TWorkflowRule } from "@/services/project/workflow.service";
import type { Route } from "./+types/page";

const ROLE_OPTIONS: { value: TWorkflowRole; label: string }[] = [
  { value: 20, label: "Admin" },
  { value: 15, label: "Member" },
  { value: 5, label: "Guest" },
];

const ANY_STATE = "__any__";

const inputClass =
  "w-full rounded-md border border-strong bg-surface-1 px-3 py-1.5 text-13 text-secondary focus:border-transparent focus:ring-2 focus:ring-accent-strong focus:outline-none";

function WorkflowSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { t } = useTranslation();
  // store hooks
  const { currentProjectDetails, updateProject } = useProject();
  const { getProjectStates, getStateById } = useProjectState();
  const { getProjectRules, fetchRules, createRule, updateRule, deleteRule } = useWorkflowRules();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const {
    project: { getProjectMemberIds, getProjectMemberDetails },
  } = useMember();
  // form state
  const [fromState, setFromState] = useState<string>(ANY_STATE);
  const [toState, setToState] = useState<string>("");
  const [roles, setRoles] = useState<TWorkflowRole[]>([20]);
  const [approvers, setApprovers] = useState<string[]>([]);
  const [description, setDescription] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  // derived values
  const isAdmin = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId) === EUserPermissions.ADMIN;
  const states = getProjectStates(projectId) ?? [];
  const rules = getProjectRules(projectId);
  const members = (getProjectMemberIds(projectId, false) ?? [])
    .map((id) => getProjectMemberDetails(id, projectId))
    .filter((m): m is NonNullable<typeof m> => !!m)
    .map((m) => ({ id: m.member.id, name: m.member.display_name || m.member.email }));
  const isEnabled = !!currentProjectDetails?.is_workflow_enabled;

  useSWR(`PROJECT_WORKFLOW_RULES_SETTINGS_${projectId}`, () => fetchRules(workspaceSlug, projectId, true));

  const resetForm = () => {
    setFromState(ANY_STATE);
    setToState("");
    setRoles([20]);
    setApprovers([]);
    setDescription("");
  };

  const handleCreate = async () => {
    if (!toState) return;
    setIsSaving(true);
    try {
      await createRule(workspaceSlug, projectId, {
        from_state: fromState === ANY_STATE ? null : fromState,
        to_state: toState,
        allowed_roles: roles,
        approver_ids: approvers,
        description,
        is_active: true,
      });
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Đã thêm quy tắc",
        message: "Quy tắc chuyển trạng thái đã được lưu.",
      });
      resetForm();
    } catch (error: unknown) {
      const err = error as Record<string, unknown> | undefined;
      const message =
        (typeof err?.non_field_errors === "object" && Array.isArray(err?.non_field_errors)
          ? String(err.non_field_errors[0])
          : undefined) ??
        (err ? Object.values(err).flat().map(String).join(" ") : "") ??
        "Không lưu được quy tắc.";
      setToast({ type: TOAST_TYPE.ERROR, title: "Lỗi", message });
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleActive = async (rule: TWorkflowRule) => {
    try {
      await updateRule(workspaceSlug, projectId, rule.id, { is_active: !rule.is_active });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Lỗi", message: "Không cập nhật được quy tắc." });
    }
  };

  const handleDelete = async (rule: TWorkflowRule) => {
    try {
      await deleteRule(workspaceSlug, projectId, rule.id);
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Đã xoá", message: "Quy tắc đã được xoá." });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Lỗi", message: "Không xoá được quy tắc." });
    }
  };

  const handleToggleFeature = async () => {
    const promise = updateProject(workspaceSlug, projectId, { is_workflow_enabled: !isEnabled });
    try {
      await promise;
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Lỗi", message: "Không đổi được cài đặt dự án." });
    }
  };

  const stateName = (id: string | null) => (id ? (getStateById(id)?.name ?? "?") : "Bất kỳ");
  const memberName = (id: string) => members.find((m) => m.id === id)?.name ?? id.slice(0, 8);

  return (
    <SettingsContentWrapper>
      <PageHead
        title={
          currentProjectDetails?.name
            ? `${currentProjectDetails.name} - ${t("project_settings.workflow.label")}`
            : "Workflow"
        }
      />
      <div className="flex flex-col gap-8">
        <SettingsHeading
          title={t("workflow")}
          description={t("workflow_description")}
          control={
            isAdmin ? (
              <Button
                variant={isEnabled ? "secondary" : "primary"}
                size="sm"
                onClick={() => void handleToggleFeature()}
              >
                {isEnabled ? "Tắt quy trình" : "Bật quy trình"}
              </Button>
            ) : undefined
          }
        />
        {!isEnabled && (
          <div className="rounded-lg border border-warning-strong bg-warning-subtle px-4 py-3 text-13 text-secondary">
            Quy trình đang <b>tắt</b> cho dự án này: các quy tắc bên dưới được lưu nhưng chưa được áp dụng. Bật để bắt
            đầu chặn chuyển trạng thái.
          </div>
        )}

        {/* Existing rules */}
        <div className="rounded-lg border border-subtle">
          <div className="grid grid-cols-[1fr_1fr_1.2fr_1.2fr_1.5fr_auto] gap-3 border-b border-subtle px-4 py-3 text-11 font-medium text-tertiary uppercase">
            <span>Từ trạng thái</span>
            <span>Sang trạng thái</span>
            <span>Vai trò được phép</span>
            <span>Người duyệt</span>
            <span>Ghi chú</span>
            <span />
          </div>
          {rules.length === 0 && (
            <div className="px-4 py-6 text-13 text-tertiary">
              Chưa có quy tắc nào. Không có quy tắc = ai cũng chuyển được trạng thái như Plane mặc định.
            </div>
          )}
          {rules.map((rule) => (
            <div
              key={rule.id}
              className={`grid grid-cols-[1fr_1fr_1.2fr_1.2fr_1.5fr_auto] items-center gap-3 border-b border-subtle px-4 py-3 text-13 last:border-b-0 ${rule.is_active ? "" : "opacity-50"}`}
            >
              <span className="flex items-center gap-1.5">
                {rule.from_state && (
                  <StateGroupIcon
                    stateGroup={getStateById(rule.from_state)?.group ?? "backlog"}
                    color={getStateById(rule.from_state)?.color}
                    className="size-3.5"
                  />
                )}
                {stateName(rule.from_state)}
              </span>
              <span className="flex items-center gap-1.5">
                <StateGroupIcon
                  stateGroup={getStateById(rule.to_state)?.group ?? "backlog"}
                  color={getStateById(rule.to_state)?.color}
                  className="size-3.5"
                />
                {stateName(rule.to_state)}
              </span>
              <span>
                {rule.allowed_roles.map((r) => ROLE_OPTIONS.find((o) => o.value === r)?.label ?? r).join(", ") || "—"}
              </span>
              <span className="truncate">{rule.approver_ids.map(memberName).join(", ") || "—"}</span>
              <span className="truncate text-tertiary">{rule.description || "—"}</span>
              {isAdmin ? (
                <span className="flex items-center gap-1">
                  <Button variant="ghost" size="sm" onClick={() => void handleToggleActive(rule)}>
                    {rule.is_active ? "Tạm tắt" : "Bật"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-danger-primary"
                    onClick={() => void handleDelete(rule)}
                  >
                    Xoá
                  </Button>
                </span>
              ) : (
                <span />
              )}
            </div>
          ))}
        </div>

        {/* New rule */}
        {isAdmin && (
          <div className="flex flex-col gap-4 rounded-lg border border-subtle bg-layer-1 p-4">
            <h3 className="text-14 font-medium text-primary">Thêm quy tắc</h3>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <label className="flex flex-col gap-1 text-13 text-tertiary">
                Từ trạng thái
                <select className={inputClass} value={fromState} onChange={(e) => setFromState(e.target.value)}>
                  <option value={ANY_STATE}>Bất kỳ</option>
                  {states.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-13 text-tertiary">
                Sang trạng thái <span className="text-danger-primary">*</span>
                <select className={inputClass} value={toState} onChange={(e) => setToState(e.target.value)}>
                  <option value="">— chọn —</option>
                  {states
                    .filter((s) => s.id !== fromState)
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                </select>
              </label>
              <div className="flex flex-col gap-1 text-13 text-tertiary">
                Vai trò được phép
                <div className="flex gap-4 pt-1">
                  {ROLE_OPTIONS.map((opt) => (
                    <label key={opt.value} className="flex items-center gap-1.5 text-13 text-secondary">
                      <input
                        type="checkbox"
                        checked={roles.includes(opt.value)}
                        onChange={(e) =>
                          setRoles(e.target.checked ? [...roles, opt.value] : roles.filter((r) => r !== opt.value))
                        }
                      />
                      {opt.label}
                    </label>
                  ))}
                </div>
              </div>
              <label className="flex flex-col gap-1 text-13 text-tertiary">
                Người duyệt được chỉ định (giữ Ctrl/⌘ để chọn nhiều)
                <select
                  multiple
                  className={`${inputClass} h-24`}
                  value={approvers}
                  onChange={(e) => setApprovers(Array.from(e.target.selectedOptions).map((o) => o.value))}
                >
                  {members.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-13 text-tertiary md:col-span-2">
                Ghi chú hiển thị khi bị chặn
                <input
                  className={inputClass}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Ví dụ: Cần trưởng ban pháp chế duyệt hồ sơ."
                />
              </label>
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="primary"
                size="sm"
                disabled={!toState || (roles.length === 0 && approvers.length === 0) || isSaving}
                loading={isSaving}
                onClick={() => void handleCreate()}
              >
                Lưu quy tắc
              </Button>
              <span className="text-11 text-tertiary">
                Người thoả ít nhất một trong hai điều kiện (vai trò hoặc được chỉ định) mới chuyển được.
              </span>
            </div>
          </div>
        )}
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(WorkflowSettingsPage);
