import { useState } from "react";
import useSWR from "swr";
import { projectRolesService, roleError, type TProjectCustomRole } from "@/services/project/roles.service";
import { projectCustomizationService } from "@/services/project/customization.service";

const emptyRole = { name: "", permissions: [] as string[], property_keys: [] as string[], is_active: true };
const inputClass = "rounded border border-subtle-1 bg-surface-1 px-3 py-2 text-sm";
export function ProjectRoleManager({ workspaceSlug, projectId }: { workspaceSlug: string; projectId: string }) {
  const { data, error, mutate } = useSWR(["custom-roles", workspaceSlug, projectId], () =>
    projectRolesService.list(workspaceSlug, projectId)
  );
  const { data: properties } = useSWR(["role-properties", workspaceSlug, projectId], () =>
    projectCustomizationService.listProperties(workspaceSlug, projectId)
  );
  const [draft, setDraft] = useState<Omit<TProjectCustomRole, "id">>(emptyRole);
  const [editingId, setEditingId] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const run = async (task: () => Promise<unknown>) => {
    setBusy(true);
    setMessage("");
    try {
      await task();
      await mutate();
      setMessage("Saved.");
    } catch (e) {
      setMessage(roleError(e));
    } finally {
      setBusy(false);
    }
  };
  const reset = () => {
    setDraft(emptyRole);
    setEditingId(undefined);
  };
  if (error)
    return (
      <div role="alert">
        {roleError(error)}{" "}
        <button type="button" onClick={() => void mutate()}>
          Retry
        </button>
      </div>
    );
  if (!data) return <p role="status">Loading custom roles…</p>;
  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Custom project roles</h2>
        <p className="text-sm text-tertiary">
          Restrict a Member to the permissions selected here. Admins and Guests keep their built-in roles.
        </p>
        <p className="text-sm text-tertiary">
          Assigned members use restricted access across this workspace: each project they need must have an explicit
          custom role. Workspace-wide search, reports, notifications and other aggregate APIs are unavailable while they
          have a custom role in that workspace.
        </p>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={busy}
          className={inputClass}
          onClick={() => {
            setEditingId(undefined);
            setDraft({ ...emptyRole, name: "Accounting", permissions: ["worklogs.read", "worklogs.export"] });
          }}
        >
          Accounting preset
        </button>
        <button
          type="button"
          disabled={busy}
          className={inputClass}
          onClick={() => {
            setEditingId(undefined);
            setDraft({ ...emptyRole, name: "Legal", permissions: ["issues.read", "properties.edit"] });
          }}
        >
          Legal preset
        </button>
      </div>
      <form
        className="space-y-3 rounded border border-subtle-1 p-4"
        onSubmit={(event) => {
          event.preventDefault();
          void run(async () => {
            await projectRolesService.save(workspaceSlug, projectId, draft, editingId);
            reset();
          });
        }}
      >
        <fieldset disabled={busy} className="space-y-3">
          <legend className="font-medium">{editingId ? "Edit role" : "Create role"}</legend>
          <label className="flex flex-col gap-1">
            Role name
            <input
              required
              maxLength={100}
              className={inputClass}
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
          </label>
          {Object.entries(data.capabilities).map(([key, label]) => (
            <label key={key} className="text-sm flex gap-2">
              <input
                type="checkbox"
                checked={draft.permissions.includes(key)}
                onChange={(e) =>
                  setDraft((current) => {
                    const permissions = new Set(current.permissions);
                    if (e.target.checked) {
                      permissions.add(key);
                      if (key === "worklogs.export") permissions.add("worklogs.read");
                      if (key === "properties.edit") permissions.add("issues.read");
                    } else {
                      permissions.delete(key);
                      if (key === "worklogs.read") permissions.delete("worklogs.export");
                      if (key === "issues.read") permissions.delete("properties.edit");
                    }
                    return {
                      ...current,
                      permissions: [...permissions],
                      property_keys: permissions.has("properties.edit") ? current.property_keys : [],
                    };
                  })
                }
              />
              {label}
            </label>
          ))}
          {draft.permissions.includes("properties.edit") && (
            <div className="space-y-2">
              <p className="text-sm font-medium">Properties this role may edit</p>
              {properties
                ?.filter((p) => p.is_active)
                .map((p) => (
                  <label key={p.id} className="text-sm flex gap-2">
                    <input
                      type="checkbox"
                      checked={draft.property_keys.includes(p.key)}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          property_keys: e.target.checked
                            ? [...draft.property_keys, p.key]
                            : draft.property_keys.filter((k) => k !== p.key),
                        })
                      }
                    />
                    {p.name} ({p.key})
                  </label>
                ))}
              {!properties?.some((p) => p.is_active) && (
                <p className="text-sm">Create custom properties before granting edit access.</p>
              )}
            </div>
          )}
          <label className="text-sm flex gap-2">
            <input
              type="checkbox"
              checked={draft.is_active}
              onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })}
            />
            Active (disabling blocks assigned members)
          </label>
          <div className="flex gap-2">
            <button className={inputClass} type="submit">
              {busy ? "Saving…" : "Save role"}
            </button>
            <button className={inputClass} type="button" onClick={reset}>
              Cancel
            </button>
          </div>
        </fieldset>
      </form>
      <div className="space-y-2">
        {data.roles.map((role) => (
          <div key={role.id} className="flex flex-wrap items-center gap-3 border-b border-subtle-1 py-2">
            <span className="grow">
              {role.name} {!role.is_active && "(disabled)"}
            </span>
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setEditingId(role.id);
                setDraft({
                  name: role.name,
                  permissions: role.permissions,
                  property_keys: role.property_keys,
                  is_active: role.is_active,
                });
              }}
            >
              Edit
            </button>
            <button
              type="button"
              disabled={busy}
              className="text-danger-primary"
              onClick={() => {
                if (window.confirm(`Delete role “${role.name}”? Assigned roles must be unassigned first.`))
                  void run(() => projectRolesService.remove(workspaceSlug, projectId, role.id));
              }}
            >
              Delete
            </button>
          </div>
        ))}
      </div>
      <h3 className="font-medium">Member assignments</h3>
      <p className="text-sm text-tertiary">
        Removing the final custom-role assignment in this workspace restores built-in permissions. Removing just one
        assignment keeps restricted mode active.
      </p>
      {data.members.map((member) => (
        <label key={member.id} className="text-sm flex flex-wrap items-center justify-between gap-2">
          <span>{member.name}</span>
          <select
            aria-label={`Role for ${member.name}`}
            className={inputClass}
            disabled={busy || (!member.eligible && !member.custom_role_id)}
            value={member.custom_role_id ?? ""}
            onChange={(e) => {
              const value = e.target.value || null;
              if (
                value === null &&
                !window.confirm(
                  "Remove this assignment? Removing the final custom role in the workspace restores built-in permissions."
                )
              )
                return;
              void run(() => projectRolesService.assign(workspaceSlug, projectId, member.id, value));
            }}
          >
            <option value="">Built-in role</option>
            {data.roles.map((role) => (
              <option key={role.id} value={role.id} disabled={!role.is_active || !member.eligible}>
                {role.name}
                {!role.is_active && " (disabled)"}
              </option>
            ))}
          </select>
        </label>
      ))}
      {message && (
        <p role="status" className="text-sm">
          {message}
        </p>
      )}
    </section>
  );
}
