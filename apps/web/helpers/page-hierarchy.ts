export type HierarchyPage = { id?: string; parent?: string | null };

/** Traverse only pages returned by the authorized, filtered API/store. */
export function pageTreeRows(pages: HierarchyPage[], collapsed = new Set<string>()) {
  const ids = new Set(pages.map((page) => page.id));
  const children = new Map<string | null, HierarchyPage[]>();
  for (const page of pages) {
    const parent = page.parent && ids.has(page.parent) ? page.parent : null;
    children.set(parent, [...(children.get(parent) ?? []), page]);
  }
  const rows: { id: string; depth: number; hasChildren: boolean }[] = [];
  const visited = new Set<string>();
  const walk = (page: HierarchyPage, depth: number, hidden = false) => {
    if (!page.id || visited.has(page.id)) return;
    visited.add(page.id);
    const descendants = children.get(page.id) ?? [];
    if (!hidden) rows.push({ id: page.id, depth, hasChildren: descendants.length > 0 });
    for (const child of descendants) walk(child, depth + 1, hidden || collapsed.has(page.id));
  };
  for (const page of children.get(null) ?? []) walk(page, 0);
  // Defensive fallback for legacy cyclic data.
  for (const page of pages) if (page.id && !visited.has(page.id)) walk(page, 0);
  return rows;
}

export function descendantPageIds(pages: HierarchyPage[], pageId: string) {
  const result = new Set<string>([pageId]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const page of pages) {
      if (page.id && page.parent && result.has(page.parent) && !result.has(page.id)) {
        result.add(page.id);
        changed = true;
      }
    }
  }
  return result;
}
