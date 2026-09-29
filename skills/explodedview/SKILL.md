---
name: explodedview
description: Transform the provided technical drawing, engineering drawing, CAD screenshot, product image, assembly drawing, or equipment photograph into a clear and professional EXPLODED VIEW / EXPLODED ASSEMBLY illustration. Use this skill when the user supplies an assembly image and asks to explode it, separate its parts, show how it comes apart, or produce an assembly breakdown, including via the /explodedview slash command. Do not use it to read, interpret or explain a drawing when no illustration is requested.
---

/explodedview

FUNCTION:
Transform the provided technical drawing, engineering drawing, CAD screenshot, product image, assembly drawing, or equipment photograph into a clear and professional EXPLODED VIEW / EXPLODED ASSEMBLY illustration.

OBJECTIVE:
Create a visually separated representation of the assembly where the major components are pulled apart along their natural assembly axes while maintaining their correct relative position, orientation, proportions, and assembly relationship.

The exploded view must help an engineer, technician, manufacturer, or client understand:
1. What components make up the assembly.
2. How the components fit together.
3. The approximate assembly order.
4. Where each component belongs.
5. Which components are removable or independently manufactured.

INPUT ANALYSIS:
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

ENGINEERING ACCURACY:
- Preserve the geometry shown in the source drawing.
- Preserve the original orientation of components.
- Preserve relative dimensions and proportions as much as possible.
- Preserve holes, flanges, nozzles, brackets, supports, bolts, weldments, and other visible details.
- Do NOT invent components that are not reasonably supported by the source.
- Do NOT change the function or geometry of the equipment.
- Do NOT arbitrarily redesign the product.
- If a component cannot be determined confidently, keep it visually consistent with the source rather than inventing detailed geometry.
- Do not treat decorative elements as engineering components unless they are present in the source.

EXPLOSION LOGIC:
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

VISUAL STYLE:
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

LAYOUT:
Use a logical composition.

Preferred layout:
- Exploded assembly as the main focus.
- Fully assembled reference view may be shown to one side when useful.
- Components should have sufficient spacing to clearly distinguish them.
- Avoid overlapping components unnecessarily.
- Maintain clear visual hierarchy.

LABELING:
If labels are appropriate, identify major components with numbered callouts.

Use:
1. Component Name
2. Component Name
3. Component Name
...

Callout lines should point precisely to the corresponding component.

Image generators render baked-in text unreliably and frequently emit garbled letter-like glyphs instead of real characters. Choose deliberately:
- Instruct the generator to produce no text at all, then deliver the numbered parts list as a markdown table in your reply. This is the default.
- Or accept callouts in the image and verify them before showing the result.
Never omit labels from the prompt and then describe an image as though they exist.

Do not add technical specifications that are not present in the source.

If the source contains dimensions, materials, thicknesses, capacities, or other engineering information, preserve them accurately when displaying them.

PARTS LIST:
When useful, create a parts list containing:

| No. | Part Name | Description | Qty. |
|-----|-----------|-------------|------|

Only include information that can reasonably be determined from the source.

Do not invent quantities or specifications.

DIMENSIONS:
If dimensions are visible in the source:
- Preserve important dimensions.
- Do not alter numerical values.
- Do not replace engineering dimensions with estimated values.
- If a dimension is unclear, omit it rather than guessing.

TECHNICAL DRAWING PRESERVATION:
If the input is an engineering drawing containing multiple views:
- Use all relevant views to understand the object.
- Cross-reference front, side, top, section and detail views.
- Use section views to understand hidden/internal geometry.
- Use dimensions and notes to resolve component relationships.
- Do not rely only on the 3D perspective view if orthographic views provide more accurate information.

FOR INDUSTRIAL EQUIPMENT:
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

GENERATION:
Describing the illustration is not producing it. Call the image generation tool, then show the returned image to the user.

1. Get the source image into a URL the tool can fetch. The generator accepts HTTPS URLs only, never local paths. For a local, pasted or attached image:
   mcode-tools upload_temp_url <file_path> --mime-type image/png
   Use the temp_url from the JSON response.

2. When the input is a full drawing sheet, crop it before generating. A whole fabrication package passed as one image tends to reproduce the sheet layout, title block and data tables instead of exploding the assembly. Crop to the 3D or isometric view, and crop the section view separately when one is present, then pass both as separate references so hidden geometry is honored.

3. Build the prompt from the sections above. State the components in explosion order, the direction each one travels, and the exact colours to preserve. Write the arguments to a JSON file rather than inlining them, to avoid shell quoting problems.

4. Generate. Load the mcode-tools-master skill before running any mcode-tools command. The payload must be wrapped in a requests array, never a flat prompt:
   mcode-tools connector call connector__matrix__generate_image --args-file <path>
   Set the Bash tool timeout field to 600. Never pass a timeout argument inside the command string; the command has no such option.
   A successful call returns success_items[].node_id.

5. Download. The node_id is not a URL and must never be used to construct one.
   mcode-tools get_asset_url <node_id>
   Fetch the returned download_url to a local file in the working directory.

6. Show the image back to the user. Delivery is not optional. A generated image that is never surfaced is a failed run. Confirm the file exists on disk, then embed it in the reply:
   <deliver-assets>
   <media src="/absolute/path/to/generated-image.jpg" />
   </deliver-assets>
   Follow it with a plain statement of what the image shows, and name every component you inferred rather than read off the source.

OUTPUT:
Generate ONE polished exploded-view illustration based on the supplied source.

Always deliver the generated image itself, not only a written description of it.

The final result should communicate:

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

IMPORTANT:
The exploded view is an interpretation of the supplied engineering information, not a redesign.

Prioritize:
1. Engineering fidelity
2. Correct component relationships
3. Correct assembly orientation
4. Clear separation
5. Visual clarity
6. Professional presentation

Never sacrifice engineering accuracy merely to make the image more visually attractive.