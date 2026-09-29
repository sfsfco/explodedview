---
name: explodedview
description: Transform the provided technical drawing, engineering drawing, CAD screenshot, product image, assembly drawing, or equipment photograph into a clear and professional EXPLODED VIEW / EXPLODED ASSEMBLY illustration. Use this skill when the user supplies an assembly image and asks to explode it, separate its parts, show how it comes apart, or produce an assembly breakdown. Do not use it to read, interpret or explain a drawing when no illustration is requested.
---

# Exploded View Autopilot

## FUNCTION

Transform the provided technical drawing, engineering drawing, CAD screenshot, product image, assembly drawing, or equipment photograph into a clear and professional EXPLODED VIEW / EXPLODED ASSEMBLY illustration.

## OBJECTIVE

Create a visually separated representation of the assembly where the major components are pulled apart along their natural assembly axes while maintaining their correct relative position, orientation, proportions, and assembly relationship.

The exploded view must help an engineer, technician, manufacturer, or client understand:

1. What components make up the assembly.
2. How the components fit together.
3. The approximate assembly order.
4. Where each component belongs.
5. Which components are removable or independently manufactured.

## INPUT ANALYSIS

First analyze the provided image carefully.

Identify:

- Main assembly
- Individual components
- Subassemblies
- Fasteners
- Mounting components
- Covers
- Frames
- Structural members
- Pipes and fittings
- Nozzles
- Ladders and guards
- Electrical/mechanical components
- Any other clearly identifiable parts

Use the original drawing as the primary source of truth.

## ENGINEERING ACCURACY

- Preserve the geometry shown in the source drawing.
- Preserve the original orientation of components.
- Preserve relative dimensions and proportions as much as possible.
- Preserve holes, flanges, nozzles, brackets, supports, bolts, weldments, and other visible details.
- Do NOT invent components that are not reasonably supported by the source.
- Do NOT change the function or geometry of the equipment.
- Do NOT arbitrarily redesign the product.
- If a component cannot be determined confidently, keep it visually consistent with the source rather than inventing detailed geometry.
- Do not treat decorative elements as engineering components unless they are present in the source.

## EXPLOSION LOGIC

Separate the components from the assembled position using realistic assembly directions.

Typically:

- Vertical components move vertically.
- Covers and roofs move upward.
- Bottom plates move downward.
- Bolted/flanged components move along their bolt axis.
- Side-mounted components move horizontally away from the main body.
- Ladders, guards, brackets and external accessories move outward from their mounting surfaces.
- Fasteners may be separated slightly from the component they secure.

Use dashed centerlines, alignment lines, or subtle exploded-assembly guide lines where useful to show how components return to their original positions.

Do not randomly scatter components.

The exploded components must remain visually aligned with the original assembly.

## VISUAL STYLE

Create a professional engineering/industrial exploded-view illustration.

Preferred appearance:

- Clean white or very light background.
- High-quality technical product visualization.
- Realistic but controlled 3D CAD/product-rendering appearance.
- Clear metallic materials where appropriate.
- Consistent lighting.
- Sharp edges and readable component boundaries.
- Minimal visual clutter.
- Professional engineering documentation aesthetic.

The result should look similar to a combination of:

- Engineering exploded assembly drawing
- Technical product illustration
- CAD assembly presentation
- Manufacturing documentation

## LAYOUT

Use a logical composition.

Preferred layout:

- Exploded assembly as the main focus.
- Fully assembled reference view may be shown to one side when useful.
- Components should have sufficient spacing to clearly distinguish them.
- Avoid overlapping components unnecessarily.
- Maintain clear visual hierarchy.

## LABELING

Image generators render baked-in text unreliably and frequently emit garbled letter-like glyphs instead of real characters. Choose deliberately:

- **Default:** instruct the generator to produce no text at all, then deliver the numbered parts list as a markdown table in your reply.
- **Alternative:** accept callouts in the image, then read them back and verify them before showing the result.

Never omit labels from the prompt and then describe an image as though they exist.

Do not add technical specifications that are not present in the source.

If the source contains dimensions, materials, thicknesses, capacities, or other engineering information, preserve them accurately when displaying them.

## PARTS LIST

When useful, create a parts list containing:

| No. | Part Name | Description | Qty. |
|-----|-----------|-------------|------|

Only include information that can reasonably be determined from the source.

Do not invent quantities or specifications.

## DIMENSIONS

If dimensions are visible in the source:

- Preserve important dimensions.
- Do not alter numerical values.
- Do not replace engineering dimensions with estimated values.
- If a dimension is unclear, omit it rather than guessing.

## TECHNICAL DRAWING PRESERVATION

If the input is an engineering drawing containing multiple views:

- Use all relevant views to understand the object.
- Cross-reference front, side, top, section and detail views.
- Use section views to understand hidden/internal geometry.
- Use dimensions and notes to resolve component relationships.
- Do not rely only on the 3D perspective view if orthographic views provide more accurate information.

## FOR INDUSTRIAL EQUIPMENT

Pay particular attention to:

- Tank shell
- Roof
- Bottom
- Skid/base
- Structural supports
- Ladders
- Handrails
- Safety cages
- Nozzles
- Flanges
- Manholes
- Valves
- Brackets
- Anchor points
- Lifting points
- Bolts and fasteners
- Piping connections

---

# PRODUCTION

Everything above is host-agnostic. This section is where the illustration is actually made.

**Describing the illustration is not producing it.** Call a generator, then show the returned image to the user. A written description is not a deliverable.

## Step 1 — Build the prompt

Assemble the prompt from the sections above. It must state:

- The components, in explosion order.
- The direction each component travels.
- The exact colours and materials to preserve from the source.
- Explicitly: no text, no labels, no callouts, no watermarks in the image.
- The visual style and background.

**Write the prompt to a file. Never inline it into a shell command.** Long prompts contain quotes, commas, colons and newlines; inlining them is the single most common cause of a failed generation. Use `prompt.txt` or `prompt.json`.

## Step 2 — Prepare the source image

Most providers take reference images as HTTPS URLs, not local paths. If the source is a local, pasted or attached file, upload it first and use the returned URL.

**When the input is a full drawing sheet, crop it before generating.** A whole fabrication package passed as one image tends to reproduce the sheet layout, title block and data tables instead of exploding the assembly. Crop to the 3D or isometric view, and crop the section view separately when one is present, then pass both as separate references so hidden geometry is honoured.

## Step 3 — Generate

Use the bundled generator. It handles provider selection, the API call, and the download, so the host never has to hand-assemble a CLI invocation:

```bash
python3 scripts/generate.py --prompt-file prompt.txt --reference src.png --out exploded.png
```

Provider auto-detection order, overridable with `--provider`:

| `--provider` | Requires |
|---|---|
| `mcode` | `mcode-tools` on PATH (MiniMax Code) |
| `gemini` | `GEMINI_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `auto` | first available from the list above |

```bash
# force a provider
python3 scripts/generate.py --provider gemini --prompt-file prompt.txt --out exploded.png
```

> **Anthropic models cannot generate images.** There is no Anthropic image-generation endpoint. If you are running in a Claude host, the host writes the prompt and `generate.py` draws it using a Gemini or OpenAI key. `generate.py` exits with a clear message rather than failing obscurely. See `references/claude-code.md`.

Run `python3 scripts/generate.py --help` for all flags.

## Step 4 — Show the result

**Delivery is not optional. A generated image that is never surfaced is a failed run.**

1. Confirm the output file exists on disk (`test -f <path>`).
2. Embed it in your reply using your host's media syntax.
3. Follow it with a plain statement of what the image shows.
4. Name every component you *inferred* rather than read directly off the source, and flag anything uncertain.

Host-specific delivery syntax is in `references/`. Read only the file matching your host:

| Your host | Read |
|---|---|
| MiniMax Code | `references/mcode.md` |
| Claude Code | `references/claude-code.md` |
| Codex / OpenAI | `references/codex.md` |
| Gemini CLI | `references/gemini-cli.md` |
| Anything else with a shell | `references/generic.md` |

---

# OUTPUT

Generate ONE polished exploded-view illustration based on the supplied source.

Always deliver the generated image itself, not only a written description of it.

The final result should communicate:

```
SOURCE ASSEMBLY
        ↓
IDENTIFY COMPONENTS
        ↓
SEPARATE COMPONENTS
        ↓
ALIGN COMPONENTS WITH ASSEMBLY AXES
        ↓
SHOW ASSEMBLY RELATIONSHIPS
        ↓
LABEL MAJOR COMPONENTS
        ↓
PRODUCE PROFESSIONAL EXPLODED VIEW
```

## PRIORITISE

1. Engineering fidelity
2. Correct component relationships
3. Correct assembly orientation
4. Clear separation
5. Visual clarity
6. Professional presentation

**Never sacrifice engineering accuracy merely to make the image more visually attractive.**

The exploded view is an interpretation of the supplied engineering information, not a redesign.
