/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { DashboardsOutline } from "@makeplane/propel/icons";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Breadcrumbs, Header } from "@plane/ui";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";

type Props = { workspaceSlug?: string; dashboardName?: string; rightItem?: React.ReactNode };

/** THM dashboards header (list + detail). */
export const ThmDashboardsHeader = observer(function ThmDashboardsHeader({
  workspaceSlug,
  dashboardName,
  rightItem,
}: Props) {
  const { t } = useTranslation();
  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                label={t("thm_dashboards.label")}
                href={workspaceSlug && dashboardName ? `/${workspaceSlug}/dashboards/` : undefined}
                icon={<DashboardsOutline className="h-4 w-4 text-tertiary" />}
              />
            }
          />
          {dashboardName && <Breadcrumbs.Item component={<BreadcrumbLink label={dashboardName} />} />}
        </Breadcrumbs>
      </Header.LeftItem>
      {rightItem && <Header.RightItem className="items-center gap-2">{rightItem}</Header.RightItem>}
    </Header>
  );
});
