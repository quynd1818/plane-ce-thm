/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { isEmpty } from "lodash-es";
import Link from "next/link";
import { Controller, useForm } from "react-hook-form";
// plane internal packages
import { API_BASE_URL } from "@plane/constants";
import { Button } from "@makeplane/propel/components/button";
import { Switch } from "@makeplane/propel/components/switch";
import { TOAST_TYPE, setToast } from "@/providers/toast";
import type { IFormattedInstanceConfiguration, TInstanceKeycloakAuthenticationConfigurationKeys } from "@plane/types";
// components
import { CodeBlock } from "@/components/common/code-block";
import { ConfirmDiscardModal } from "@/components/common/confirm-discard-modal";
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerInput } from "@/components/common/controller-input";
import type { TCopyField } from "@/components/common/copy-field";
import { CopyField } from "@/components/common/copy-field";
// hooks
import { useInstance } from "@/hooks/store";

type Props = {
  config: IFormattedInstanceConfiguration;
};

type KeycloakConfigFormValues = Record<TInstanceKeycloakAuthenticationConfigurationKeys, string>;

const DEFAULT_KEYCLOAK_HOST = "https://sso.tanhoangminh.com.vn/realms/cds-tanhoangminh";

export function InstanceKeycloakConfigForm(props: Props) {
  const { config } = props;
  // states
  const [isDiscardChangesModalOpen, setIsDiscardChangesModalOpen] = useState(false);
  // store hooks
  const { updateInstanceConfigurations } = useInstance();
  // form data
  const {
    handleSubmit,
    control,
    reset,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<KeycloakConfigFormValues>({
    defaultValues: {
      KEYCLOAK_HOST: config["KEYCLOAK_HOST"] || DEFAULT_KEYCLOAK_HOST,
      KEYCLOAK_CLIENT_ID: config["KEYCLOAK_CLIENT_ID"],
      KEYCLOAK_CLIENT_SECRET: config["KEYCLOAK_CLIENT_SECRET"],
      KEYCLOAK_REQUIRE_VERIFIED_EMAIL: config["KEYCLOAK_REQUIRE_VERIFIED_EMAIL"] || "1",
    },
  });

  const originURL = !isEmpty(API_BASE_URL) ? API_BASE_URL : typeof window !== "undefined" ? window.location.origin : "";

  const KEYCLOAK_FORM_FIELDS: TControllerInputFormField<KeycloakConfigFormValues>[] = [
    {
      key: "KEYCLOAK_HOST",
      type: "text",
      label: "Realm URL",
      description: (
        <>
          The full URL of the Keycloak realm, e.g.{" "}
          <CodeBlock darkerShade>https://&lt;keycloak-host&gt;/realms/&lt;realm&gt;</CodeBlock>. Plane appends{" "}
          <CodeBlock darkerShade>/protocol/openid-connect/...</CodeBlock> to it.
        </>
      ),
      placeholder: DEFAULT_KEYCLOAK_HOST,
      error: Boolean(errors.KEYCLOAK_HOST),
      required: true,
    },
    {
      key: "KEYCLOAK_CLIENT_ID",
      type: "text",
      label: "Client ID",
      description: <>The client ID of the OIDC client created for Plane in the Keycloak realm.</>,
      placeholder: "plane",
      error: Boolean(errors.KEYCLOAK_CLIENT_ID),
      required: true,
    },
    {
      key: "KEYCLOAK_CLIENT_SECRET",
      type: "password",
      label: "Client secret",
      description: <>Found under the client&apos;s &quot;Credentials&quot; tab in the Keycloak admin console.</>,
      placeholder: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      error: Boolean(errors.KEYCLOAK_CLIENT_SECRET),
      required: true,
    },
  ];

  const KEYCLOAK_SERVICE_FIELD: TCopyField[] = [
    {
      key: "Callback_URI",
      label: "Callback URI",
      url: `${originURL}/auth/keycloak/callback/`,
      description: (
        <>
          Add this to the client&apos;s <CodeBlock darkerShade>Valid redirect URIs</CodeBlock> in Keycloak.
        </>
      ),
    },
    {
      key: "Space_Callback_URI",
      label: "Callback URI (public spaces)",
      url: `${originURL}/auth/spaces/keycloak/callback/`,
      description: <>Also add this one so members can sign in from public project pages.</>,
    },
  ];

  const onSubmit = async (formData: KeycloakConfigFormValues) => {
    const payload: Partial<KeycloakConfigFormValues> = { ...formData };

    try {
      const response = await updateInstanceConfigurations(payload);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Done!",
        message: "Your THM SSO authentication is configured. You should test it now.",
      });
      reset({
        KEYCLOAK_HOST: response.find((item) => item.key === "KEYCLOAK_HOST")?.value,
        KEYCLOAK_CLIENT_ID: response.find((item) => item.key === "KEYCLOAK_CLIENT_ID")?.value,
        KEYCLOAK_CLIENT_SECRET: response.find((item) => item.key === "KEYCLOAK_CLIENT_SECRET")?.value,
        KEYCLOAK_REQUIRE_VERIFIED_EMAIL: response.find((item) => item.key === "KEYCLOAK_REQUIRE_VERIFIED_EMAIL")?.value,
      });
    } catch (err) {
      console.error(err);
    }
  };

  const handleGoBack = (e: React.MouseEvent<HTMLAnchorElement, MouseEvent>) => {
    if (isDirty) {
      e.preventDefault();
      setIsDiscardChangesModalOpen(true);
    }
  };

  return (
    <>
      <ConfirmDiscardModal
        isOpen={isDiscardChangesModalOpen}
        onDiscardHref="/authentication"
        handleClose={() => setIsDiscardChangesModalOpen(false)}
      />
      <div className="flex flex-col gap-8">
        <div className="grid w-full grid-cols-2 gap-x-12 gap-y-8">
          <div className="col-span-2 flex flex-col gap-y-4 pt-1 md:col-span-1">
            <div className="pt-2.5 text-18 font-medium">Keycloak-provided details for Plane</div>
            {KEYCLOAK_FORM_FIELDS.map((field) => (
              <ControllerInput
                key={field.key}
                control={control}
                type={field.type}
                name={field.key}
                label={field.label}
                description={field.description}
                placeholder={field.placeholder}
                error={field.error}
                required={field.required}
              />
            ))}
            <div className="flex items-start justify-between gap-4">
              <div className="flex flex-col gap-1">
                <h4 className="text-13 font-medium text-tertiary">Require verified email</h4>
                <p className="text-11 text-tertiary">
                  Reject sign-ins whose Keycloak profile has <CodeBlock darkerShade>email_verified: false</CodeBlock>.
                  Turn off when accounts are provisioned from AD/LDAP and the flag is never set.
                </p>
              </div>
              <Controller
                control={control}
                name="KEYCLOAK_REQUIRE_VERIFIED_EMAIL"
                render={({ field: { value, onChange } }) => (
                  <Switch
                    checked={value === "1"}
                    onCheckedChange={() => onChange(value === "1" ? "0" : "1")}
                    size="sm"
                  />
                )}
              />
            </div>
            <div className="flex flex-col gap-1 pt-4">
              <div className="flex items-center gap-4">
                <Button
                  variant="primary"
                  size="md"
                  stretch="auto"
                  onClick={(e) => void handleSubmit(onSubmit)(e)}
                  loading={isSubmitting}
                  disabled={!isDirty}
                  label={isSubmitting ? "Saving" : "Save changes"}
                />
                <Button
                  variant="secondary"
                  size="md"
                  stretch="auto"
                  nativeButton={false}
                  render={<Link href="/authentication" onClick={handleGoBack} />}
                  label="Go back"
                />
              </div>
            </div>
          </div>
          <div className="col-span-2 md:col-span-1">
            <div className="flex flex-col gap-y-4 rounded-lg bg-layer-1 px-6 pt-1.5 pb-4">
              <div className="pt-2 text-18 font-medium">Plane-provided details for Keycloak</div>
              {KEYCLOAK_SERVICE_FIELD.map((field) => (
                <CopyField key={field.key} label={field.label} url={field.url} description={field.description} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
