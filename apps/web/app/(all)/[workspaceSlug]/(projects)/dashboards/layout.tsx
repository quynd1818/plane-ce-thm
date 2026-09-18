/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Outlet } from "react-router";
import { ContentWrapper } from "@/components/core/content-wrapper";

/** THM dashboards: each page renders its own AppHeader (the detail page needs actions in it). */
export default function ThmDashboardsLayout() {
  return (
    <ContentWrapper>
      <Outlet />
    </ContentWrapper>
  );
}
