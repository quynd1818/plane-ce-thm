/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useTranslation } from "@plane/i18n";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { cn } from "@plane/utils";
import type { TWorkLog } from "@/services/issue/worklog.service";

const STATUS_CLASS: Record<TWorkLog["status"], string> = {
  submitted: "bg-warning-subtle text-warning-primary border-warning-subtle",
  approved: "bg-success-subtle text-success-primary border-success-subtle",
  rejected: "bg-danger-subtle text-danger-primary border-danger-subtle",
};

type Props = { log: Pick<TWorkLog, "status" | "review_note" | "reviewed_by_detail">; className?: string };

/** THM: small pill showing a worklog's approval state; rejection reason on hover. */
export function WorklogStatusBadge({ log, className }: Props) {
  const { t } = useTranslation();
  const reviewer = log.reviewed_by_detail?.display_name ?? log.reviewed_by_detail?.email;
  const tooltip =
    log.status === "rejected" && log.review_note
      ? `${reviewer ? `${reviewer}: ` : ""}${log.review_note}`
      : reviewer
        ? `${t(`worklog_review.status.${log.status}`)} · ${reviewer}`
        : t(`worklog_review.status.${log.status}`);

  return (
    <Tooltip label={tooltip}>
      <span
        className={cn(
          "text-caption inline-flex h-5 shrink-0 items-center rounded-full border px-1.5 font-medium",
          STATUS_CLASS[log.status],
          className
        )}
      >
        {t(`worklog_review.status.${log.status}`)}
      </span>
    </Tooltip>
  );
}
