/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useTranslation } from "@plane/i18n";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import type { TThmRollup } from "@plane/types";
import { cn } from "@plane/utils";

const SEGMENTS: { key: keyof TThmRollup; color: string }[] = [
  { key: "completed", color: "#16a34a" },
  { key: "started", color: "#f59e0b" },
  { key: "unstarted", color: "#3b82f6" },
  { key: "backlog", color: "#a3a3a3" },
  { key: "cancelled", color: "#ef4444" },
];

type Props = { rollup: TThmRollup; className?: string; showNumbers?: boolean };

/** THM: stacked progress bar for an epic / initiative rollup. */
export function ThmRollupBar({ rollup, className, showNumbers = true }: Props) {
  const { t } = useTranslation();
  const total = rollup.total || 0;
  const tooltip = SEGMENTS.map((s) => `${t(`thm_epics.state_group.${String(s.key)}`)}: ${rollup[s.key]}`).join(" · ");
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <Tooltip label={tooltip}>
        <div className="flex h-2 w-full min-w-24 overflow-hidden rounded-full bg-layer-2">
          {total > 0 &&
            SEGMENTS.map((s) => {
              const value = rollup[s.key] as number;
              if (!value) return null;
              return (
                <span
                  key={String(s.key)}
                  style={{ width: `${(value / total) * 100}%`, backgroundColor: s.color }}
                  className="h-full"
                />
              );
            })}
        </div>
      </Tooltip>
      {showNumbers && (
        <span className="text-caption shrink-0 text-tertiary tabular-nums">
          {rollup.completed}/{total} · {rollup.progress}%
          {rollup.overdue > 0 && (
            <span className="ml-1 text-danger-primary">
              · {t("thm_epics.overdue_count", { count: rollup.overdue })}
            </span>
          )}
        </span>
      )}
    </div>
  );
}
