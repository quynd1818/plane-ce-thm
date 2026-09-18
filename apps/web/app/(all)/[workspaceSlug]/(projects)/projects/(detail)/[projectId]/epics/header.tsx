/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { EpicOutline } from "@makeplane/propel/icons";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Breadcrumbs, Header } from "@plane/ui";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { CommonProjectBreadcrumbs } from "@/components/breadcrumbs/common";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useAppRouter } from "@/hooks/use-app-router";

type Props = { workspaceSlug: string; projectId: string; rightItem?: React.ReactNode };

export const ProjectEpicsHeader = observer(function ProjectEpicsHeader({ workspaceSlug, projectId, rightItem }: Props) {
  const router = useAppRouter();
  const { t } = useTranslation();
  const { loader } = useProject();
  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs onBack={router.back} isLoading={loader === "init-loader"}>
          <CommonProjectBreadcrumbs workspaceSlug={workspaceSlug} projectId={projectId} />
          <Breadcrumbs.Item
            component={
              <BreadcrumbLink
                label={t("sidebar.epics")}
                href={`/${workspaceSlug}/projects/${projectId}/epics/`}
                icon={<EpicOutline className="h-4 w-4 text-tertiary" />}
                isLast
              />
            }
            isLast
          />
        </Breadcrumbs>
      </Header.LeftItem>
      {rightItem && <Header.RightItem className="items-center gap-2">{rightItem}</Header.RightItem>}
    </Header>
  );
});
