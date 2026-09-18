import { useState } from "react";
import { observer } from "mobx-react";
import { Link } from "react-router";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { getPageName } from "@plane/utils";
import { descendantPageIds } from "@/helpers/page-hierarchy";
import { usePageStore, type EPageStoreType } from "@/hooks/store";
import type { TPageInstance } from "@/store/pages/base-page";
import { CreatePageModal } from "../modals/create-page-modal";

type Props = { page: TPageInstance; storeType: EPageStoreType; projectId: string; workspaceSlug: string };

export const PageHierarchy = observer(function PageHierarchy({ page, storeType, projectId, workspaceSlug }: Props) {
  const [creating, setCreating] = useState(false);
  const [moving, setMoving] = useState(false);
  const store = usePageStore(storeType);
  const { data, error, mutate } = useSWR(["PAGE_HIERARCHY", workspaceSlug, projectId], () =>
    store.fetchPagesList(workspaceSlug, projectId)
  );
  const pages = (data ?? []).flatMap(({ id }) => {
    const item = id ? store.getPageById(id) : undefined;
    return item ? [item] : [];
  });
  const excluded = descendantPageIds(pages, page.id ?? "");
  const choices = pages.filter((item) => item.id && !excluded.has(item.id) && !item.archived_at && !item.is_locked);
  const ancestors: TPageInstance[] = [];
  const seen = new Set([page.id]);
  const visiblePages = new Map(pages.map((item) => [item.id, item]));
  let parent = page.parent ? visiblePages.get(page.parent) : undefined;
  while (parent?.id && !seen.has(parent.id)) {
    seen.add(parent.id);
    ancestors.unshift(parent);
    parent = parent.parent ? visiblePages.get(parent.parent) : undefined;
  }
  const changeParent = async (value: string) => {
    setMoving(true);
    try {
      await page.update({ parent: value || null });
      await mutate();
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Cannot move page", message: "Check the parent page and try again." });
    } finally {
      setMoving(false);
    }
  };
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-subtle px-6 py-2 text-13">
      <nav aria-label="Page hierarchy" className="flex min-w-0 flex-wrap items-center gap-2">
        <Link to={`/${workspaceSlug}/projects/${projectId}/pages/`}>Pages</Link>
        {ancestors.map((ancestor) => (
          <span key={ancestor.id}>
            {" "}
            / <Link to={ancestor.getRedirectionLink()}>{getPageName(ancestor.name)}</Link>
          </span>
        ))}
        <span aria-current="page"> / {getPageName(page.name)}</span>
      </nav>
      {error && (
        <button type="button" onClick={() => void mutate()}>
          Cannot load page hierarchy. Retry
        </button>
      )}
      {page.isContentEditable && store.canCurrentUserCreatePage && (
        <div className="flex items-center gap-3">
          <label title="Moving a page does not change its public/private access." className="flex items-center gap-2">
            Parent page
            <select
              aria-label="Parent page"
              className="max-w-48 rounded border border-subtle bg-surface-1 p-1"
              value={page.parent ?? ""}
              disabled={moving || !data || !!error}
              onChange={(event) => void changeParent(event.target.value)}
            >
              <option value="">No parent (top level)</option>
              {page.parent && !choices.some((item) => item.id === page.parent) && (
                <option value={page.parent}>Current parent unavailable</option>
              )}
              {choices.map((item) => (
                <option key={item.id} value={item.id}>
                  {getPageName(item.name)}
                </option>
              ))}
            </select>
          </label>
          <Button variant="secondary" size="sm" onClick={() => setCreating(true)}>
            Add subpage
          </Button>
        </div>
      )}
      <CreatePageModal
        workspaceSlug={workspaceSlug}
        projectId={projectId}
        parentId={page.id}
        pageAccess={page.access}
        isModalOpen={creating}
        handleModalClose={() => setCreating(false)}
        redirectionEnabled
        storeType={storeType}
      />
    </div>
  );
});
