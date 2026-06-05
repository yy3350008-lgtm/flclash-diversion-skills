#!/usr/bin/env python3
"""Merge a secondary FlClash/Mihomo config into a base config with diversion rules.

Creates a combined profile where:
- Secondary proxies are added to the base config.
- A secondary group is created containing all secondary proxies.
- The secondary group is inserted into the main group.
- A target group is created for domain-specific diversion.
- Diversion rules route target domains through the target group.
- Broad domain rules (google.com, googleapis.com, gstatic.com) are blocked
  unless --allow-broad-domain is set.
"""
from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from pathlib import Path

try:
    from ruamel.yaml import YAML
except ImportError:
    print("Missing dependency: ruamel.yaml")
    print("Install with: python -m pip install ruamel.yaml")
    sys.exit(1)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Broad domains that are dangerous to route entirely through a diversion group.
BROAD_DOMAINS = {"google.com", "googleapis.com", "gstatic.com"}

# Special proxy names that are not actual proxy definitions.
SPECIAL_PROXIES = {"DIRECT", "REJECT", "REJECT-DROP", "PASS", "COMPATIBLE"}


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

def yaml_loader() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml_loader().load(f)


def save_yaml(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        yaml_loader().dump(data, f)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def require_list(config: dict, key: str) -> list:
    value = config.get(key)
    if value is None:
        value = []
        config[key] = value
    if not isinstance(value, list):
        raise TypeError(f"'{key}' must be a list")
    return value


def proxy_name(proxy) -> str | None:
    if isinstance(proxy, dict):
        name = proxy.get("name")
        return str(name) if name is not None else None
    return None


def is_real_proxy(name: str) -> bool:
    """Return False for meta-entries like traffic/expiry notices."""
    return not (
        name.startswith("剩余流量")
        or name.startswith("套餐到期")
    )


def group_by_name(groups: list, name: str) -> dict | None:
    for g in groups:
        if isinstance(g, dict) and g.get("name") == name:
            return g
    return None


def remove_group(groups: list, name: str) -> None:
    groups[:] = [
        g for g in groups
        if not (isinstance(g, dict) and g.get("name") == name)
    ]


# ---------------------------------------------------------------------------
# Core merge logic
# ---------------------------------------------------------------------------

def collect_secondary_proxies(secondary: dict) -> list[str]:
    """Return names of real proxies from the secondary config."""
    names: list[str] = []
    for proxy in require_list(secondary, "proxies"):
        name = proxy_name(proxy)
        if name and is_real_proxy(name):
            names.append(name)
    if not names:
        raise RuntimeError("No real proxies found in secondary config")
    return names


def append_proxies(base: dict, secondary: dict) -> None:
    """Add secondary proxies to base (skip duplicates by name)."""
    base_proxies = require_list(base, "proxies")
    existing = {proxy_name(p) for p in base_proxies}
    for proxy in require_list(secondary, "proxies"):
        name = proxy_name(proxy)
        if name and name not in existing:
            base_proxies.append(deepcopy(proxy))
            existing.add(name)


def create_secondary_group(base: dict, secondary_group: str, proxy_names: list[str]) -> None:
    """Create (or replace) the secondary group."""
    groups = require_list(base, "proxy-groups")
    remove_group(groups, secondary_group)
    groups.append({
        "name": secondary_group,
        "type": "select",
        "proxies": list(proxy_names),
    })


def insert_secondary_into_main(base: dict, main_group: str, secondary_group: str) -> None:
    """Insert the secondary group into the main group's proxy list."""
    groups = require_list(base, "proxy-groups")
    mg = group_by_name(groups, main_group)
    if mg is None:
        raise RuntimeError(f"Main group '{main_group}' not found in config")
    proxies = mg.get("proxies")
    if proxies is None:
        proxies = []
        mg["proxies"] = proxies
    if not isinstance(proxies, list):
        raise TypeError(f"'{main_group}.proxies' must be a list")

    # Remove if already present, then insert at position 0.
    proxies[:] = [p for p in proxies if p != secondary_group]
    proxies.insert(0, secondary_group)


def create_target_group(
    base: dict,
    target_group: str,
    target_group_type: str,
    target_nodes: list[str],
    all_proxy_names: set[str],
) -> None:
    """Create the target diversion group.

    Validates every target-node exists in merged proxies.
    Raises RuntimeError if any target node is missing.
    """
    groups = require_list(base, "proxy-groups")
    remove_group(groups, target_group)

    missing = [n for n in target_nodes if n not in all_proxy_names]
    if missing:
        raise RuntimeError(
            f"Target node(s) not found in merged proxies: {', '.join(missing)}"
        )

    group_def: dict = {
        "name": target_group,
        "type": target_group_type,
        "proxies": list(target_nodes),
    }
    if target_group_type == "url-test":
        group_def["url"] = "https://www.gstatic.com/generate_204"
        group_def["interval"] = 300
    groups.append(group_def)


def normalize_domain(domain: str) -> str:
    """Strip whitespace and leading dots from a domain."""
    return domain.strip().lstrip(".")


def add_diversion_rules(
    base: dict,
    target_group: str,
    target_domains: list[str],
    allow_broad: bool,
) -> None:
    """Remove existing DOMAIN-SUFFIX rules for target domains, then prepend new ones."""
    rules = require_list(base, "rules")

    # Remove every existing DOMAIN-SUFFIX rule for each target domain
    # regardless of destination group.
    remaining = []
    for r in rules:
        rs = str(r)
        dominated = False
        for domain in target_domains:
            if rs.startswith(f"DOMAIN-SUFFIX,{domain},"):
                dominated = True
                break
        if not dominated:
            remaining.append(r)

    # Build new diversion rules.
    new_rules = [f"DOMAIN-SUFFIX,{d},{target_group}" for d in target_domains]
    rules[:] = new_rules + remaining


def validate_output(
    config: dict,
    main_group: str,
    secondary_group: str,
    target_group: str,
    target_domains: list[str],
    target_nodes: list[str],
    allow_broad: bool,
) -> list[str]:
    """Return a list of validation warnings (empty = all good)."""
    warnings: list[str] = []
    groups = require_list(config, "proxy-groups")
    rules = require_list(config, "rules")
    proxy_names = {proxy_name(p) for p in require_list(config, "proxies")}
    all_valid = proxy_names | SPECIAL_PROXIES
    # In Clash Meta, groups can reference other groups by name.
    group_names = {g.get("name") for g in groups if isinstance(g, dict)}
    all_valid = all_valid | group_names

    # Groups exist.
    for gname in (main_group, secondary_group, target_group):
        if group_by_name(groups, gname) is None:
            warnings.append(f"Missing group: {gname}")

    # Secondary in main.
    mg = group_by_name(groups, main_group)
    if mg and secondary_group not in list(mg.get("proxies") or []):
        warnings.append(f"'{main_group}' does not contain '{secondary_group}'")

    # Validate proxy-group references: every proxy listed in a group must exist
    # in the proxies section, or be a group name, or be a special name.
    # IMPORTANT: Some groups use `use` providers rather than `proxies`;
    # validate only groups that have a proxies list.
    for group in groups:
        if not isinstance(group, dict):
            continue
        gname = group.get("name", "<unknown>")
        if "proxies" not in group:
            continue
        for pref in list(group.get("proxies") or []):
            if pref not in all_valid:
                warnings.append(
                    f"Group '{gname}' references unknown proxy '{pref}'"
                )

    # Target group proxies must exactly equal target_nodes.
    tg = group_by_name(groups, target_group)
    if tg:
        tg_proxies = list(tg.get("proxies") or [])
        if tg_proxies != list(target_nodes):
            warnings.append(
                f"Target group proxies mismatch: expected {target_nodes}, got {tg_proxies}"
            )

    # Diversion rules present.
    for domain in target_domains:
        expected = f"DOMAIN-SUFFIX,{domain},{target_group}"
        if expected not in [str(r) for r in rules]:
            warnings.append(f"Missing diversion rule: {expected}")

    # First rules must be the diversion rules in order.
    for i, domain in enumerate(target_domains):
        expected = f"DOMAIN-SUFFIX,{domain},{target_group}"
        if i < len(rules) and str(rules[i]) != expected:
            warnings.append(
                f"Rule order mismatch: expected '{expected}' at position {i}, "
                f"got '{rules[i]}'"
            )

    # Broad rules blocked.
    if not allow_broad:
        rule_strs = [str(r) for r in rules]
        for domain in BROAD_DOMAINS:
            forbidden = f"DOMAIN-SUFFIX,{domain},{target_group}"
            if forbidden in rule_strs:
                warnings.append(f"Broad domain rule present: {forbidden}")
        for domain in BROAD_DOMAINS:
            for rule in rules:
                rs = str(rule)
                if (
                    rs.startswith(f"DOMAIN-SUFFIX,{domain},")
                    and rs != f"DOMAIN-SUFFIX,{domain},{target_group}"
                ):
                    warnings.append(
                        f"Broad domain rule '{rs}' may override specific "
                        f"diversion rules for subdomains of {domain}"
                    )

    return warnings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Merge a secondary FlClash config into a base config with diversion rules.",
    )
    p.add_argument("--base", required=True, type=Path, help="Base config YAML path")
    p.add_argument("--secondary", required=True, type=Path, help="Secondary config YAML path")
    p.add_argument("--output", required=True, type=Path, help="Output config YAML path")
    p.add_argument("--main-group", required=True, help="Name of the main group in base config")
    p.add_argument("--secondary-group", required=True, help="Name for the new secondary group")
    p.add_argument("--target-group", required=True, help="Name for the target diversion group")
    p.add_argument("--target-domain", required=True, action="append", dest="target_domains",
                   help="Domain to divert (repeatable). e.g. notebooklm.google")
    p.add_argument("--target-node", required=True, action="append", dest="target_nodes",
                   help="Specific node name for the target group (repeatable)")
    p.add_argument("--target-group-type", default="select", choices=["select", "url-test"],
                   help="Type of the target group (default: select)")
    p.add_argument("--allow-broad-domain", action="store_true",
                   help="Allow broad domain rules (google.com, googleapis.com, gstatic.com)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    # Normalize target domains: strip whitespace and leading dots; reject empty.
    normalized_domains: list[str] = []
    for d in args.target_domains:
        nd = normalize_domain(d)
        if not nd:
            print(f"ERROR: Empty domain after normalization: '{d}'", file=sys.stderr)
            sys.exit(1)
        normalized_domains.append(nd)
    args.target_domains = normalized_domains

    # Reject broad domains unless --allow-broad-domain.
    if not args.allow_broad_domain:
        for d in args.target_domains:
            if d in BROAD_DOMAINS:
                print(
                    f"ERROR: Broad domain '{d}' is blocked. "
                    f"Use --allow-broad-domain to override.",
                    file=sys.stderr,
                )
                sys.exit(1)

    base = load_yaml(args.base)
    secondary = load_yaml(args.secondary)

    proxy_names = collect_secondary_proxies(secondary)
    append_proxies(base, secondary)
    create_secondary_group(base, args.secondary_group, proxy_names)
    insert_secondary_into_main(base, args.main_group, args.secondary_group)

    # Validate target nodes against merged proxies before writing.
    all_merged = {proxy_name(p) for p in require_list(base, "proxies")}
    missing = [n for n in args.target_nodes if n not in all_merged]
    if missing:
        print(
            f"ERROR: Target node(s) not found in merged proxies: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    create_target_group(
        base, args.target_group, args.target_group_type,
        args.target_nodes, all_merged,
    )
    add_diversion_rules(base, args.target_group, args.target_domains, args.allow_broad_domain)

    # In-memory validation before writing.
    warnings = validate_output(
        base, args.main_group, args.secondary_group,
        args.target_group, args.target_domains, args.target_nodes,
        args.allow_broad_domain,
    )
    if warnings:
        for w in warnings:
            print(f"WARNING: {w}", file=sys.stderr)
        print("ERROR: In-memory validation failed; not writing output.", file=sys.stderr)
        sys.exit(1)

    save_yaml(args.output, base)

    # Re-validate from disk.
    disk = load_yaml(args.output)
    disk_warnings = validate_output(
        disk, args.main_group, args.secondary_group,
        args.target_group, args.target_domains, args.target_nodes,
        args.allow_broad_domain,
    )
    if disk_warnings:
        for w in disk_warnings:
            print(f"DISK WARNING: {w}", file=sys.stderr)
        # Delete the just-written output on post-write validation failure.
        try:
            args.output.unlink()
        except OSError:
            pass
        sys.exit(1)

    # Summary only; do not print config contents or credentials.
    print(f"Created: {args.output}")
    print(f"Main group: {args.main_group}")
    print(f"Secondary group: {args.secondary_group}")
    print(f"Target group: {args.target_group}")
    print(f"Target domains: {', '.join(args.target_domains)}")
    print(f"Target nodes: {', '.join(args.target_nodes)}")
    print(f"Proxies in base: {len(require_list(base, 'proxies'))}")
    print(f"Groups: {len(require_list(base, 'proxy-groups'))}")
    print(f"Rules: {len(require_list(base, 'rules'))}")


if __name__ == "__main__":
    main()
