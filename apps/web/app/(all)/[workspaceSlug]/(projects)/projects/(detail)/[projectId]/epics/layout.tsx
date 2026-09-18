/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Outlet } from "react-router";
import { ContentWrapper } from "@/components/core/content-wrapper";

/** THM epics: the page renders its own AppHeader (it needs the create action). */
export default function ProjectEpicsLayout() {
  return (
    <ContentWrapper>
      <Outlet />
    </ContentWrapper>
  );
}
