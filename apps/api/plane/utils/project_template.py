# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""THM project templates: capture a project's set-up into JSON and apply it to
a freshly created project.

``template_data`` schema (all keys optional, all lists may be empty)::

    {
      "project": {"network": 2, "cycle_view": true, ... feature flags ...},
      "states": [{"name", "color", "group", "sequence", "default", "description"}],
      "labels": [{"name", "color", "description", "sort_order", "parent"}],
      "modules": [{"name", "description", "status", "sort_order"}],
      "workflow_rules": [{"from_state", "to_state", "allowed_roles", "description"}],
      "custom_properties": [{"name", "key", "property_type", "options", "is_required"}],
      "work_item_templates": [{"name", "description", "defaults"}],
      "work_items": [{"name", "description_html", "priority", "state", "labels", "modules", "sort_order"}],
    }

States, labels and modules are referenced by *name* everywhere so a template
never carries ids from the source project. People (assignees, leads, named
workflow approvers) are deliberately not captured: they are project members,
not project structure.
"""

from copy import deepcopy

from django.db import transaction

from plane.db.models import (
    Issue,
    IssueLabel,
    Label,
    Module,
    ModuleIssue,
    Project,
    ProjectCustomProperty,
    State,
    WorkflowTransitionRule,
    WorkItemTemplate,
)

# Project columns that describe *how the project works* and are safe to copy.
PROJECT_SETTING_FIELDS = (
    "network",
    "cycle_view",
    "module_view",
    "issue_views_view",
    "page_view",
    "intake_view",
    "is_time_tracking_enabled",
    "is_workflow_enabled",
    "is_worklog_approval_enabled",
    "is_issue_type_enabled",
    "guest_view_all_features",
    "archive_in",
    "close_in",
    "timezone",
)

MAX_WORK_ITEMS = 500


WORK_ITEM_DEFAULT_FIELDS = (
    "name",
    "description_html",
    "priority",
    "start_date",
    "target_date",
    "custom_properties",
)


def portable_defaults(defaults, states, labels, modules):
    """Copy values and resolve source IDs to names; omit people and unsupported relations."""
    defaults = defaults or {}
    result = {key: deepcopy(defaults[key]) for key in WORK_ITEM_DEFAULT_FIELDS if key in defaults}
    state_names = {str(state.id): state.name for state in states}
    if defaults.get("state_id") in state_names:
        result["state"] = state_names[defaults["state_id"]]
    for key, objects in (("labels", labels), ("modules", modules)):
        names = {str(obj.id): obj.name for obj in objects}
        if f"{key[:-1]}_ids" in defaults:
            result[key] = [names[value] for value in defaults[f"{key[:-1]}_ids"] or [] if value in names]
    return result


def restore_defaults(defaults, states, labels, modules):
    """Only destination-project IDs may appear in restored work item defaults."""
    result = {key: deepcopy(defaults[key]) for key in WORK_ITEM_DEFAULT_FIELDS if key in defaults}
    if defaults.get("state") in states:
        result["state_id"] = str(states[defaults["state"]].id)
    for key, objects in (("labels", labels), ("modules", modules)):
        if key in defaults:
            result[f"{key[:-1]}_ids"] = [str(objects[name].id) for name in defaults[key] or [] if name in objects]
    return result


# --------------------------------------------------------------------------- #
# capture
# --------------------------------------------------------------------------- #
def capture_project(project: Project, include_work_items: bool = False) -> dict:
    """Snapshot ``project`` into ``template_data``."""
    states = list(State.objects.filter(project=project, is_triage=False).order_by("sequence"))
    labels = list(Label.objects.filter(project=project).select_related("parent").order_by("sort_order", "name"))
    modules = list(Module.objects.filter(project=project, archived_at__isnull=True).order_by("sort_order", "name"))

    data = {
        "project": {field: getattr(project, field) for field in PROJECT_SETTING_FIELDS},
        "states": [
            {
                "name": s.name,
                "color": s.color,
                "group": s.group,
                "sequence": s.sequence,
                "default": s.default,
                "description": s.description,
            }
            for s in states
        ],
        "labels": [
            {
                "name": lbl.name,
                "color": lbl.color,
                "description": lbl.description,
                "sort_order": lbl.sort_order,
                "parent": lbl.parent.name if lbl.parent_id else None,
            }
            for lbl in labels
        ],
        "modules": [
            {"name": m.name, "description": m.description, "status": m.status, "sort_order": m.sort_order}
            for m in modules
        ],
        "workflow_rules": [
            {
                "from_state": rule.from_state.name if rule.from_state_id else None,
                "to_state": rule.to_state.name,
                "allowed_roles": rule.allowed_roles or [],
                "description": rule.description,
            }
            for rule in WorkflowTransitionRule.objects.filter(project=project, is_active=True).select_related(
                "from_state", "to_state"
            )
        ],
        "custom_properties": [
            {
                "name": p.name,
                "key": p.key,
                "property_type": p.property_type,
                "options": p.options,
                "is_required": p.is_required,
            }
            for p in ProjectCustomProperty.objects.filter(project=project, is_active=True)
        ],
        "work_item_templates": [
            {
                "name": w.name,
                "description": w.description,
                "defaults": portable_defaults(w.defaults, states, labels, modules),
            }
            for w in WorkItemTemplate.objects.filter(project=project, is_active=True)
        ],
        "work_items": [],
    }

    if include_work_items:
        issues = (
            Issue.issue_objects.filter(project=project, parent__isnull=True)
            .select_related("state")
            .prefetch_related("label_issue__label", "issue_module__module")
            .order_by("sequence_id")[:MAX_WORK_ITEMS]
        )
        data["work_items"] = [
            {
                "name": issue.name,
                "description_html": issue.description_html or "<p></p>",
                "priority": issue.priority,
                "state": issue.state.name if issue.state_id else None,
                "labels": [il.label.name for il in issue.label_issue.all() if il.label_id],
                "modules": [im.module.name for im in issue.issue_module.all() if im.module_id],
                "sort_order": issue.sort_order,
            }
            for issue in issues
        ]
    return data


# --------------------------------------------------------------------------- #
# apply
# --------------------------------------------------------------------------- #
@transaction.atomic
def apply_template(project: Project, template_data: dict, user, source_project=None) -> None:
    """Reproduce ``template_data`` inside ``project``.

    Called right after the project row exists. Template states *replace* the
    stock default states; everything else is added. Safe to call with an
    empty / partial template.
    """
    data = template_data or {}
    workspace = project.workspace
    audit = {"created_by": user, "workspace": workspace, "project": project}

    # 1. project settings
    settings = {k: v for k, v in (data.get("project") or {}).items() if k in PROJECT_SETTING_FIELDS}
    if settings:
        Project.objects.filter(pk=project.pk).update(**settings)
        for k, v in settings.items():
            setattr(project, k, v)

    # 2. states — replace the defaults so the template's set is the whole set
    states_by_name: dict[str, State] = {}
    tpl_states = [dict(s) for s in (data.get("states") or []) if s.get("name")]
    if tpl_states:
        # brand-new project: nothing references the stock states yet, so hard-delete
        State.objects.filter(project=project, is_triage=False).delete(soft=False)
        if not any(s.get("default") for s in tpl_states):
            tpl_states[0]["default"] = True
        for i, s in enumerate(tpl_states):
            state = State.objects.create(
                name=s["name"],
                color=s.get("color") or "#a3a3a3",
                group=s.get("group") or "backlog",
                sequence=s.get("sequence") if s.get("sequence") is not None else (i + 1) * 15000,
                default=bool(s.get("default")),
                description=s.get("description") or "",
                **audit,
            )
            states_by_name[state.name] = state
    else:
        states_by_name = {s.name: s for s in State.objects.filter(project=project, is_triage=False)}

    # 3. labels (parents first so children can link to them)
    labels_by_name: dict[str, Label] = {}
    tpl_labels = [lbl for lbl in (data.get("labels") or []) if lbl.get("name")]
    for lbl in sorted(tpl_labels, key=lambda x: 0 if not x.get("parent") else 1):
        if lbl["name"] in labels_by_name:
            continue
        labels_by_name[lbl["name"]] = Label.objects.create(
            name=lbl["name"],
            color=lbl.get("color") or "",
            description=lbl.get("description") or "",
            sort_order=lbl.get("sort_order") or 65535,
            parent=labels_by_name.get(lbl.get("parent")) if lbl.get("parent") else None,
            **audit,
        )

    # 4. modules
    modules_by_name: dict[str, Module] = {}
    for m in data.get("modules") or []:
        if not m.get("name") or m["name"] in modules_by_name:
            continue
        modules_by_name[m["name"]] = Module.objects.create(
            name=m["name"],
            description=m.get("description") or "",
            status=m.get("status") or "planned",
            sort_order=m.get("sort_order") or 65535,
            **audit,
        )

    # 5. workflow rules (by state name; rules pointing at unknown states are skipped)
    for rule in data.get("workflow_rules") or []:
        to_state = states_by_name.get(rule.get("to_state"))
        if to_state is None:
            continue
        from_name = rule.get("from_state")
        if from_name and from_name not in states_by_name:
            continue
        WorkflowTransitionRule.objects.create(
            from_state=states_by_name.get(from_name) if from_name else None,
            to_state=to_state,
            allowed_roles=[int(r) for r in (rule.get("allowed_roles") or []) if str(r).isdigit()],
            approver_ids=[],
            description=rule.get("description") or "",
            **audit,
        )

    # 6. custom properties + work item templates
    seen_keys: set[str] = set()
    for p in data.get("custom_properties") or []:
        if not p.get("key") or p["key"] in seen_keys:
            continue
        seen_keys.add(p["key"])
        ProjectCustomProperty.objects.create(
            name=p.get("name") or p["key"],
            key=p["key"],
            property_type=p.get("property_type") or "text",
            options=p.get("options") or [],
            is_required=bool(p.get("is_required")),
            **audit,
        )
    seen_names: set[str] = set()
    for w in data.get("work_item_templates") or []:
        if not w.get("name") or w["name"] in seen_names:
            continue
        seen_names.add(w["name"])
        defaults = w.get("defaults") or {}
        # Older snapshots stored raw IDs. Resolve them only within their recorded source.
        if source_project and any(key in defaults for key in ("state_id", "label_ids", "module_ids")):
            defaults = {
                **defaults,
                **portable_defaults(
                    defaults,
                    State.objects.filter(project=source_project, is_triage=False),
                    Label.objects.filter(project=source_project),
                    Module.objects.filter(project=source_project, archived_at__isnull=True),
                ),
            }
        WorkItemTemplate.objects.create(
            name=w["name"],
            description=w.get("description") or "",
            defaults=restore_defaults(defaults, states_by_name, labels_by_name, modules_by_name),
            **audit,
        )

    # 7. starter work items
    default_state = next((s for s in states_by_name.values() if s.default), None)
    for item in (data.get("work_items") or [])[:MAX_WORK_ITEMS]:
        if not item.get("name"):
            continue
        issue = Issue(
            name=item["name"][:255],
            description_html=item.get("description_html") or "<p></p>",
            priority=item.get("priority") or "none",
            state=states_by_name.get(item.get("state")) or default_state,
            workspace=workspace,
            project=project,
        )
        issue.save(created_by_id=user.id)
        for name in item.get("labels") or []:
            if name in labels_by_name:
                IssueLabel.objects.create(issue=issue, label=labels_by_name[name], **audit)
        for name in item.get("modules") or []:
            if name in modules_by_name:
                ModuleIssue.objects.create(issue=issue, module=modules_by_name[name], **audit)
