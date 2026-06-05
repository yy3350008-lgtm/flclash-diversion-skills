"""Tests for merge_flclash_configs.py — run with: pytest"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "merge_flclash_configs.py"
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
REPO_ROOT = Path(__file__).resolve().parent.parent

# Forbidden credential keys that must never appear in example YAML files.
# Use negative lookbehind to avoid false positives (e.g. "port:" must not
# match "mixed-port:").  [\w-] covers word chars and hyphens.
FORBIDDEN_KEY_PATTERNS_EXAMPLES = [
    re.compile(r"(?<![\w-])server:"),
    re.compile(r"(?<![\w-])port:"),
    re.compile(r"(?<![\w-])uuid:"),
    re.compile(r"(?<![\w-])password:"),
    re.compile(r"token="),
]

# Patterns that must never appear in any committed file.
FORBIDDEN_PATH_PATTERNS = [
    re.compile(r"AppData"),
    re.compile(r"Users[/\\]"),
    re.compile(r"%APPDATA%"),
]

# Forbidden credential patterns for output / source files.
FORBIDDEN_CREDENTIAL_PATTERNS = [
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),  # IPv4
]


def run_merge(tmp_path: Path, *extra_args: str, base: str = "generic-main.yaml",
              secondary: str = "generic-secondary.yaml") -> subprocess.CompletedProcess:
    """Run the merge script and return the result."""
    output = tmp_path / "output.yaml"
    cmd = [
        sys.executable, str(SCRIPT),
        "--base", str(EXAMPLES / base),
        "--secondary", str(EXAMPLES / secondary),
        "--output", str(output),
        "--main-group", "Main",
        "--secondary-group", "Secondary-Main",
        "--target-group", "NotebookLM",
        "--target-domain", "notebooklm.google",
        "--target-node", "Proxy-B",
        *extra_args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


class TestSuccessfulMerge:
    """Happy-path tests."""

    def test_exit_zero(self, tmp_path: Path) -> None:
        result = run_merge(tmp_path)
        assert result.returncode == 0, f"stderr:\n{result.stderr}"

    def test_output_created(self, tmp_path: Path) -> None:
        run_merge(tmp_path)
        output = tmp_path / "output.yaml"
        assert output.exists()

    def test_secondary_group_in_main(self, tmp_path: Path) -> None:
        """Secondary-Main must appear in Main's proxy list."""
        run_merge(tmp_path)
        from ruamel.yaml import YAML
        yaml = YAML()
        data = yaml.load((tmp_path / "output.yaml").read_text(encoding="utf-8"))
        groups = {g["name"]: g for g in data["proxy-groups"]}
        assert "Secondary-Main" in groups["Main"]["proxies"]

    def test_notebooklm_group_type_select(self, tmp_path: Path) -> None:
        """NotebookLM group should be select type."""
        run_merge(tmp_path)
        from ruamel.yaml import YAML
        yaml = YAML()
        data = yaml.load((tmp_path / "output.yaml").read_text(encoding="utf-8"))
        groups = {g["name"]: g for g in data["proxy-groups"]}
        assert groups["NotebookLM"]["type"] == "select"

    def test_notebooklm_contains_target_node(self, tmp_path: Path) -> None:
        """NotebookLM group should contain exactly the target node."""
        run_merge(tmp_path)
        from ruamel.yaml import YAML
        yaml = YAML()
        data = yaml.load((tmp_path / "output.yaml").read_text(encoding="utf-8"))
        groups = {g["name"]: g for g in data["proxy-groups"]}
        assert "Proxy-B" in groups["NotebookLM"]["proxies"]

    def test_diversion_rule_first(self, tmp_path: Path) -> None:
        """DOMAIN-SUFFIX for target domain should be the first rule."""
        run_merge(tmp_path)
        from ruamel.yaml import YAML
        yaml = YAML()
        data = yaml.load((tmp_path / "output.yaml").read_text(encoding="utf-8"))
        assert str(data["rules"][0]) == "DOMAIN-SUFFIX,notebooklm.google,NotebookLM"

    def test_secondary_proxies_added(self, tmp_path: Path) -> None:
        """Secondary proxies should appear in the merged proxy list."""
        run_merge(tmp_path)
        from ruamel.yaml import YAML
        yaml = YAML()
        data = yaml.load((tmp_path / "output.yaml").read_text(encoding="utf-8"))
        names = {p["name"] for p in data["proxies"]}
        assert "Secondary-Alpha" in names
        assert "Secondary-Beta" in names
        assert "Secondary-Gamma" in names


class TestTargetNodeValidation:
    """Target node must exist in merged proxies."""

    def test_missing_target_node_exits_nonzero(self, tmp_path: Path) -> None:
        result = run_merge(tmp_path, "--target-node", "NonexistentNode")
        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "not found" in result.stdout.lower()

    def test_missing_target_node_no_output(self, tmp_path: Path) -> None:
        run_merge(tmp_path, "--target-node", "NonexistentNode")
        output = tmp_path / "output.yaml"
        assert not output.exists()


class TestTargetGroupType:
    """--target-group-type flag."""

    def test_url_test_type(self, tmp_path: Path) -> None:
        result = run_merge(tmp_path, "--target-group-type", "url-test")
        assert result.returncode == 0
        from ruamel.yaml import YAML
        yaml = YAML()
        data = yaml.load((tmp_path / "output.yaml").read_text(encoding="utf-8"))
        groups = {g["name"]: g for g in data["proxy-groups"]}
        assert groups["NotebookLM"]["type"] == "url-test"


class TestBroadDomainBlocking:
    """Broad domains should be blocked by default."""

    def test_broad_domain_exits_nonzero(self, tmp_path: Path) -> None:
        result = run_merge(tmp_path, "--target-domain", "google.com")
        assert result.returncode != 0
        assert "blocked" in result.stderr.lower() or "blocked" in result.stdout.lower()

    def test_allow_broad_domain_flag(self, tmp_path: Path) -> None:
        result = run_merge(
            tmp_path,
            "--target-domain", "google.com",
            "--allow-broad-domain",
        )
        assert result.returncode == 0


class TestDomainNormalization:
    """Domains with leading dots or whitespace should be normalized."""

    def test_leading_dot_stripped(self, tmp_path: Path) -> None:
        result = run_merge(tmp_path, "--target-domain", ".example.google")
        assert result.returncode == 0
        from ruamel.yaml import YAML
        yaml = YAML()
        data = yaml.load((tmp_path / "output.yaml").read_text(encoding="utf-8"))
        rules_str = [str(r) for r in data["rules"]]
        assert "DOMAIN-SUFFIX,example.google,NotebookLM" in rules_str


class TestPrivacy:
    """Ensure no real credentials leak into output."""

    def test_no_real_ip_in_output(self, tmp_path: Path) -> None:
        """Output should not contain IPs from AppData paths or real user dirs."""
        run_merge(tmp_path)
        content = (tmp_path / "output.yaml").read_text(encoding="utf-8")
        for pat in FORBIDDEN_PATH_PATTERNS:
            assert not pat.search(content), f"Forbidden path pattern in output: {pat.pattern}"

    def test_no_credential_keys_in_output(self, tmp_path: Path) -> None:
        """Output should not contain server/port/uuid/password/token keys."""
        run_merge(tmp_path)
        content = (tmp_path / "output.yaml").read_text(encoding="utf-8")
        for pat in FORBIDDEN_KEY_PATTERNS_EXAMPLES:
            assert not pat.search(content), f"Forbidden credential key in output: {pat.pattern}"

    def test_no_ipv4_in_output(self, tmp_path: Path) -> None:
        """Output should not contain any IPv4 addresses."""
        run_merge(tmp_path)
        content = (tmp_path / "output.yaml").read_text(encoding="utf-8")
        for pat in FORBIDDEN_CREDENTIAL_PATTERNS:
            assert not pat.search(content), f"Forbidden IPv4 in output: {pat.pattern}"


class TestExampleFilesPrivacy:
    """Ensure example YAML files contain no real credentials."""

    @pytest.mark.parametrize("filename", [
        "generic-main.yaml",
        "generic-secondary.yaml",
    ])
    def test_no_forbidden_keys_in_examples(self, filename: str) -> None:
        """Example files must not contain server:, port:, uuid:, password:, or token=."""
        content = (EXAMPLES / filename).read_text(encoding="utf-8")
        for pat in FORBIDDEN_KEY_PATTERNS_EXAMPLES:
            assert not pat.search(content), f"Forbidden key '{pat.pattern}' found in {filename}"

    @pytest.mark.parametrize("filename", [
        "generic-main.yaml",
        "generic-secondary.yaml",
    ])
    def test_no_ipv4_in_examples(self, filename: str) -> None:
        """Example files must not contain any IPv4 addresses."""
        content = (EXAMPLES / filename).read_text(encoding="utf-8")
        for pat in FORBIDDEN_CREDENTIAL_PATTERNS:
            assert not pat.search(content), f"Forbidden IPv4 in {filename}: {pat.pattern}"

    @pytest.mark.parametrize("filename", [
        "generic-main.yaml",
        "generic-secondary.yaml",
    ])
    def test_no_forbidden_paths_in_examples(self, filename: str) -> None:
        """Example files must not contain user-specific paths."""
        content = (EXAMPLES / filename).read_text(encoding="utf-8")
        for pat in FORBIDDEN_PATH_PATTERNS:
            assert not pat.search(content), f"Forbidden path pattern in {filename}: {pat.pattern}"
