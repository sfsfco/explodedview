# Host adapter: MiniMax Code

The host this skill was written in. Everything here is verified working.

## Install

The skill directory is `skills/explodedview/`. It must be visible at
`~/.minimax/skills/explodedview/`.

```bash
# from a clone of this repo
ln -s "$PWD/skills/explodedview" ~/.minimax/skills/explodedview
```

A symlink is deliberate: `~/.minimax/skills/` is runtime-owned and gets
rewritten when skills are installed or updated from the skill hub. Keeping the
git checkout elsewhere means an update can never clobber your working tree.

## Generating

`mcode-tools` is already on PATH inside MiniMax Code, so the generator picks
the `mcode` provider with no configuration:

```bash
python3 scripts/generate.py --prompt-file prompt.txt --reference src.png --out exploded.png
```

If you are running the mcode-tools CLI by hand instead of through the script,
these are the exact invocations, and they are what the script performs:

```bash
# 1. the generator only accepts HTTPS URLs, never local paths
mcode-tools upload_temp_url <file> --mime-type image/png

# 2. arguments MUST be wrapped in a requests array - a flat prompt is rejected
mcode-tools connector call connector__matrix__generate_image --args-file <path.json>

# 3. node_id is not a URL. Do not concatenate it into one.
mcode-tools get_asset_url <node_id>

# 4. fetch the download_url from the previous response
```

Two failure modes worth memorising, both hit during development:

- **A flat payload is silently wrong.** The connector expects `{"requests": [...]}`,
  not `{"prompt": "..."}`.
- **`node_id` is an identifier, not a location.** Building `https://.../<node_id>`
  produces a 404 that looks like a permissions problem.

Set the Bash tool `timeout` field to **600**. Do not pass a timeout argument
inside the command string — the command has no such option.

If you invoke `mcode-tools` directly rather than through `generate.py`, load the
`mcode-tools-master` skill first.

## Delivering the result

Confirm the file exists, then embed it:

```xml
<deliver-assets>
<media src="/absolute/path/to/exploded.png" />
</deliver-assets>
```

Follow the embed with a plain sentence describing what the image shows, and name
every component you inferred rather than read off the source. A generated image
that is never surfaced is a failed run.
