#!/usr/bin/env python3
"""Validate and assemble only the read-only probe, not a design completion package."""
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
MEMBERS = ("run.sh", "probe.py", "probe_cadence.il", "开始这里.md")


def check_skill_structure(text):
    depth, string, escape, comment = 0, False, False, False
    for char in text:
        if comment:
            if char == "\n":
                comment = False
        elif string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                string = False
        elif char == ';':
            comment = True
        elif char == '"':
            string = True
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth < 0:
                raise ValueError("Unmatched SKILL close parenthesis")
    if depth or string:
        raise ValueError("Unbalanced SKILL source; not a runtime syntax validation")


def main():
    output = ROOT / "releases"
    output.mkdir(exist_ok=True)
    probe = ROOT / "probe"
    ast.parse((probe / "probe.py").read_text())
    subprocess.run(["bash", "-n", str(probe / "run.sh")], check=True)
    check_skill_structure((probe / "probe_cadence.il").read_text())
    import contextlib
    import unittest
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    (output / "local_validation_v1.1.0.log").write_text(log.getvalue())
    if not result.wasSuccessful():
        raise RuntimeError("Local behavioral tests failed; see local_validation_v1.1.0.log")
    manifest = {"package": "project1_probe", "version": "1.1.0", "type": "READ_ONLY_ENVIRONMENT_HANDOFF",
                "files": {n: hashlib.sha256((probe / n).read_bytes()).hexdigest() for n in MEMBERS},
                "validation": {"behavioral_tests_passed": result.testsRun, "python_ast": "PASS",
                               "bash_syntax": "PASS", "skill_lexical_balance": "PASS",
                               "skill_runtime": "NOT_RUN_REQUIRES_VIRTUOSO", "cadence_simulation": "NOT_RUN"},
                "first_test_attempt": "One fixture assertion failed because macOS aliases /var to /private/var; fixed by comparing resolved paths. No Cadence execution occurred."}
    (output / "local_validation_v1.1.0.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    target = output / "project1_probe_v1.1.0.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for name in MEMBERS:
            z.write(probe / name, "project1_handoff/probe_v1_1/" + name)
        z.writestr("project1_handoff/probe_v1_1/package_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(z.read("project1_handoff/probe_v1_1/" + name)).hexdigest() == digest
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / (target.name + ".sha256")).write_text(digest + "  " + target.name + "\n")
    print(json.dumps({"zip": str(target), "bytes": target.stat().st_size,
                      "tests_passed": result.testsRun, "sha256": digest,
                      "cadence": "NOT_RUN"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
