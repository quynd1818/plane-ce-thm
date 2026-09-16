/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useCallback, useEffect, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import type {
  ISearchIssueResponse,
  TIssue,
  TIssuePropertyValueErrors,
  TIssuePropertyValues,
} from "@plane/types";
// components
import { IssueModalContext } from "@/components/issues/issue-modal/context";
// hooks
import { useUser } from "@/hooks/store/user/user-user";
import { projectCustomizationService, type TCustomProperty, type TWorkItemTemplate } from "@/services/project/customization.service";

export type TIssueModalProviderProps = {
  templateId?: string;
  dataForPreload?: Partial<TIssue>;
  allowedProjectIds?: string[];
  children: React.ReactNode;
};

export const IssueModalProvider = observer(function IssueModalProvider(props: TIssueModalProviderProps) {
  const { children, allowedProjectIds, dataForPreload, templateId } = props;
  const { workspaceSlug, projectId: routeProjectId } = useParams();
  // states
  const [selectedParentIssue, setSelectedParentIssue] = useState<ISearchIssueResponse | null>(null);
  const [workItemTemplateId, setWorkItemTemplateId] = useState<string | null>(templateId ?? null);
  const [isApplyingTemplate, setIsApplyingTemplate] = useState(false);
  const preloadedCustomProperties = (
    dataForPreload as Partial<TIssue> & { custom_properties?: TIssuePropertyValues }
  )?.custom_properties;
  const [issuePropertyValues, setIssuePropertyValues] = useState<TIssuePropertyValues>(
    preloadedCustomProperties ?? {}
  );
  const [issuePropertyValueErrors, setIssuePropertyValueErrors] = useState<TIssuePropertyValueErrors>({});
  const [customPropertyDefinitions, setCustomPropertyDefinitions] = useState<TCustomProperty[]>([]);
  const [workItemTemplates, setWorkItemTemplates] = useState<TWorkItemTemplate[]>([]);
  const projectId = dataForPreload?.project_id ?? routeProjectId?.toString();

  const handleProjectEntitiesFetch = useCallback(
    async ({ workItemProjectId, workspaceSlug: slug }: { workItemProjectId: string | null | undefined; workspaceSlug: string }) => {
      if (!workItemProjectId) return;
      const [definitions, templates] = await Promise.all([
        projectCustomizationService.listProperties(slug, workItemProjectId),
        projectCustomizationService.listTemplates(slug, workItemProjectId),
      ]);
      setCustomPropertyDefinitions(definitions);
      setWorkItemTemplates(templates);
    },
    []
  );

  useEffect(() => {
    if (workspaceSlug && projectId) {
      void handleProjectEntitiesFetch({
        workItemProjectId: projectId.toString(),
        workspaceSlug: workspaceSlug.toString(),
      });
    }
  }, [handleProjectEntitiesFetch, projectId, workspaceSlug]);
  // store hooks
  const { projectsWithCreatePermissions } = useUser();
  // derived values
  const projectIdsWithCreatePermissions = Object.keys(projectsWithCreatePermissions ?? {});

  return (
    <IssueModalContext.Provider
      // oxlint-disable-next-line react/jsx-no-constructed-context-values
      value={{
        allowedProjectIds: allowedProjectIds ?? projectIdsWithCreatePermissions,
        workItemTemplateId,
        setWorkItemTemplateId,
        isApplyingTemplate,
        setIsApplyingTemplate,
        selectedParentIssue,
        setSelectedParentIssue,
        issuePropertyValues,
        setIssuePropertyValues,
        issuePropertyValueErrors,
        setIssuePropertyValueErrors,
        customPropertyDefinitions,
        workItemTemplates,
        getIssueTypeIdOnProjectChange: () => null,
        getActiveAdditionalPropertiesLength: () => customPropertyDefinitions.length,
        handlePropertyValuesValidation: ({ projectId: validationProjectId }) => {
          if (!validationProjectId) return true;
          const missing = customPropertyDefinitions
            .filter((definition) => definition.is_required && issuePropertyValues[definition.key] == null)
            .map((definition) => definition.key);
          setIssuePropertyValueErrors(
            Object.fromEntries(missing.map((key) => [key, "This field is required."]))
          );
          return missing.length === 0;
        },
        handleCreateUpdatePropertyValues: () => Promise.resolve(),
        handleProjectEntitiesFetch,
        handleTemplateChange: async ({ reset }) => {
          if (!workItemTemplateId) return;
          const template = workItemTemplates.find((item) => item.id === workItemTemplateId);
          if (!template) return;
          setIsApplyingTemplate(true);
          const defaults = template.defaults;
          const customProperties =
            (defaults.custom_properties as Record<string, unknown> | undefined) ?? issuePropertyValues;
          setIssuePropertyValues(customProperties);
          reset((currentValues) => ({
            ...currentValues,
            ...defaults,
            project_id: projectId,
            custom_properties: customProperties,
          }));
          setIsApplyingTemplate(false);
        },
        handleConvert: () => Promise.resolve(),
        handleCreateSubWorkItem: () => Promise.resolve(),
      }}
    >
      {children}
    </IssueModalContext.Provider>
  );
});
