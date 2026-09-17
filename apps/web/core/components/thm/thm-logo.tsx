/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * Tân Hoàng Minh brand mark — replaces PlaneLockup on the screens the fork owns.
 */

import { cn } from "@plane/utils";
// assets
import thmLogo from "@/app/assets/logos/thm-logo.png?url";

type Props = {
  /** Rendered height in px; width follows the 302×184 source ratio. */
  height?: number;
  className?: string;
};

export function ThmLogo({ height = 44, className }: Props) {
  return (
    <img
      src={thmLogo}
      alt="Tân Hoàng Minh Group"
      height={height}
      style={{ height, width: "auto" }}
      className={cn("object-contain select-none", className)}
      draggable={false}
    />
  );
}
