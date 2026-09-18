# Custom project roles (THM)

## Shipped scope

Administrators can configure named roles and assign one role to an existing Member in each project. Built-in Admin / Member / Guest memberships remain in the database; custom roles restrict access, never elevate it. This first release covers accounting and legal-property workflows, not an arbitrary permission editor for every CE feature.

| Capability        | Access                                                                                             |
| ----------------- | -------------------------------------------------------------------------------------------------- |
| `worklogs.read`   | Project worklog report, totals, individual worklogs                                                |
| `worklogs.export` | CSV report download; requires `worklogs.read`                                                      |
| `issues.read`     | Search/paginate work item names, sequence numbers and custom-property values in the focused screen |
| `properties.edit` | Change values for explicitly selected active property keys; requires `issues.read`                 |

Accounting preset: worklog read + CSV export. Legal preset: issue-property read + selected property edits. Property editing never grants changes to issue title, description, state, assignees, property definitions, or other properties. The read capability exposes all custom-property values; this is field-level **write** permission, not field-level redaction.

Only active Members with an active Member workspace membership can receive roles. Admin and Guest accounts cannot receive roles. Existing ownership, membership and worklog rules continue to apply; custom permissions do not bypass them.

## Restricted workspace mode — operational impact

**Assigning any custom role puts that user into restricted mode for the entire workspace. Every project they need must have an explicit custom-role assignment. Built-in privileges in other projects in that workspace do not grant access while restricted mode is active.** This is displayed above the assignment controls.

This conservative boundary prevents existing cross-project relations, workspace search, dashboards, exports, notifications, asset routes and API-token endpoints from disclosing or modifying restricted project data. Those endpoints are denied rather than returning partially filtered results. A project identifier or a project ID in a body/query cannot bypass the boundary. Personal profile/settings and workspace/project metadata needed for navigation remain available.

Users enter a focused workspace screen with project links and only the permitted worklog/property tools. No ordinary project data component mounts before authorization is loaded. API failures show an error and Retry; disabled roles show a no-access message. The UI rechecks role access on focus and every 30 seconds. The server reads authorization from the primary database on every request.

Users without a custom role retain the original CE behavior. Other workspaces are unaffected. Unscoped aggregate endpoints are unavailable if the user has a restricted assignment anywhere. Existing downloaded files, emails, cached browser content and publicly published content cannot be revoked by this API permission system.

## Administration

1. Open **Project settings → Customization → Custom project roles** as project admin (or workspace admin who belongs to the project).
2. Create a named role or use Accounting / Legal preset. Select active custom properties for Legal.
3. Assign it to each required Member/project. Assignment changes affect the next API request.
4. Disable a role to suspend access without restoring built-in permissions.
5. Remove assignments explicitly to restore built-in access. Restricted mode ends only after the user's final assignment in that workspace is removed. A role with assignments cannot be deleted (409).

Inactive/soft-deleted memberships retain the restriction until an administrator explicitly removes their assignment. They cannot use the role's tools. The manager includes inactive memberships so administrators can release those assignments. Removing an assignment uses a hard delete to make the one-to-one slot reusable; deleting a role uses soft deletion. Changing or soft-deleting a role does not grant broader permissions.

Role/property names are not privileges. A role grants only the enumerated capabilities. Property grants use stable project property **keys**: administrators should not reuse a key for a semantically different property without reviewing role grants. Unknown or inactive properties are rejected when editing values. Updates merge only submitted keys under an issue-row lock, preserve other properties and append an `IssueActivity` attributed to the actor.

## API and implementation

- `GET/POST .../projects/{project}/custom-roles/`
- `PATCH/DELETE .../projects/{project}/custom-roles/{role}/`
- `PUT .../projects/{project}/role-assignments/{membership}/` with `custom_role_id` (UUID or null)
- `GET .../projects/{project}/custom-role/me/`
- `GET .../workspaces/{slug}/role-access/`
- `GET .../projects/{project}/role-issues/?search=&offset=` (50 items/page)
- `PATCH .../projects/{project}/role-issues/{issue}/` with only `custom_properties`

The shared guard is installed on both app/session and public/token API base classes. Views opt into a capability with `rbac_policy`; unclassified endpoints deny restricted users. `metadata` is an explicit exemption and must never be used for project data or cross-project mutations. Do not extend permissions simply by changing a frontend checkbox.

Worklog CSV uses the existing endpoint. Renderer negotiation now accepts its `format=csv` query parameter, export checks are separate from read checks, and cells starting with spreadsheet formula characters are escaped. Exported data remains governed by existing worklog date/status filters and approval defaults.

## Rollout / validation

Run migration `0133_project_custom_roles` before releasing the API/web changes. There is no automatic role assignment, backfill or change to existing member permissions. Do not roll back the API alone while assignments exist: an old API does not enforce these restrictions. Remove assignments deliberately before reverting the feature, or keep the guard in place.

Contract tests cover report/export separation, forbidden issue/worklog/timer writes, direct API-token calls, field validation and preservation, cross-project targets, workspace aggregate denial, role revocation, admin-only assignment/removal, inactive memberships, disabled/deleted roles and CSV formula escaping. UI tests cover scoped tools, failed saves, assignment, fail-closed workspace entry and projects without explicit roles.
