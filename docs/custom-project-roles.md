# Custom project roles (THM)

## Scope and effective permissions

A custom role restricts **only the project where it is assigned**. Other projects retain their own custom role or built-in role. Workspace navigation, search, dashboards, notifications and export history remain available; their project data is filtered before aggregation and pagination.

Effective access is the intersection of the built-in membership, custom capabilities, and existing ownership/privacy/workflow rules. A custom role never elevates a Member into an Admin. Active project Members and project Admins can receive roles when their workspace membership is Member. Workspace Admins and Guests are not eligible. Only an unrestricted administrator can manage roles or assignments; a restricted project Admin cannot remove their own restrictions.

## Permission catalog

The role editor groups capabilities by feature. Read is required for other actions on the same feature. The backend catalog is the authoritative list.

| Feature                                     | Actions                                                                               |
| ------------------------------------------- | ------------------------------------------------------------------------------------- |
| Work items / epics                          | Read, create, update, delete, archive/restore, export                                 |
| Comments, attachments                       | Read, create, update, delete                                                          |
| Cycles, modules                             | Read, create, update, delete, archive/restore                                         |
| Pages                                       | Read, create, update, delete, archive/restore, lock/unlock, change visibility, export |
| Views, intake, worklogs                     | Read, create, update, delete                                                          |
| Worklogs                                    | Separate CSV export and approval/review                                               |
| States, labels, estimates, types, templates | Read, create, update, delete within existing CE authority                             |
| Workflow, recurring work items              | Read, create, update, delete                                                          |
| Members, project settings                   | Read, create, update, delete; existing administrator checks still apply               |
| Project lifecycle                           | Archive/restore, publish                                                              |
| Analytics and dashboards                    | Read, create, update, delete, export                                                  |
| Custom properties                           | Read names/values, edit selected property keys, create/update/delete definitions      |

Navigation metadata such as project names, member rosters and state/label choices remains readable under existing membership checks. This does not expose work item/page content. Workspace and instance administration continue to use their built-in roles; the catalog governs project features, not instance administration.

Accounting preset grants worklog read/export. Legal preset grants `properties.read` and `properties.edit` for selected keys. A read-only preset grants feature read capabilities. Accounting/legal roles retain a focused project screen; expanded roles use the normal CE feature screens. Disabled roles grant no project content access. Role access refreshes on focus and every 30 seconds; API checks use the primary database on each request.

`properties.read` exposes work item names, sequence numbers and all property values without description/content. `issues.read` exposes full work items. Property keys restrict writes, not field-level visibility. Updates merge submitted keys, preserving other values. Role names have no special authority.

## Administration

1. Open **Project settings → Customization → Custom project roles**.
2. Create a role, choose feature actions, and select property keys if granting property edits.
3. Assign one role to the relevant project membership. No assignments are created automatically.
4. Disable a role to suspend its grants. Remove an assignment explicitly to restore that project's built-in permissions.

Roles with assignments cannot be deleted (409). Inactive/soft-deleted memberships retain the assignment restriction until an administrator removes it, preventing accidental restoration. Assignment removal hard-deletes the one-to-one link so reassignment remains possible.

## Enforcement and extension points

- App/session and public/API-token endpoints use the shared guard and explicit `project_rbac_policies.py` catalog. Unclassified routes targeting an assigned project fail closed.
- `scoped_queryset` filters project data, related-key validation and export history. `scoped_aggregate` filters reverse-relation counts/sums. Add these scopes when implementing a new workspace query; a project URL guard alone cannot protect aggregates.
- Cross-project work item mutations authorize both ends. Object IDs must belong to the project in the URL. Generic page updates also check separate lock, archive and visibility capabilities.
- Role-bearing requests bypass response caches and return `Cache-Control: private, no-store`. Request context is reset after dispatch, including errors.
- Export workers recheck grants using the initiating user. Related comments/modules/parents/relations are filtered too. Default issue exports include only permitted projects.
- Live editor connections check page access even for an already-cached document. Read-only connections cannot apply Yjs updates; subsequent client messages recheck access. API persistence remains independently protected. PDF export checks `pages.export`; local Word/Markdown export controls honor the same capability.

Previously downloaded content, public published content, and copies of already-readable content cannot be revoked by these permissions. Export controls govern built-in export operations; they do not provide DRM.

## APIs

- `GET/POST .../projects/{project}/custom-roles/`
- `PATCH/DELETE .../projects/{project}/custom-roles/{role}/`
- `PUT .../projects/{project}/role-assignments/{membership}/` with `custom_role_id` or null
- `GET .../projects/{project}/custom-role/me/`
- `GET .../workspaces/{slug}/role-access/`
- `GET .../projects/{project}/role-issues/?search=&offset=` (50 rows/page)
- `PATCH .../projects/{project}/role-issues/{issue}/` with `custom_properties`
- `GET .../projects/{project}/pages/{page}/access-check/` (optional `action=export`)

## Migration and rollout

Apply migrations `0133_project_custom_roles` and `0134_expand_project_role_permissions` and release API, web, workers and live together. Migration 0134 converts legacy `issues.read` grants into `properties.read`, preserving the older Legal role's limited content access. Administrators explicitly grant the new full `issues.read` permission when appropriate.

An API rollback alone would discard enforcement. Review/remove expanded roles deliberately before rolling back, or retain this guard. Reversing the data migration does not make expanded capabilities compatible with the old API.

Tests cover mixed-project access, granular reads/writes, token calls, cross-project IDs, field preservation, analytics filtering, cache revocation, export worker checks, legacy migration, endpoint classification, UI routing and live-editor authorization.
