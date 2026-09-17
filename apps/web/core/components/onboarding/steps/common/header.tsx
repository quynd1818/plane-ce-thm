/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

type Props = {
  title: string;
  description: string;
};

export function CommonOnboardingHeader({ title, description }: Props) {
  return (
    <div className="space-y-3 text-left">
      <div className="h-[3px] w-10 rounded-full" style={{ background: "#C9A24C" }} />
      <h1
        className="text-[28px] leading-[1.2] font-semibold text-primary"
        style={{ fontFamily: '"Playfair Display", Georgia, "Times New Roman", serif' }}
      >
        {title}
      </h1>
      <p className="text-body-md-regular text-tertiary">{description}</p>
    </div>
  );
}
