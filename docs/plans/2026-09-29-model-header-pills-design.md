# Model header

The approved design replaces three rows of pills with two groups: reference,
GitHub, and Compare actions in one wrapping row, followed by a compact metadata
strip. Contributor attribution shares the action row with the reference, GitHub, and
Compare controls. The row wraps on small screens.

Metadata uses layer-stack, sliders, expand, graduation-cap, and scales icons for
architecture, parameters, input, supervision, and license. Values stay visible;
parameters and input retain short text labels, and code/weights license scopes
remain explicit. Screen-reader labels identify the other values, decorative
icons are hidden from assistive technology, and links retain keyboard focus.

Use one pale background behind the strip instead of individual pill backgrounds.
Wrap naturally on mobile. Preserve concise license mappings and links to full
details. Verify desktop/mobile rendering, separate code and weights licenses,
anchor targets, and horizontal overflow.
