/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * Navy "card" shown on the left of the onboarding / auth screens.
 * Mirrors the login design from the THM handoff (theme.css, v13 red) so the
 * two screens read as one flow. Colours are hard-coded on purpose: this panel
 * is always deep red + gold regardless of the user's light/dark theme.
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

// THM palette (theme.css v13 "khung đỏ đậm"): deep red gradient + antique gold
const RED_DARK = "#3E0810";
const IVORY = "#FFF7F2";
const GOLD = "#E3CB84";

export function ThmBrandPanel({ title, accent, description, footer }: Props) {
  return (
    <aside
      aria-hidden="true"
      className="relative hidden h-full shrink-0 flex-col justify-between overflow-hidden rounded-[28px] p-11 lg:flex lg:w-[calc(50vw-33px)]"
      style={{
        color: IVORY,
        background: [
          "radial-gradient(640px 520px at 8% 6%, rgba(201,162,76,0.22), transparent 62%)",
          "radial-gradient(520px 420px at 100% 100%, rgba(0,0,0,0.20), transparent 60%)",
          `linear-gradient(160deg, #7A1020 0%, #5A0B17 55%, ${RED_DARK} 100%)`,
        ].join(","),
        boxShadow: "0 24px 60px rgba(62,8,16,0.30), inset 0 0 0 1px rgba(201,162,76,0.25)",
      }}
    >
      <ThmLogo height={110} className="self-start" />

      <div className="max-w-[460px]">
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
            className="mt-6 max-w-[380px] text-[14px] leading-[1.7] font-medium"
            style={{ color: "rgba(255,247,242,0.75)", fontFamily: '"Be Vietnam Pro", system-ui, sans-serif' }}
          >
            {description}
          </p>
        )}
      </div>

      {footer && (
        <div
          className="pt-4 text-[11px] tracking-[1.2px] uppercase"
          style={{ color: "rgba(255,247,242,0.55)", borderTop: "1px solid rgba(201,162,76,0.35)" }}
        >
          {footer}
        </div>
      )}
    </aside>
  );
}
