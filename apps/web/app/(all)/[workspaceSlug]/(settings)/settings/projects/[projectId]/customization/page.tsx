import { useCustomProjectRole } from "@/components/project-roles/access";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useUserPermissions } from "@/hooks/store/user";
import { ProjectRoleManager } from "@/components/project-roles/manager";
import { observer } from "mobx-react";
import { useCallback, useEffect, useState } from "react";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import {
  projectCustomizationService,
  type TCustomProperty,
  type TWorkItemTemplate,
  type TWorkItemType,
  type TAvailableWorkItemType,
} from "@/services/project/customization.service";
import { projectPhase3Service, type TIntakeForm, type TRecurringIssue } from "@/services/project/phase3.service";
import { useProject } from "@/hooks/store/use-project";
import type { Route } from "./+types/page";

function CustomizationPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { currentProjectDetails } = useProject();
  const { allowPermissions } = useUserPermissions();
  const customRole = useCustomProjectRole(projectId);
  const canManageRoles =
    !customRole && allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT, workspaceSlug, projectId);
  const [properties, setProperties] = useState<TCustomProperty[]>([]);
  const [templates, setTemplates] = useState<TWorkItemTemplate[]>([]);
  const [types, setTypes] = useState<TWorkItemType[]>([]);
  const [availableTypes, setAvailableTypes] = useState<TAvailableWorkItemType[]>([]);
  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [propertyType, setPropertyType] = useState<TCustomProperty["property_type"]>("text");
  const [propertyOptions, setPropertyOptions] = useState("");
  const [propertyRequired, setPropertyRequired] = useState(false);
  const [templateName, setTemplateName] = useState("");
  const [templateDefaults, setTemplateDefaults] = useState("{}");
  const [typeId, setTypeId] = useState("");
  const [intakeForms, setIntakeForms] = useState<TIntakeForm[]>([]);
  const [recurringIssues, setRecurringIssues] = useState<TRecurringIssue[]>([]);
  const [formName, setFormName] = useState("");
  const [formSlug, setFormSlug] = useState("");
  const [recurringName, setRecurringName] = useState("");
  const [recurringFrequency, setRecurringFrequency] = useState<TRecurringIssue["frequency"]>("weekly");
  const [recurringInterval, setRecurringInterval] = useState(1);
  const [dashboardSummary, setDashboardSummary] = useState<{
    work_items: { total: number; completed: number; overdue: number; unassigned: number };
    worklogs: { total_seconds: number; entries: number };
  } | null>(null);

  const load = useCallback(async () => {
    const [nextProperties, nextTemplates, nextTypes, nextAvailableTypes, nextForms, nextRecurring, nextSummary] =
      await Promise.all([
        projectCustomizationService.listProperties(workspaceSlug, projectId),
        projectCustomizationService.listTemplates(workspaceSlug, projectId),
        projectCustomizationService.listWorkItemTypes(workspaceSlug, projectId),
        projectCustomizationService.listAvailableWorkItemTypes(workspaceSlug, projectId),
        projectPhase3Service.listIntakeForms(workspaceSlug, projectId),
        projectPhase3Service.listRecurringIssues(workspaceSlug, projectId),
        projectPhase3Service.getDashboardSummary(workspaceSlug, projectId),
      ]);
    setProperties(nextProperties);
    setTemplates(nextTemplates);
    setTypes(nextTypes);
    setAvailableTypes(nextAvailableTypes);
    setIntakeForms(nextForms);
    setRecurringIssues(nextRecurring);
    setDashboardSummary(nextSummary);
  }, [projectId, workspaceSlug]);

  useEffect(() => {
    void load();
  }, [load]);

  const addProperty = async () => {
    if (!name.trim() || !key.trim()) return;
    await projectCustomizationService.createProperty(workspaceSlug, projectId, {
      name,
      key,
      property_type: propertyType,
      options: propertyOptions
        .split(",")
        .map((option) => option.trim())
        .filter(Boolean),
      is_required: propertyRequired,
      is_active: true,
    });
    setName("");
    setKey("");
    setPropertyOptions("");
    setPropertyRequired(false);
    await load();
  };

  const addTemplate = async () => {
    if (!templateName.trim()) return;
    let defaults: Record<string, unknown>;
    try {
      defaults = JSON.parse(templateDefaults) as Record<string, unknown>;
    } catch {
      return;
    }
    await projectCustomizationService.createTemplate(workspaceSlug, projectId, {
      name: templateName,
      description: "",
      defaults,
      is_active: true,
    });
    setTemplateName("");
    setTemplateDefaults("{}");
    await load();
  };

  const addType = async () => {
    if (!typeId.trim()) return;
    await projectCustomizationService.addWorkItemType(workspaceSlug, projectId, typeId.trim());
    setTypeId("");
    await load();
  };

  const addIntakeForm = async () => {
    if (!formName.trim() || !formSlug.trim()) return;
    await projectPhase3Service.createIntakeForm(workspaceSlug, projectId, {
      name: formName.trim(),
      slug: formSlug.trim(),
      description: "",
      fields: [
        { key: "title", label: "Title", type: "text", required: true },
        { key: "description", label: "Description", type: "textarea", required: false },
      ],
      default_values: {},
      is_active: true,
    });
    setFormName("");
    setFormSlug("");
    await load();
  };

  const addRecurringIssue = async () => {
    if (!recurringName.trim()) return;
    await projectPhase3Service.createRecurringIssue(workspaceSlug, projectId, {
      name: recurringName.trim(),
      description_html: "<p></p>",
      frequency: recurringFrequency,
      interval: recurringInterval,
      next_run_at: new Date().toISOString(),
      is_active: true,
      priority: "none",
      assignee_ids: [],
      label_ids: [],
      custom_properties: {},
    });
    setRecurringName("");
    await load();
  };

  const remove = async (kind: "property" | "template" | "type" | "form" | "recurring", id: string) => {
    if (!window.confirm("Remove this item?")) return;
    if (kind === "property") await projectCustomizationService.deleteProperty(workspaceSlug, projectId, id);
    if (kind === "template") await projectCustomizationService.deleteTemplate(workspaceSlug, projectId, id);
    if (kind === "type") await projectCustomizationService.deleteWorkItemType(workspaceSlug, projectId, id);
    if (kind === "form") await projectPhase3Service.deleteIntakeForm(workspaceSlug, projectId, id);
    if (kind === "recurring") await projectPhase3Service.deleteRecurringIssue(workspaceSlug, projectId, id);
    await load();
  };

  return (
    <SettingsContentWrapper>
      <PageHead
        title={currentProjectDetails?.name ? `${currentProjectDetails.name} - Customization` : "Customization"}
      />
      <div className="flex flex-col gap-8">
        {canManageRoles && <ProjectRoleManager workspaceSlug={workspaceSlug} projectId={projectId} />}
        <div>
          <h1 className="text-xl font-semibold">Work item customization</h1>
          <p className="text-sm text-tertiary">
            Configure properties, templates, and work item types for this project.
          </p>
        </div>
        <section className="space-y-3">
          <h2 className="text-base font-medium">Custom properties</h2>
          <div className="flex flex-wrap gap-2">
            <input
              className="rounded border border-subtle-1 px-2 py-1"
              placeholder="Name"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <input
              className="rounded border border-subtle-1 px-2 py-1"
              placeholder="key"
              value={key}
              onChange={(event) => setKey(event.target.value)}
            />
            <select
              className="rounded border border-subtle-1 px-2 py-1"
              value={propertyType}
              onChange={(event) => setPropertyType(event.target.value as TCustomProperty["property_type"])}
            >
              <option value="text">Text</option>
              <option value="number">Number</option>
              <option value="boolean">Boolean</option>
              <option value="date">Date</option>
              <option value="select">Select</option>
              <option value="multi_select">Multi select</option>
            </select>
            {(propertyType === "select" || propertyType === "multi_select") && (
              <input
                className="rounded border border-subtle-1 px-2 py-1"
                placeholder="Options: low, medium, high"
                value={propertyOptions}
                onChange={(event) => setPropertyOptions(event.target.value)}
              />
            )}
            <label className="text-sm flex items-center gap-1">
              <input
                type="checkbox"
                checked={propertyRequired}
                onChange={(event) => setPropertyRequired(event.target.checked)}
              />
              Required
            </label>
            <button
              type="button"
              className="rounded bg-accent-primary px-3 py-1 text-on-color"
              onClick={() => void addProperty()}
            >
              Add
            </button>
          </div>
          {properties.map((item) => (
            <div key={item.id} className="text-sm flex justify-between border-b border-subtle-1 py-2">
              <span>
                {item.name}{" "}
                <span className="text-tertiary">
                  ({item.key}, {item.property_type})
                </span>
              </span>
              <button type="button" className="text-danger-primary" onClick={() => void remove("property", item.id)}>
                Remove
              </button>
            </div>
          ))}
        </section>
        <section className="space-y-3">
          <h2 className="text-base font-medium">Intake forms</h2>
          <p className="text-sm text-tertiary">
            Create a public form that submits work items to the project intake inbox.
          </p>
          <div className="flex flex-wrap gap-2">
            <input
              className="rounded border border-subtle-1 px-2 py-1"
              placeholder="Form name"
              value={formName}
              onChange={(event) => setFormName(event.target.value)}
            />
            <input
              className="rounded border border-subtle-1 px-2 py-1"
              placeholder="slug"
              value={formSlug}
              onChange={(event) => setFormSlug(event.target.value)}
            />
            <button
              type="button"
              className="rounded bg-accent-primary px-3 py-1 text-on-color"
              onClick={() => void addIntakeForm()}
            >
              Add
            </button>
          </div>
          {intakeForms.map((item) => (
            <div key={item.id} className="text-sm flex justify-between border-b border-subtle-1 py-2">
              <span>
                {item.name}{" "}
                <span className="text-tertiary">
                  ({item.slug}) · public key: {item.public_key}
                </span>
              </span>
              <button type="button" className="text-danger-primary" onClick={() => void remove("form", item.id)}>
                Remove
              </button>
            </div>
          ))}
        </section>
        <section className="space-y-3">
          <h2 className="text-base font-medium">Recurring issues</h2>
          <div className="flex flex-wrap gap-2">
            <input
              className="rounded border border-subtle-1 px-2 py-1"
              placeholder="Issue title"
              value={recurringName}
              onChange={(event) => setRecurringName(event.target.value)}
            />
            <select
              className="rounded border border-subtle-1 px-2 py-1"
              value={recurringFrequency}
              onChange={(event) => setRecurringFrequency(event.target.value as TRecurringIssue["frequency"])}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
            <input
              className="w-20 rounded border border-subtle-1 px-2 py-1"
              type="number"
              min={1}
              value={recurringInterval}
              onChange={(event) => setRecurringInterval(Math.max(1, Number(event.target.value) || 1))}
            />
            <button
              type="button"
              className="rounded bg-accent-primary px-3 py-1 text-on-color"
              onClick={() => void addRecurringIssue()}
            >
              Add
            </button>
          </div>
          {recurringIssues.map((item) => (
            <div key={item.id} className="text-sm flex justify-between border-b border-subtle-1 py-2">
              <span>
                {item.name}{" "}
                <span className="text-tertiary">
                  ({item.interval} {item.frequency}) · next {new Date(item.next_run_at).toLocaleString()}
                </span>
              </span>
              <button type="button" className="text-danger-primary" onClick={() => void remove("recurring", item.id)}>
                Remove
              </button>
            </div>
          ))}
        </section>
        {dashboardSummary && (
          <section className="space-y-3">
            <h2 className="text-base font-medium">Project dashboard summary</h2>
            <div className="text-sm grid grid-cols-2 gap-3 md:grid-cols-4">
              <div className="rounded border border-subtle-1 p-3">
                Work items <strong className="text-lg block">{dashboardSummary.work_items.total}</strong>
              </div>
              <div className="rounded border border-subtle-1 p-3">
                Completed <strong className="text-lg block">{dashboardSummary.work_items.completed}</strong>
              </div>
              <div className="rounded border border-subtle-1 p-3">
                Overdue <strong className="text-lg block">{dashboardSummary.work_items.overdue}</strong>
              </div>
              <div className="rounded border border-subtle-1 p-3">
                Logged hours{" "}
                <strong className="text-lg block">{(dashboardSummary.worklogs.total_seconds / 3600).toFixed(1)}</strong>
              </div>
            </div>
          </section>
        )}
        <section className="space-y-3">
          <h2 className="text-base font-medium">Work item templates</h2>
          <div className="flex flex-wrap gap-2">
            <input
              className="rounded border border-subtle-1 px-2 py-1"
              placeholder="Template name"
              value={templateName}
              onChange={(event) => setTemplateName(event.target.value)}
            />
            <input
              className="w-64 rounded border border-subtle-1 px-2 py-1"
              placeholder='Defaults JSON, e.g. {"priority":"high"}'
              value={templateDefaults}
              onChange={(event) => setTemplateDefaults(event.target.value)}
            />
            <button
              type="button"
              className="rounded bg-accent-primary px-3 py-1 text-on-color"
              onClick={() => void addTemplate()}
            >
              Add
            </button>
          </div>
          {templates.map((item) => (
            <div key={item.id} className="text-sm flex justify-between border-b border-subtle-1 py-2">
              <span>{item.name}</span>
              <button type="button" className="text-danger-primary" onClick={() => void remove("template", item.id)}>
                Remove
              </button>
            </div>
          ))}
        </section>
        <section className="space-y-3">
          <h2 className="text-base font-medium">Work item types</h2>
          <div className="flex gap-2">
            <select
              className="grow rounded border border-subtle-1 px-2 py-1"
              value={typeId}
              onChange={(event) => setTypeId(event.target.value)}
            >
              <option value="">Select a work item type</option>
              {availableTypes.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="rounded bg-accent-primary px-3 py-1 text-on-color"
              onClick={() => void addType()}
            >
              Add
            </button>
          </div>
          {types.map((item) => (
            <div key={item.id} className="text-sm flex justify-between border-b border-subtle-1 py-2">
              <span>{item.name}</span>
              <button type="button" className="text-danger-primary" onClick={() => void remove("type", item.id)}>
                Remove
              </button>
            </div>
          ))}
        </section>
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(CustomizationPage);
