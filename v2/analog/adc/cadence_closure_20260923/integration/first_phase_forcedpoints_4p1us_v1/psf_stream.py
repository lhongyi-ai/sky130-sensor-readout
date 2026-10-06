#!/usr/bin/env python3
"""Small-memory PSFASCII reader for scalar voltage traces, with GROUP 1 aliases."""
import gzip
import math
from pathlib import Path
import re


class Trace:
    def __init__(self, path, wanted=None):
        self.path = Path(path)
        self.wanted = set(wanted) if wanted is not None else None
        self.names = []
        self.types = {}
        self.header = {}
        self.identical_duplicate_rows = 0

    def rows(self):
        opener = gzip.open if self.path.suffix == ".gz" else open
        aliases, pending, section, current, previous = {}, None, "header", None, None
        with opener(self.path, "rt") as f:
            for line in f:
                line = line.strip()
                if line == "TRACE":
                    section = "trace"
                    continue
                if line == "VALUE":
                    section = "value"
                    if self.wanted is not None and not self.wanted.issubset(self.names):
                        raise ValueError("Requested trace missing: " + str(self.wanted-set(self.names)))
                    continue
                if section == "header":
                    quoted = re.fullmatch(r'"([^"]+)"\s+"([^"]*)"', line)
                    if quoted:
                        self.header[quoted[1]] = quoted[2]
                        continue
                if section == "trace":
                    g = re.fullmatch(r'"([^"]+)" GROUP (\d+)', line)
                    if g:
                        if g[2] != "1":
                            raise ValueError("Only scalar GROUP 1 is supported")
                        pending = g[1]
                        continue
                    g = re.match(r'^"([^"]+)"\s+"([^"]+)"', line)
                    if g:
                        name, kind = g.groups()
                        if pending is not None:
                            aliases[pending] = name
                            pending = None
                        if kind == "V":
                            self.names.append(name)
                            self.types[name] = kind
                    continue
                m = re.fullmatch(r'"([^"]+)"\s+([-+.0-9eE]+)', line)
                if not m:
                    continue
                name, value = m[1], float(m[2])
                if section == "header":
                    self.header[name] = value
                elif section == "value":
                    if name == "time":
                        if current is not None:
                            self._validate(current)
                            if previous is not None and current["time"] <= previous["time"]:
                                if current == previous:
                                    self.identical_duplicate_rows += 1
                                else:
                                    raise ValueError("Nonincreasing/distinct same-time data; no silent deduplication")
                            else:
                                yield current
                                previous = current
                        current = {"time": value}
                    else:
                        name = aliases.get(name, name)
                        if name in self.types and (self.wanted is None or name in self.wanted):
                            if current is None:
                                raise ValueError("Voltage before first time")
                            current[name] = value
            if current is not None:
                self._validate(current)
                if previous is None or current["time"] > previous["time"]:
                    yield current
                elif current == previous:
                    self.identical_duplicate_rows += 1
                else:
                    raise ValueError("Final same-time/nonmonotonic row")

    def _validate(self, row):
        wanted = self.wanted if self.wanted is not None else set(self.names)
        if set(row) != wanted | {"time"}:
            raise ValueError("Incomplete saved row")
        if not all(math.isfinite(v) for v in row.values()):
            raise ValueError("Nonfinite saved waveform")
