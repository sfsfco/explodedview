# Host adapter: a MiniMax model outside MiniMax Code

Use this when a MiniMax model is the agent but the host is something else —
Claude Code pointed at MiniMax's Anthropic-compatible endpoint, OpenCode,
Cline, Kilo, or any other shell-capable agent. Inside MiniMax Code itself, read
`mcode.md` instead: the `mcode` provider needs no key and can take the source
image.

## Two constraints to check first

**1. Can the model see the drawing?** MiniMax's coding models may be
text-only in your setup. If you cannot read the attached image directly, use
the MiniMax MCP server's `understand_image` tool to analyse it, and ask it the
questions from the Input Analysis section in SKILL.md: which components, which
views, which mounting faces. Use the same tool on the generated image before
you describe it. If neither direct vision nor an image-understanding tool is
available, stop and tell the user — do not guess the assembly.

**2. What will draw the picture?**

| Credential | Result |
|---|---|
| `mcode-tools` on PATH | `mcode` — takes the source image. Best option if present. |
| `GEMINI_API_KEY` or `OPENAI_API_KEY` | Takes the source image. Recommended. |
| Only `MINIMAX_API_KEY` | `minimax` (image-01) — **text only**, prompt ≤ 1,500 characters. |

The MiniMax image API's `subject_reference` only accepts faces
(`type: "character"`), so it cannot condition on an engineering drawing. The
generator therefore refuses `--reference` with `--provider minimax` rather than
drawing something unrelated. With only a MiniMax key you have two honest
options: drop `--reference` and describe the geometry completely in a tight
prompt, or tell the user a Gemini or OpenAI key will give a far more faithful
exploded view. Say which one you chose.

## Generating

```bash
export MINIMAX_API_KEY=...
# mainland China accounts only:
export MINIMAX_API_HOST=https://api.minimaxi.com

python3 <skill-dir>/scripts/generate.py --provider minimax --prompt-file prompt.txt --out exploded.png
```

Valid `--aspect-ratio` values: `1:1`, `16:9`, `4:3`, `3:2`, `2:3`, `3:4`,
`9:16`, `21:9`.

The script sets `prompt_optimizer: false` so MiniMax sends your prompt to the
model word for word. Check the request without spending anything:

```bash
python3 <skill-dir>/scripts/generate.py --provider minimax --prompt-file prompt.txt --dry-run
```

## Delivering the result

Deliver it the way your host shows images; the host's own adapter file covers
this (e.g. `claude-code.md`), otherwise `generic.md`. Because this path is
text-only, list every component whose shape or position came from your reading
of the drawing rather than from the generator seeing it.
