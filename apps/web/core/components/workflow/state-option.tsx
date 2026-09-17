/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { Combobox } from "@headlessui/react";
import { LockOutline, TickOutline } from "@makeplane/propel/icons";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { cn } from "@plane/utils";
// hooks
import { useWorkflowRules } from "@/hooks/store/use-workflow-rules";

export type TStateOptionProps = {
  projectId: string | null | undefined;
  option: {
    value: string | undefined;
    query: string;
    content: React.ReactNode;
  };
  selectedValue: string | null | undefined;
  className?: string;
  filterAvailableStateIds?: boolean;
  isForWorkItemCreation?: boolean;
  alwaysAllowStateChange?: boolean;
};

/**
 * One state in the state dropdown. THM: when the project has workflow rules,
 * transitions the current user may not perform are shown locked with the
 * reason instead of silently failing on save.
 */
export const StateOption = observer(function StateOption(props: TStateOptionProps) {
  const { option, className = "", projectId, selectedValue, isForWorkItemCreation, alwaysAllowStateChange } = props;
  // router
  const { workspaceSlug } = useParams();
  // store hooks
  const { isTransitionAllowed } = useWorkflowRules();
  // derived values — creation has no "from" state, and callers may opt out
  const decision =
    isForWorkItemCreation || alwaysAllowStateChange
      ? { allowed: true }
      : isTransitionAllowed(workspaceSlug?.toString(), projectId, selectedValue, option.value);
  const isLocked = !decision.allowed;

  return (
    <Combobox.Option
      as="li"
      key={option.value}
      value={option.value}
      disabled={isLocked}
      className={({ active, selected }) =>
        cn(
          `${className} ${active && !isLocked ? "bg-layer-transparent-hover" : ""} ${selected ? "text-primary" : "text-secondary"}`,
          isLocked && "cursor-not-allowed opacity-60"
        )
      }
    >
      {({ selected }) => (
        <>
          <span className="flex-grow truncate">{option.content}</span>
          {selected && <TickOutline className="h-3.5 w-3.5 flex-shrink-0" />}
          {isLocked && (
            <Tooltip label={decision.reason ?? ""} side="right">
              <span className="flex-shrink-0">
                <LockOutline className="h-3.5 w-3.5 text-placeholder" />
              </span>
            </Tooltip>
          )}
        </>
      )}
    </Combobox.Option>
  );
});
