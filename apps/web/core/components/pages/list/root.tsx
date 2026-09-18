/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { pageTreeRows } from "@/helpers/page-hierarchy";
import { observer } from "mobx-react";
// types
import type { TPageNavigationTabs } from "@plane/types";
// components
import { ListLayout } from "@/components/core/list";
// plane web hooks
import type { EPageStoreType } from "@/hooks/store";
import { usePageStore } from "@/hooks/store";
// local imports
import { PageListBlock } from "./block";

type TPagesListRoot = {
  pageType: TPageNavigationTabs;
  storeType: EPageStoreType;
};

export const PagesListRoot = observer(function PagesListRoot(props: TPagesListRoot) {
  const { pageType, storeType } = props;
  // store hooks
  const [collapsed, setCollapsed] = useState(new Set<string>());
  const { getCurrentProjectFilteredPageIdsByTab, getPageById } = usePageStore(storeType);
  // derived values
  const filteredPageIds = getCurrentProjectFilteredPageIdsByTab(pageType);

  if (!filteredPageIds) return <></>;
  return (
    <ListLayout>
      {pageTreeRows(
        filteredPageIds.map((id) => ({ id, parent: getPageById(id)?.parent })),
        collapsed
      ).map((row) => (
        <div key={row.id} className="flex items-center" style={{ paddingLeft: Math.min(row.depth, 12) * 20 }}>
          <button
            type="button"
            className="w-6 shrink-0 text-tertiary"
            aria-label={`${collapsed.has(row.id) ? "Expand" : "Collapse"} ${getPageById(row.id)?.name || "Untitled"}`}
            aria-expanded={row.hasChildren ? !collapsed.has(row.id) : undefined}
            disabled={!row.hasChildren}
            onClick={() =>
              setCollapsed((previous) => {
                const next = new Set(previous);
                if (next.has(row.id)) next.delete(row.id);
                else next.add(row.id);
                return next;
              })
            }
          >
            {row.hasChildren ? (collapsed.has(row.id) ? "▸" : "▾") : ""}
          </button>
          <div className="min-w-0 flex-1">
            <PageListBlock pageId={row.id} storeType={storeType} />
          </div>
        </div>
      ))}
    </ListLayout>
  );
});
