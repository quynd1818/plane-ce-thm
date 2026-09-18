/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { InitiativeOutline } from "@makeplane/propel/icons";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Breadcrumbs, Header } from "@plane/ui";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";

type Props = { workspaceSlug?: string; initiativeName?: string; rightItem?: React.ReactNode };

export const ThmInitiativesHeader = observer(function ThmInitiativesHeader({
  workspaceSlug,
  initiativeName,
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
                label={t("thm_initiatives.label")}
                href={workspaceSlug && initiativeName ? `/${workspaceSlug}/initiatives/` : undefined}
                icon={<InitiativeOutline className="h-4 w-4 text-tertiary" />}
              />
            }
          />
          {initiativeName && <Breadcrumbs.Item component={<BreadcrumbLink label={initiativeName} />} />}
        </Breadcrumbs>
      </Header.LeftItem>
      {rightItem && <Header.RightItem className="items-center gap-2">{rightItem}</Header.RightItem>}
    </Header>
  );
});
