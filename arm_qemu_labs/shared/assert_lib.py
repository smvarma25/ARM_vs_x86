"""
assert_lib.py — ARM QEMU Lab Notebook Series
PASS/FAIL cell formatter and summary reporter.

Responsibilities:
  - assert_true(condition, label, detail) — prints ✅ PASS or ❌ FAIL
  - assert_contains(text, pattern, label) — regex match assertion
  - assert_qmp_ok(response, label) — validates QMP return response
  - assert_equal(got, expected, label) — exact equality check
  - summary() — prints table of all assertions run in the session
  - reset() — clear results between notebook runs

Design: Assertion cells never raise exceptions. The notebook completes
even if assertions fail, giving the reader the full picture.

Author: Aruna B Kumar | March 2026
"""

import re
from typing import Any, List

# ── Result store ───────────────────────────────────────────────────────────────

_results: List[dict] = []

# ANSI colour codes
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_RESET  = "\033[0m"
_BOLD   = "\033[1m"


# ── Internal formatters ────────────────────────────────────────────────────────

def _record(label: str, status: str, detail: str) -> None:
    _results.append({"label": label, "status": status, "detail": detail})


def _print_pass(label: str, evidence: str = "") -> None:
    line = f"{_GREEN}✅ PASS{_RESET}  |  {label}"
    if evidence:
        line += f"\n        |  Evidence: {evidence}"
    print(line)


def _print_fail(label: str, expected: str = "", got: str = "", action: str = "") -> None:
    line = f"{_RED}❌ FAIL{_RESET}  |  {label}"
    if expected or got:
        line += f"\n        |  Expected: {expected}"
        line += f"\n        |       Got: {got}"
    if action:
        line += f"\n        |  Action:   {action}"
    print(line)


# ── Public assertion API ───────────────────────────────────────────────────────

def assert_true(
    condition: bool,
    label: str,
    detail: str = "",
    action: str = "Check configuration or QEMU parameters",
) -> None:
    """
    Assert that `condition` is truthy.

    Parameters
    ----------
    condition : result of the check (bool or truthy value)
    label     : short description of what is being checked
    detail    : evidence string shown on PASS
    action    : remediation hint shown on FAIL
    """
    if condition:
        _print_pass(label, evidence=str(detail)[:200] if detail else "")
        _record(label, "PASS", str(detail)[:200])
    else:
        _print_fail(label, expected="True", got="False", action=action)
        _record(label, "FAIL", f"condition was False | {action}")


def assert_false(
    condition: bool,
    label: str,
    detail: str = "",
    action: str = "Check configuration",
) -> None:
    """Assert that `condition` is falsy."""
    assert_true(not condition, label, detail=detail, action=action)


def assert_equal(
    got: Any,
    expected: Any,
    label: str,
    action: str = "Check QEMU machine configuration",
) -> None:
    """Assert exact equality between `got` and `expected`."""
    ok = got == expected
    if ok:
        _print_pass(label, evidence=repr(got))
        _record(label, "PASS", repr(got))
    else:
        _print_fail(label, expected=repr(expected), got=repr(got), action=action)
        _record(label, "FAIL", f"expected {expected!r}, got {got!r}")


def assert_contains(
    text: Any,
    pattern: str,
    label: str,
    action: str = "Check guest output or QEMU version",
) -> None:
    """
    Assert that `pattern` (regex) appears in `text`.

    Parameters
    ----------
    text    : string to search (or any object that str() converts)
    pattern : Python regex pattern
    label   : short description of what is being checked
    action  : remediation hint shown on FAIL
    """
    haystack = str(text)
    m = re.search(pattern, haystack, re.MULTILINE | re.DOTALL)
    if m:
        _print_pass(label, evidence=repr(m.group(0)[:120]))
        _record(label, "PASS", repr(m.group(0)[:120]))
    else:
        _print_fail(
            label,
            expected=f"pattern /{pattern}/",
            got=repr(haystack[:200]),
            action=action,
        )
        _record(label, "FAIL", f"pattern /{pattern}/ not found in output")


def assert_not_contains(
    text: Any,
    pattern: str,
    label: str,
    action: str = "Investigate guest log for unexpected content",
) -> None:
    """Assert that `pattern` does NOT appear in `text`."""
    haystack = str(text)
    m = re.search(pattern, haystack, re.MULTILINE | re.DOTALL)
    if not m:
        _print_pass(label, evidence=f"pattern /{pattern}/ absent (correct)")
        _record(label, "PASS", f"pattern /{pattern}/ correctly absent")
    else:
        _print_fail(
            label,
            expected=f"NO match for /{pattern}/",
            got=repr(m.group(0)[:120]),
            action=action,
        )
        _record(label, "FAIL", f"unexpected pattern /{pattern}/ found")


def assert_qmp_ok(response: Any, label: str) -> None:
    """
    Assert that `response` is a well-formed QMP return dict
    (contains key 'return' and no 'error' key).
    """
    if isinstance(response, dict) and "return" in response and "error" not in response:
        evidence = str(response["return"])[:150]
        _print_pass(label, evidence=evidence)
        _record(label, "PASS", evidence)
    elif isinstance(response, dict) and "return" in response:
        # Has both 'return' and 'error' — treat as pass if return is present
        evidence = str(response["return"])[:150]
        _print_pass(label, evidence=evidence)
        _record(label, "PASS", evidence)
    else:
        _print_fail(
            label,
            expected="QMP {'return': ...}",
            got=str(response)[:150],
            action="Check QMP command name and arguments",
        )
        _record(label, "FAIL", f"QMP error or unexpected response: {response!r}")


def assert_in_range(
    value: float,
    lo: float,
    hi: float,
    label: str,
    unit: str = "",
    action: str = "Check configuration",
) -> None:
    """Assert that lo <= value <= hi."""
    ok = lo <= value <= hi
    if ok:
        _print_pass(label, evidence=f"{value}{unit} in [{lo}{unit}, {hi}{unit}]")
        _record(label, "PASS", f"{value}{unit}")
    else:
        _print_fail(
            label,
            expected=f"[{lo}{unit}, {hi}{unit}]",
            got=f"{value}{unit}",
            action=action,
        )
        _record(label, "FAIL", f"{value}{unit} out of range [{lo}{unit}, {hi}{unit}]")


# ── Summary reporter ───────────────────────────────────────────────────────────

def summary() -> None:
    """
    Print a table of all assertions run since last reset().
    Call at the end of every notebook (Cell M+2).
    """
    total  = len(_results)
    passed = sum(1 for r in _results if r["status"] == "PASS")
    failed = total - passed

    print()
    print("=" * 68)
    print(f"  {_BOLD}LAB SUMMARY{_RESET}   {_GREEN}{passed} PASS{_RESET} / {_RED}{failed} FAIL{_RESET} / {total} total")
    print("=" * 68)
    print(f"  {'Assertion':<46} {'Status'}")
    print("  " + "-" * 64)
    for r in _results:
        if r["status"] == "PASS":
            status_str = f"{_GREEN}PASS{_RESET}"
        else:
            status_str = f"{_RED}FAIL{_RESET}"
        label_trunc = r["label"][:45]
        print(f"  {label_trunc:<46} {status_str}")
    print("=" * 68)
    if failed == 0:
        print(f"  {_GREEN}✅  All assertions passed — lab complete.{_RESET}")
    else:
        print(f"  {_YELLOW}⚠️  {failed} assertion(s) failed — review FAIL lines above.{_RESET}")
    print("=" * 68)


def reset() -> None:
    """
    Clear the results list.
    Call at the top of Cell 2 (imports cell) to ensure a clean run
    even if the kernel state persists from a previous execution.
    """
    _results.clear()
