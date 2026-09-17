/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * Navy "card" shown on the left of the onboarding / auth screens.
 * Mirrors the login design from the THM handoff (theme.css) so the two
 * screens read as one flow. Colours are hard-coded on purpose: this panel
 * is always navy + gold regardless of the user's light/dark theme.
 */

import { ThmLogo } from "./thm-logo";

type Props = {
  title: string;
  /** Second, italic gold line under the title. */
  accent?: string;
  description?: string;
  /** Small uppercase strip at the bottom of the panel. */
  footer?: string;
};

const NAVY = "#0B1E3C";
const IVORY = "#F6F2EA";
const GOLD = "#D9B665";

export function ThmBrandPanel({ title, accent, description, footer }: Props) {
  return (
    <aside
      aria-hidden="true"
      className="relative hidden h-full shrink-0 flex-col justify-between overflow-hidden rounded-[28px] p-11 lg:flex lg:w-[42%] xl:w-[44%]"
      style={{
        color: IVORY,
        background: [
          "radial-gradient(640px 520px at 8% 6%, rgba(201,162,76,0.22), transparent 62%)",
          "radial-gradient(520px 420px at 100% 100%, rgba(227,203,132,0.10), transparent 60%)",
          `linear-gradient(160deg, #0F2447 0%, ${NAVY} 55%, #091A35 100%)`,
        ].join(","),
        boxShadow: "0 24px 60px rgba(11,30,60,0.22), inset 0 0 0 1px rgba(201,162,76,0.18)",
      }}
    >
      <ThmLogo height={110} className="self-start" />

      <div className="max-w-[420px]">
        <h2
          className="text-[38px] leading-[1.18] font-medium tracking-[-0.2px]"
          style={{ fontFamily: '"Playfair Display", Georgia, "Times New Roman", serif' }}
        >
          {title}
          {accent && (
            <>
              <br />
              <em style={{ color: GOLD }}>{accent}</em>
            </>
          )}
        </h2>
        {description && (
          <p
            className="mt-6 max-w-[380px] text-[14px] leading-[1.7]"
            style={{ color: "rgba(246,242,234,0.68)", fontFamily: '"Be Vietnam Pro", system-ui, sans-serif' }}
          >
            {description}
          </p>
        )}
      </div>

      {footer && (
        <div
          className="pt-4 text-[11px] tracking-[1.2px] uppercase"
          style={{ color: "rgba(246,242,234,0.48)", borderTop: "1px solid rgba(201,162,76,0.28)" }}
        >
          {footer}
        </div>
      )}
    </aside>
  );
}
