#!/usr/bin/env python3
"""Read-only EDA metadata collection; all writes stay under this handoff folder.

Python 3.6+, stdlib only. Does not source startup scripts, run simulations,
query license servers, copy model bodies, or modify OpenAccess libraries.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import uuid
import zipfile

BASE = Path(__file__).resolve().parent
VERSION = "1.1.0"
TOOLS = ("virtuoso", "spectre", "ocean", "xrun", "irun", "amsDesigner",
         "pvs", "pegasus", "assura", "qrc", "quantus", "strmIn", "strmOut")
SENSITIVE = re.compile(r"password|passwd|token|secret|license|licen[cs]e|270\d+@", re.I)
KNOWN_PDK = Path("/project/engineering/cadence21/CDK/sky130_release_0.0.3")


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_lines(text):
    return "\n".join(line for line in text.splitlines() if not SENSITIVE.search(line))[:6000]


def run_readonly(argv, keep_pattern=None):
    try:
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=15, universal_newlines=True, errors="replace")
        output = p.stdout
        if keep_pattern:
            output = "\n".join(line for line in output.splitlines() if re.search(keep_pattern, line, re.I))
        return {"returncode": p.returncode, "output": safe_lines(output)}
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT_15S"}
    except OSError as exc:
        return {"status": "EXECUTION_ERROR", "error": str(exc)}


def tool_inventory(search_path):
    result = {}
    for name in TOOLS:
        exe = shutil.which(name, path=search_path)
        result[name] = {"path": exe, "state": "FOUND_NOT_EXECUTED" if exe else "NOT_ON_THIS_PATH"}
        if exe:
            result[name]["resolved_path"] = str(Path(exe).resolve())
            if name == "pvs" and Path(exe).resolve().name == "lvm":
                result[name]["state"] = "NAME_COLLISION_LINUX_LVM_NOT_CADENCE"
    # Spectre -W and -h print version/help only, with no input deck.
    exe = result["spectre"]["path"]
    if exe:
        result["spectre"]["version_query"] = run_readonly([exe, "-W"])
        help_result = run_readonly([exe, "-h", "tran"], r"noise|noisetran")
        result["spectre"]["tran_help_status"] = {k: v for k, v in help_result.items() if k != "output"}
        result["spectre"]["noise_help_mentions"] = [
            line for line in help_result.get("output", "").splitlines()
            if re.search(r"noise(fmax|fmin|seed|update)?|noisetran", line, re.I)]
    return result


def expand_location(value, parent):
    value = os.path.expandvars(os.path.expanduser(value))
    if "$" in value:
        return None
    path = Path(value)
    return path if path.is_absolute() else parent / path


def cds_inventory(entry):
    """Follow bounded INCLUDEs; retain declarations/locations, never whole files."""
    queue, visited, definitions, notes = [entry], set(), [], []
    while queue and len(visited) < 40:
        p = queue.pop(0).resolve()
        if p in visited:
            continue
        visited.add(p)
        try:
            if p.stat().st_size > 512 * 1024:
                notes.append({"file": str(p), "status": "SKIPPED_SIZE_LIMIT"})
                continue
            lines = p.read_text(errors="replace").splitlines()
        except OSError as exc:
            notes.append({"file": str(p), "status": "UNREADABLE", "error": str(exc)})
            continue
        for number, line in enumerate(lines, 1):
            if SENSITIVE.search(line):
                continue
            try:
                fields = shlex.split(line, comments=True)
            except ValueError:
                continue
            if not fields:
                continue
            op = fields[0].upper()
            if op in ("INCLUDE", "SOFTINCLUDE") and len(fields) == 2:
                target = expand_location(fields[1], p.parent)
                if target:
                    queue.append(target)
                else:
                    notes.append({"file": str(p), "line": number, "status": "UNRESOLVED_VARIABLE"})
            elif op == "DEFINE" and len(fields) >= 3:
                name = fields[1]
                if name == "project1" or "sky130" in name.lower() or name in ("analogLib", "basic"):
                    target = expand_location(fields[2], p.parent)
                    definitions.append({"name": name, "path": str(target) if target else fields[2],
                                        "exists": target.exists() if target else None,
                                        "source": str(p), "line": number})
            elif op in ("UNDEFINE", "ASSIGN"):
                notes.append({"file": str(p), "line": number, "status": "DIRECTIVE_NOT_INTERPRETED", "directive": op})
    return {"entry": str(entry), "definitions": definitions, "notes": notes,
            "scan_limit_reached": bool(queue), "authority": "TEXT_HINTS_ONLY_CADENCE_REPORT_IS_AUTHORITATIVE"}


def model_metadata(path):
    """Return names only, no model parameter values or rule-deck content."""
    data = {"path": str(path), "sections": [], "subcircuits": [], "statistics_keyword": False}
    try:
        data["size_bytes"] = path.stat().st_size
        sections, subckts = set(), set()
        with path.open(errors="replace") as f:
            used = 0
            for line in f:
                used += len(line)
                if used > 2 * 1024 * 1024:
                    data["header_scan_truncated"] = True
                    break
                if SENSITIVE.search(line) or line.lstrip().startswith(("*", "//")):
                    continue
                for pattern, dest in [(r"^\s*section\s+([\w.-]+)", sections),
                                      (r"^\s*\.lib\s+([\w.-]+)\s*$", sections),
                                      (r"^\s*\.?subckt\s+([\w.-]+)", subckts)]:
                    m = re.search(pattern, line, re.I)
                    if m and len(dest) < 80:
                        dest.add(m.group(1))
                if re.search(r"^\s*statistics\s*\{", line, re.I):
                    data["statistics_keyword"] = True
        data["sections"], data["subcircuits"] = sorted(sections), sorted(subckts)
    except OSError as exc:
        data["error"] = str(exc)
    return data


def scan_pdk(roots):
    models, rules, visited, errors = [], [], set(), []
    directories = []
    file_count = 0
    limited = False
    for root in roots:
        root = Path(root).resolve()
        if not root.is_dir():
            errors.append({"path": str(root), "status": "NOT_A_DIRECTORY"})
            continue
        for current, dirs, files in os.walk(str(root), followlinks=False,
                                             onerror=lambda e: errors.append({"error": str(e)})):
            current = Path(current)
            if current in visited:
                dirs[:] = []
                continue
            visited.add(current)
            depth = len(current.relative_to(root).parts)
            if depth <= 2 and len(directories) < 300:
                directories.append({"path": str(current), "subdirectories": sorted(dirs)[:80]})
            dirs[:] = sorted((d for d in dirs if not d.startswith(".") and d not in
                             ("doc", "docs", "documentation", "examples", "html", "libs", "oa", "symbol", "layout", "schematic", "auLvs", "auCdl")),
                             key=lambda d: (0 if re.search(r"model|spectre|corner|rule|drc|lvs|rcx", d, re.I) else 1 if re.search(r"nfet.*01v8|pfet.*01v8|res_", d) else 2, d))
            if depth >= 5:
                dirs[:] = []
                limited = True
            for name in sorted(files):
                file_count += 1
                if file_count > 12000:
                    limited = True
                    break
                path = current / name
                if SENSITIVE.search(name):
                    continue
                low = str(path).lower()
                if path.suffix.lower() in (".scs", ".spice", ".sp", ".lib", ".model", ".mdl", ".spectre") and name != "cds.lib":
                    if len(models) < 160:
                        models.append(model_metadata(path))
                    else:
                        limited = True
                if re.search(r"drc|lvs|qrc|quantus|pegasus|assura|techgen|rcx|\.map$", low):
                    if len(rules) < 160:
                        rules.append(str(path))
                    else:
                        limited = True
            if file_count > 12000:
                break
        if file_count > 12000:
            break
    return {"roots": [str(p) for p in roots], "model_headers": models,
            "rule_path_candidates": rules, "directory_index": directories, "errors": errors, "bounded_scan": True,
            "limit_reached": limited, "inspected_filenames": file_count,
            "qualification": "LOCATIONS_ONLY_NOT_MODEL_OR_RULE_QUALIFICATION"}


def active_run(base):
    state = json.loads((base / "active_run.json").read_text())
    run = base / "runs" / state["run_id"]
    if not re.fullmatch(r"[0-9TZ]+_[a-f0-9]{8}", state["run_id"]) or run.resolve().parent != (base / "runs").resolve():
        raise ValueError("Invalid run path")
    return state, run


def probe(base, cds, roots):
    runid = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    run = base / "runs" / runid
    run.mkdir(parents=True, exist_ok=False)
    libs = cds_inventory(cds)
    search_roots = list(roots)
    if KNOWN_PDK.is_dir():
        search_roots.append(KNOWN_PDK)
    for entry in libs["definitions"]:
        if "sky130" in entry["name"].lower() and entry["exists"]:
            p = Path(entry["path"])
            search_roots.append(p)
            # PDK model directories commonly sit next to the OA library.
            for ancestor in list(p.parents)[:3]:
                if "sky130" in ancestor.name.lower():
                    search_roots.insert(0, ancestor)
    search_roots = list(dict.fromkeys(str(Path(p).resolve()) for p in search_roots))[:12]
    report = {"schema_version": 1, "package_version": VERSION, "run_id": runid,
              "status": "LINUX_METADATA_ONLY", "platform": platform.system(),
              "python": platform.python_version(), "terminal_tools": tool_inventory(os.environ.get("PATH", "")),
              "libraries": libs, "pdk": scan_pdk(search_roots),
              "cadence_simulation": "NOT_RUN", "license_checkout": "NOT_TESTED"}
    write_json(run / "linux_report.json", report)
    # JSON quoting is compatible with SKILL strings for these filesystem paths.
    loader = '(load ' + json.dumps(str(base / "probe_cadence.il")) + ')\n'
    loader += '(p1Probe ' + json.dumps(str(run)) + ' ' + json.dumps(runid) + ')\n'
    (run / "load_probe.il").write_text(loader)
    write_json(base / "active_run.json", {"run_id": runid})
    print("Terminal checks complete. This is not a simulation pass.\nEnter the following at the bottom of the main Cadence window:\n")
    print('load(' + json.dumps(str(run / "load_probe.il")) + ')')
    print("\nAfter PROJECT1_PROBE_COMPLETE appears, return to this terminal and run:\nbash run.sh collect")
    print("If Cadence reports an error, run collect anyway and return the partial report and error text.")
    return run


def collect(base):
    state, run = active_run(base)
    linux = json.loads((run / "linux_report.json").read_text())
    report_path = run / "cadence_report.txt"
    text = report_path.read_text(errors="replace") if report_path.exists() else ""
    complete = ('PROBE_COMPLETE\t"' + state["run_id"] + '"') in text.splitlines()
    required_ok = "CORE_METADATA_OK\tt" in text.splitlines()
    paths = {}
    if (run / "cadence_paths.txt").exists():
        for line in (run / "cadence_paths.txt").read_text(errors="replace").splitlines():
            key, sep, value = line.partition("\t")
            if sep and key in ("PATH", "CDSHOME", "MMSIMHOME", "SPECTREHOME"):
                paths[key] = value
    extra = tool_inventory(paths["PATH"]) if paths.get("PATH") else {}
    write_json(run / "cadence_tools.json", {"origin": "LIVE_VIRTUOSO_PATH", "tools": extra})
    live_roots = []
    for line in text.splitlines():
        if line.startswith("LIBRARY\t"):
            strings = re.findall(r'"(?:[^"\\]|\\.)*"', line)
            if len(strings) >= 2:
                try:
                    name, location = [json.loads(s) for s in strings[:2]]
                    if "sky130" in name.lower() and Path(location).is_absolute():
                        p = Path(location)
                        live_roots.append(p)
                        for ancestor in list(p.parents)[:3]:
                            if "sky130" in ancestor.name.lower():
                                live_roots.insert(0, ancestor)
                except ValueError:
                    pass
    pdk_index = scan_pdk(list(dict.fromkeys(live_roots))[:12])
    write_json(run / "cadence_pdk_index.json", pdk_index)
    problems = []
    if not any(line.startswith("SPECTRE_CDF\t") and "nfet_01v8" in line for line in text.splitlines()):
        problems.append("NMOS_SPECTRE_CDF_MAPPING_NOT_COLLECTED")
    if not any(m.get("sections") for m in pdk_index["model_headers"] + linux["pdk"]["model_headers"]):
        problems.append("MODEL_SECTION_ENTRYPOINT_NOT_COLLECTED")
    if not complete:
        problems.append("CADENCE_PROBE_INCOMPLETE_OR_NOT_RUN")
    if not required_ok:
        problems.append("PROJECT1_OR_TECH_METADATA_NOT_CONFIRMED")
    if "CELL_ERROR\t" in text:
        problems.append("SOME_CELL_METADATA_READS_FAILED")
    if not (linux["terminal_tools"]["spectre"]["path"] or extra.get("spectre", {}).get("path")):
        problems.append("SPECTRE_NOT_FOUND_ON_OBSERVED_PATHS")
    summary = {"schema_version": 1, "run_id": state["run_id"],
               "status": "METADATA_COLLECTED_REQUIRES_REVIEW" if complete and required_ok else "PARTIAL_REPORT",
               "cadence_probe_complete": complete, "issues": problems,
               "simulation": "NOT_RUN", "license_checkout": "NOT_TESTED",
               "device_multiplier_semantics": "NOT_QUALIFIED",
               "pcell_legal_dimensions": "NOT_QUALIFIED",
               "noise_mismatch_drc_lvs_pex": "NOT_RUN",
               "next_action": "Return this ZIP to Codex for adapter preparation. Do not run M0-M5 yet."}
    write_json(run / "summary.json", summary)
    # Explicit allowlist: never include PDK files, terminal history, or arbitrary logs.
    names = ["linux_report.json", "cadence_tools.json", "cadence_pdk_index.json", "summary.json"]
    if report_path.exists():
        (run / "cadence_report_share.txt").write_text("\n".join(
            line for line in text.splitlines() if not SENSITIVE.search(line)) + "\n")
        names.append("cadence_report_share.txt")
    integrity = {name: sha(run / name) for name in names}
    write_json(run / "report_manifest.json", {"run_id": state["run_id"], "sha256": integrity})
    names.append("report_manifest.json")
    suffix = datetime.datetime.now(datetime.timezone.utc).strftime("%H%M%S") + "_" + uuid.uuid4().hex[:4]
    target = base / ("project1_report_" + state["run_id"] + "_" + suffix + ".zip")
    with zipfile.ZipFile(str(target), "x", zipfile.ZIP_DEFLATED) as z:
        for name in names:
            z.write(str(run / name), state["run_id"] + "/" + name)
    print("Please download and return:\n" + str(target))
    print("Report status: " + summary["status"] + "; no circuit simulation has been run.")
    return target, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("probe", "collect"))
    parser.add_argument("--cds-lib", default=str(Path.home() / "cadence_skywater" / "cds.lib"))
    parser.add_argument("--pdk-root", action="append", default=[], help="Optional known PDK root; bounded read-only scan")
    args = parser.parse_args()
    if args.action == "probe":
        probe(BASE, Path(args.cds_lib).expanduser().resolve(), args.pdk_root)
    else:
        collect(BASE)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as exc:
        print("Checks incomplete: " + str(exc) + "\nPreserve and return this error text; do not modify the PDK or license.", file=sys.stderr)
        sys.exit(2)
