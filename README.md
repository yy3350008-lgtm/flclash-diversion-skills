# FlClash Diversion Skills

English | [简体中文](README.zh-CN.md)

> Merging FlClash and Mihomo (Clash Meta) proxy profiles into one configuration
> with precise domain routing and split tunneling — safe for multiple subscriptions.

## Use Cases

- **One subscription for daily use, another for a specific site.** Keep your main
  subscription for general traffic while routing a single website through a different
  provider's nodes.
- **Preferred main node with targeted diversion.** Route NotebookLM, Gemini, ChatGPT,
  or any other domain through verified nodes without affecting the rest of your traffic.
- **Combine multiple subscriptions into one FlClash-compatible local profile.** Merge
  two or more subscription configs into a single file that FlClash can load directly.
- **Avoid broad Google-domain rules that accidentally reroute unrelated services.**
  The tool blocks wide rules like `google.com` by default so only confirmed target
  domains are diverted.

## What You Get

| Before | After |
|---|---|
| Only one active FlClash profile at a time. | One merged profile containing a main group, a secondary group, and a target diversion group. |
| Switching subscriptions means losing one set of nodes. | All nodes from both subscriptions coexist in a single config with precise domain-level routing. |

## Why?

FlClash activates one profile at a time. If you have a secondary profile whose
proxies work better for specific services (e.g. NotebookLM), you cannot simply
select both profiles. This tool merges two profiles into a single output config:

- All secondary proxies are added to the base config.
- A secondary group is created and inserted into the main group.
- A diversion group routes specific domains through chosen nodes.
- Broad domain rules (google.com, etc.) are blocked by default to prevent
  hijacking all traffic from a provider.

## Features

- **Precise domain diversion** — route only confirmed target domains, not entire
  top-level domains.
- **Target node validation** — the script refuses to write output if any specified
  target node is not found in the merged proxy list.
- **Broad domain blocking** — rules for google.com, googleapis.com, gstatic.com
  are rejected unless `--allow-broad-domain` is explicitly set.
- **Post-write validation** — output is re-read and validated from disk; the file
  is deleted if validation fails.
- **No credential exposure** — the script prints only group names, domain names,
  and proxy counts. No IPs, UUIDs, tokens, or passwords are printed.
- **Privacy-safe examples** — all example configs use `type: direct` proxy stubs
  with no endpoint or credential fields.

## Safety & Privacy

This project is designed to be safe to publish:

- **No hardcoded paths, IPs, UUIDs, tokens, or passwords** in any script or config.
- **No user-specific file paths** — no local machine paths or usernames.
- **Examples use `type: direct` proxy stubs** with no endpoint or credential fields.
- **Output summary never prints config contents or credentials.**
- The `.gitignore` blocks `output.yaml`, `*.local.yaml`, `*.secret.yaml`, and
  `.env` to prevent accidental credential commits.

## Installation

### Requirements

- Python 3.10+
- `ruamel.yaml` >= 0.18

### Install

```bash
pip install ruamel.yaml
```

Or with dev dependencies (for running tests):

```bash
pip install -e ".[dev]"
```

### As a Codex/Claude Skill

Copy the `SKILL.md` file and the `agents/` and `scripts/` directories into your
skill path. The skill description in `SKILL.md` will be auto-detected by
Codex/Claude.

## CLI Usage

```bash
python scripts/merge_flclash_configs.py \
  --base examples/generic-main.yaml \
  --secondary examples/generic-secondary.yaml \
  --output output.yaml \
  --main-group Main \
  --secondary-group Secondary-Main \
  --target-group NotebookLM \
  --target-domain notebooklm.google \
  --target-node Proxy-B
```

### Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--base` | Yes | — | Base config YAML path |
| `--secondary` | Yes | — | Secondary config YAML path |
| `--output` | Yes | — | Output merged YAML path |
| `--main-group` | Yes | — | Name of the main select group in base config |
| `--secondary-group` | Yes | — | Name for the new secondary proxy group |
| `--target-group` | Yes | — | Name for the new diversion group |
| `--target-domain` | Yes | — | Domain to divert (repeatable) |
| `--target-node` | Yes | — | Specific node name for the target group (repeatable) |
| `--target-group-type` | No | `select` | Group type: `select` or `url-test` |
| `--allow-broad-domain` | No | `false` | Allow broad domain rules |

### What the Script Does

1. Loads base and secondary YAML configs.
2. Appends secondary proxies to base (skips duplicates, skips meta-entries like
   traffic/expiry notices).
3. Creates the secondary group with all real secondary proxies.
4. Inserts the secondary group into the main group at position 0.
5. Validates every `--target-node` exists in merged proxies; exits nonzero if not.
6. Creates the target group with exactly the specified target nodes.
7. Removes existing DOMAIN-SUFFIX rules for target domains, then prepends new ones.
8. Blocks broad domain rules unless `--allow-broad-domain` is set.
9. Validates in memory before writing; re-reads and validates from disk after.

## FlClash Integration

1. Open FlClash and go to **Profiles**.
2. Add the output YAML as a local config.
3. Enable the config.
4. Go to **Proxies** and verify nodes in each group.
5. Test that target domains route through the diversion group.

To roll back, simply reload the original profile in FlClash.

## Testing

```bash
pytest
```

Tests cover:

- Successful merge with correct group structure and rule ordering.
- Target node validation (missing nodes cause nonzero exit).
- `--target-group-type url-test` flag.
- Broad domain blocking and `--allow-broad-domain` override.
- Domain normalization (leading dots, whitespace).
- Privacy checks (no local paths or user directories in output).

## Limitations

- The script assumes YAML input is valid FlClash/Mihomo config syntax.
- `url-test` groups use `https://www.gstatic.com/generate_204` as the test URL.
- The script does not modify input files; it always writes a new output file.
- Broad domain blocking only checks the three most common Google domains.

## Who Is This For?

- **Students and researchers** who need region-sensitive services like NotebookLM or
  Gemini accessible through a reliable proxy node.
- **Developers** managing multiple proxy subscriptions for different projects or
  environments.
- **Users with region-sensitive web services** who want fine-grained control over
  which domains route through which nodes.

## Contributing

1. Fork the repository.
2. Create a feature branch.
3. Add tests for new functionality.
4. Run `pytest` to verify all tests pass.
5. Submit a pull request.

Please ensure no real credentials, IPs, or user-specific paths are included in
any commits.

## Keywords

This project covers FlClash split tunneling, Mihomo rules and routing, Clash Meta
profile merging, multi-subscription proxy management, domain-based proxy routing,
and NotebookLM proxy routing through policy groups.

## License

[MIT](LICENSE) — Copyright 2026 FlClash Diversion Skills contributors.
