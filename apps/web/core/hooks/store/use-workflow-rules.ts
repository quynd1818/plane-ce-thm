/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useContext } from "react";
// mobx store
import { StoreContext } from "@/lib/store-context";
import type { IWorkflowRulesStore } from "@/store/workflow-rules.store";

export const useWorkflowRules = (): IWorkflowRulesStore => {
  const context = useContext(StoreContext);
  if (context === undefined) throw new Error("useWorkflowRules must be used within StoreProvider");
  return context.workflowRules;
};
