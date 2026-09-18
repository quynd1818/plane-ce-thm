import { useState } from "react";
import useSWR from "swr";
import { WorkLogService } from "@/services/issue/worklog.service";
import {
  projectRolesService,
  roleError,
  type TProjectCustomRole,
  type TRoleIssue,
} from "@/services/project/roles.service";
import type { TCustomProperty } from "@/services/project/customization.service";

const worklogs = new WorkLogService();
const control = "rounded border border-subtle-1 bg-surface-1 px-3 py-2 text-sm";
type Props = { workspaceSlug: string; projectId: string; role: TProjectCustomRole };

function PropertyEditor({
  property,
  value,
  onSave,
}: {
  property: TCustomProperty;
  value: unknown;
  onSave: (value: unknown) => Promise<void>;
}) {
  const [draft, setDraft] = useState(
    property.property_type === "multi_select"
      ? JSON.stringify(Array.isArray(value) ? value : [])
      : value == null
        ? ""
        : String(value)
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = async () => {
    setBusy(true);
    setError("");
    let next: unknown = draft;
    if (draft === "") next = null;
    else if (property.property_type === "number") next = Number(draft);
    else if (property.property_type === "boolean") next = draft === "true";
    else if (property.property_type === "multi_select") next = JSON.parse(draft);
    try {
      await onSave(next);
    } catch (e) {
      setError(roleError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-1">
      <label className="text-sm flex flex-wrap items-center gap-2">
        <span className="w-40">
          {property.name}
          {property.is_required && " *"}
        </span>
        {property.property_type === "boolean" || property.property_type === "select" ? (
          <select disabled={busy} className={control} value={draft} onChange={(e) => setDraft(e.target.value)}>
            <option value="">Unset</option>
            {(property.property_type === "boolean" ? ["true", "false"] : property.options).map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        ) : property.property_type === "multi_select" ? (
          <select
            multiple
            disabled={busy}
            className={control}
            value={JSON.parse(draft) as string[]}
            onChange={(e) => setDraft(JSON.stringify(Array.from(e.target.selectedOptions, (option) => option.value)))}
          >
            {property.options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        ) : (
          <input
            disabled={busy}
            className={control}
            type={property.property_type === "number" ? "number" : property.property_type === "date" ? "date" : "text"}
            step="any"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Value"
          />
        )}
        <button type="button" className={control} disabled={busy} onClick={() => void save()}>
          {busy ? "Saving…" : "Save"}
        </button>
      </label>
      {error && (
        <p role="alert" className="text-sm text-danger-primary">
          {error}
        </p>
      )}
    </div>
  );
}

function IssueProperties({
  issue,
  properties,
  allowedKeys,
  save,
}: {
  issue: TRoleIssue;
  properties: TCustomProperty[];
  allowedKeys: string[];
  save: (key: string, value: unknown) => Promise<void>;
}) {
  return (
    <article className="space-y-3 rounded border border-subtle-1 p-4">
      <h3 className="font-medium">
        #{issue.sequence_id} {issue.name}
      </h3>
      {properties.map((property) =>
        allowedKeys.includes(property.key) ? (
          <PropertyEditor
            key={`${issue.id}-${property.key}-${JSON.stringify(issue.custom_properties[property.key])}`}
            property={property}
            value={issue.custom_properties[property.key]}
            onSave={(v) => save(property.key, v)}
          />
        ) : (
          <p key={property.key} className="text-sm">
            <span className="text-tertiary">{property.name}: </span>
            {JSON.stringify(issue.custom_properties[property.key] ?? null)}
          </p>
        )
      )}
    </article>
  );
}

function RestrictedIssues({ workspaceSlug, projectId, role }: Props) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const { data, error, mutate } = useSWR(["role-issues", workspaceSlug, projectId, role.id, query, offset], () =>
    projectRolesService.issues(workspaceSlug, projectId, query, offset)
  );
  const allowedKeys = role.permissions.includes("properties.edit") ? role.property_keys : [];
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-medium">Work item properties</h2>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setOffset(0);
          setQuery(search);
        }}
      >
        <input
          className={control}
          aria-label="Search work items"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search work items"
        />
        <button className={control} type="submit">
          Search
        </button>
      </form>
      {error ? (
        <p role="alert">
          {roleError(error)}{" "}
          <button onClick={() => void mutate()} type="button">
            Retry
          </button>
        </p>
      ) : !data ? (
        <p role="status">Loading work items…</p>
      ) : (
        <>
          {!data.results.length && <p>No matching work items.</p>}
          {data.results.map((issue) => (
            <IssueProperties
              key={issue.id}
              issue={issue}
              properties={data.properties}
              allowedKeys={allowedKeys}
              save={async (key, value) => {
                await projectRolesService.updateProperties(workspaceSlug, projectId, issue.id, { [key]: value });
                await mutate();
              }}
            />
          ))}
          <div className="flex items-center gap-3">
            <button
              type="button"
              className={control}
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 50))}
            >
              Previous
            </button>
            <span>{data.count} work items</span>
            <button
              type="button"
              className={control}
              disabled={offset + 50 >= data.count}
              onClick={() => setOffset(offset + 50)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function RestrictedWorklogs({ workspaceSlug, projectId, role }: Props) {
  const [after, setAfter] = useState(() => new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10));
  const [before, setBefore] = useState(() => new Date().toISOString().slice(0, 10));
  const [exportError, setExportError] = useState("");
  const [busy, setBusy] = useState(false);
  const params = { started_after: after, started_before: before };
  const { data, error, mutate } = useSWR(["role-worklogs", workspaceSlug, projectId, role.id, after, before], () =>
    worklogs.getProjectReport(workspaceSlug, projectId, params)
  );
  const download = async () => {
    setBusy(true);
    setExportError("");
    try {
      const blob = await worklogs.exportProjectReport(workspaceSlug, projectId, params);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "worklogs.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setExportError(roleError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-medium">Worklogs</h2>
      <div className="flex flex-wrap items-center gap-3">
        <label>
          From <input className={control} type="date" value={after} onChange={(e) => setAfter(e.target.value)} />
        </label>
        <label>
          To <input className={control} type="date" value={before} onChange={(e) => setBefore(e.target.value)} />
        </label>
        {role.permissions.includes("worklogs.export") && (
          <button className={control} type="button" disabled={busy || !data} onClick={() => void download()}>
            {busy ? "Exporting…" : "Export CSV"}
          </button>
        )}
      </div>
      {exportError && <p role="alert">{exportError}</p>}
      {error ? (
        <p role="alert">
          {roleError(error)}{" "}
          <button type="button" onClick={() => void mutate()}>
            Retry
          </button>
        </p>
      ) : !data ? (
        <p role="status">Loading worklogs…</p>
      ) : (
        <>
          <p>
            Total: {(data.total_seconds / 3600).toFixed(2)} hours. Projects with approval enabled show approved entries
            by default.
          </p>
          <div className="overflow-auto">
            <table className="text-sm w-full text-left">
              <thead>
                <tr>
                  <th>Work item</th>
                  <th>User</th>
                  <th>Description</th>
                  <th>Hours</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((log) => (
                  <tr key={log.id} className="border-t border-subtle-1">
                    <td className="py-2">{log.issue_name}</td>
                    <td>{log.user_email}</td>
                    <td>{log.description}</td>
                    <td>{(log.duration_seconds / 3600).toFixed(2)}</td>
                    <td>{log.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!data.results.length && <p>No worklogs in this period.</p>}
        </>
      )}
    </section>
  );
}

export function RestrictedProjectPanel(props: Props) {
  const { role } = props;
  return (
    <main className="h-full w-full space-y-8 overflow-auto p-6">
      <header>
        <h1 className="text-xl font-semibold">{role.name}</h1>
        <p className="text-sm text-tertiary">
          Your project role grants access to the tools below. Contact a project administrator to change your access.
        </p>
      </header>
      {!role.is_active || !role.permissions.length ? (
        <p role="status">This role currently grants no access.</p>
      ) : (
        <>
          {role.permissions.includes("worklogs.read") && <RestrictedWorklogs {...props} />}
          {role.permissions.includes("issues.read") && <RestrictedIssues {...props} />}
        </>
      )}
    </main>
  );
}
