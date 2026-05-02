"""Distill verbose test/CLI output into compact :class:`CommandResultPacket`s.

Currently parses pytest, jest, mocha, and a generic fallback. The aim is not
perfect parsing but a stable, low-token representation of the failure surface
so an agent never has to ingest raw logs again.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from contextmesh.packets.schema import CommandResultPacket, TestFailurePacket

PYTEST_FILE_LINE = re.compile(r"^([^\s:]+\.py):(\d+):\s*(.*)$")
JEST_FAIL = re.compile(r"^\s*✕\s+(.*?)(?:\s+\(\d+\s*ms\))?$")
JEST_AT = re.compile(r"^\s*at\s+.*?\(([^:]+):(\d+):(\d+)\)")


def _build_pytest_failure(test_name: str, trace: list[str]) -> TestFailurePacket:
    file_path = "unknown"
    line_num: int | None = None
    assertion: str | None = None

    for line in reversed(trace):
        m = PYTEST_FILE_LINE.match(line.strip())
        if m:
            file_path = m.group(1)
            line_num = int(m.group(2))
            assertion = m.group(3) or assertion
            break

    e_lines = [ln[4:].strip() for ln in trace if ln.startswith("E   ")]
    if e_lines:
        assertion = e_lines[0]

    relevant = [ln for ln in trace if ln.startswith(">") or ln.startswith("E   ")]
    minimal_trace = "\n".join(relevant) if relevant else "\n".join(trace[-5:])
    return TestFailurePacket(
        test=test_name,
        file=file_path,
        line=line_num,
        assertion=assertion,
        minimal_trace=minimal_trace.strip(),
    )


def parse_pytest_output(command: str, exit_code: int, output: str) -> CommandResultPacket:
    failures: list[TestFailurePacket] = []
    in_failures = False
    current_test: str | None = None
    current_trace: list[str] = []

    for raw in output.splitlines():
        line = raw.rstrip()
        if line.startswith("===") and "FAILURES" in line:
            in_failures = True
            continue
        if line.startswith("===") and in_failures and "FAILURES" not in line:
            if current_test:
                failures.append(_build_pytest_failure(current_test, current_trace))
                current_test, current_trace = None, []
            in_failures = False
            continue

        if in_failures:
            if line.startswith("___") and line.endswith("___"):
                if current_test:
                    failures.append(_build_pytest_failure(current_test, current_trace))
                current_test = line.strip("_ ")
                current_trace = []
            elif current_test is not None:
                current_trace.append(line)

    if current_test:
        failures.append(_build_pytest_failure(current_test, current_trace))

    if exit_code != 0 and not failures:
        failures.append(TestFailurePacket(
            test="unknown",
            file="unknown",
            minimal_trace=output[-1000:],
        ))

    return CommandResultPacket(
        command=command,
        status="success" if exit_code == 0 else "failed",
        failures=failures,
        new_failures_since_last_run=len(failures),
        fixed_failures_since_last_run=0,
    )


def parse_jest_output(command: str, exit_code: int, output: str) -> CommandResultPacket:
    failures: list[TestFailurePacket] = []
    lines = output.splitlines()
    i = 0
    while i < len(lines):
        m = JEST_FAIL.match(lines[i])
        if m:
            test_name = m.group(1).strip()
            block: list[str] = []
            j = i + 1
            while j < len(lines) and not (JEST_FAIL.match(lines[j]) or lines[j].startswith("Tests:")):
                block.append(lines[j])
                j += 1

            file_path = "unknown"
            line_num: int | None = None
            for ln in block:
                at = JEST_AT.match(ln)
                if at:
                    file_path = at.group(1)
                    line_num = int(at.group(2))
                    break

            assertion = next(
                (ln.strip() for ln in block if "Expected" in ln or "expect(" in ln),
                None,
            )
            minimal = "\n".join(ln for ln in block if ln.strip())[:500]
            failures.append(TestFailurePacket(
                test=test_name,
                file=file_path,
                line=line_num,
                assertion=assertion,
                minimal_trace=minimal,
            ))
            i = j
            continue
        i += 1

    if exit_code != 0 and not failures:
        failures.append(TestFailurePacket(
            test="unknown",
            file="unknown",
            minimal_trace=output[-1000:],
        ))

    return CommandResultPacket(
        command=command,
        status="success" if exit_code == 0 else "failed",
        failures=failures,
        new_failures_since_last_run=len(failures),
    )


def _detect_runner(command_parts: Iterable[str]) -> str:
    parts = list(command_parts)
    head = " ".join(parts).lower()
    if any("pytest" in p for p in parts) or " -m pytest" in head:
        return "pytest"
    if "jest" in head or "vitest" in head:
        return "jest"
    if "mocha" in head:
        return "jest"  # close enough; mocha output is similar
    if parts[:2] == ["npm", "test"] or parts[:2] == ["yarn", "test"]:
        return "jest"
    return "generic"


def distill_command_output(
    command_parts: list[str],
    exit_code: int,
    output: str,
) -> CommandResultPacket:
    command_str = " ".join(command_parts)
    runner = _detect_runner(command_parts)
    if runner == "pytest":
        return parse_pytest_output(command_str, exit_code, output)
    if runner == "jest":
        return parse_jest_output(command_str, exit_code, output)

    failures: list[TestFailurePacket] = []
    if exit_code != 0:
        failures.append(TestFailurePacket(
            test="generic_command",
            file="unknown",
            minimal_trace=output[-1000:],
        ))
    return CommandResultPacket(
        command=command_str,
        status="success" if exit_code == 0 else "failed",
        failures=failures,
        truncated_output_tail=output[-500:] if len(output) > 500 else None,
    )
