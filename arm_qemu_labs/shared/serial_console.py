"""
serial_console.py — ARM QEMU Lab Notebook Series
pexpect-based serial console over TCP socket.

Responsibilities:
  - connect(host, port) — wraps pexpect over a netcat TCP socket
  - wait_for_prompt(timeout) — blocks until shell prompt appears
  - login(user, password) — handles Ubuntu cloud-image login sequence
  - run_command(cmd, timeout) — send command, capture output until next prompt
  - grep_output(pattern) — regex search on last captured output
  - read_log_until(pattern, timeout) — scan raw serial stream for pattern

Author: Aruna B Kumar | March 2026
Dependency: pexpect (pip install pexpect)
"""

import re
import socket
import time
from typing import Optional

try:
    import pexpect
except ImportError as exc:
    raise ImportError(
        "pexpect is required: pip install pexpect"
    ) from exc


# ── Prompt patterns ────────────────────────────────────────────────────────────

# Ubuntu 24.04 default shell prompts
_SHELL_PROMPTS = [
    r"\$\s*$",       # regular user
    r"#\s*$",        # root
    r"ubuntu@.*\$",  # cloud-image default
]
_LOGIN_PROMPT = r"login:\s*$"
_PASSWORD_PROMPT = r"[Pp]assword:\s*$"
_CLOUD_INIT_DONE = r"Cloud-init.*finished"


class SerialConsole:
    """
    pexpect wrapper for QEMU serial console (TCP socket backend).

    Usage:
        sc = SerialConsole(port=launcher.serial_port)
        sc.connect()
        sc.login("ubuntu", "arm-lab-2026")
        out = sc.run_command("dmesg | grep GIC")
        sc.close()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = None):
        if port is None:
            raise ValueError("port is required")
        self.host = host
        self.port = port
        self._child: Optional[pexpect.spawn] = None
        self._last_output: str = ""

    # ── Connection lifecycle ───────────────────────────────────────────────────

    def connect(self, timeout: float = 60.0) -> "SerialConsole":
        """
        Wait for the serial TCP port to open, then attach pexpect.
        The port is opened by QEMU at launch; this may take a few seconds.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                s = socket.create_connection((self.host, self.port), timeout=2)
                s.close()
                break
            except (ConnectionRefusedError, OSError):
                time.sleep(0.5)
        else:
            raise TimeoutError(
                f"Serial port {self.port} not open after {timeout}s"
            )

        # Use netcat to relay TCP → pexpect stdin/stdout
        self._child = pexpect.spawn(
            f"nc {self.host} {self.port}",
            timeout=180,
            encoding="utf-8",
            codec_errors="replace",
        )
        print(f"[serial_console] Connected to serial on port {self.port}")
        return self

    def close(self) -> None:
        """Terminate the pexpect/nc subprocess."""
        if self._child and self._child.isalive():
            self._child.close(force=True)
        self._child = None
        print("[serial_console] Closed")

    # ── Boot sequence helpers ──────────────────────────────────────────────────

    def wait_for_boot(self, timeout: float = 180.0) -> str:
        """
        Wait for the guest to reach a login prompt.
        Returns all serial output captured during boot.
        """
        patterns = [_LOGIN_PROMPT, r"ubuntu login:"]
        idx = self._child.expect(patterns, timeout=timeout)
        boot_log = self._child.before + self._child.after
        self._last_output = boot_log
        print("[serial_console] Login prompt detected")
        return boot_log

    def login(
        self,
        username: str = "ubuntu",
        password: str = "arm-lab-2026",
        timeout: float = 60.0,
    ) -> str:
        """
        Perform username/password login on the serial console.
        Handles both fresh-boot and already-at-prompt cases.
        """
        # Send username
        self._child.sendline(username)
        idx = self._child.expect(
            [_PASSWORD_PROMPT, r"[Pp]assword:", pexpect.TIMEOUT],
            timeout=timeout,
        )
        if idx == 2:
            raise TimeoutError("Password prompt not seen after sending username")

        # Send password
        self._child.sendline(password)
        shell_patterns = _SHELL_PROMPTS + [r"Login incorrect", pexpect.TIMEOUT]
        idx = self._child.expect(shell_patterns, timeout=timeout)
        if idx == len(_SHELL_PROMPTS):
            raise PermissionError("Login failed: incorrect credentials")
        if idx == len(_SHELL_PROMPTS) + 1:
            raise TimeoutError("Shell prompt not seen after login")

        self._last_output = self._child.before + self._child.after
        print(f"[serial_console] Logged in as {username}")
        return self._last_output

    # ── Command execution ──────────────────────────────────────────────────────

    def run_command(self, cmd: str, timeout: float = 30.0) -> str:
        """
        Send `cmd` to the shell, wait for the next prompt, return output.
        Strips the echoed command from the output.
        """
        self._child.sendline(cmd)
        patterns = _SHELL_PROMPTS + [pexpect.TIMEOUT]
        idx = self._child.expect(patterns, timeout=timeout)
        if idx == len(_SHELL_PROMPTS):
            raise TimeoutError(
                f"Command '{cmd}' timed out after {timeout}s"
            )
        raw = self._child.before or ""
        # Strip leading echo of the command itself
        lines = raw.splitlines()
        if lines and cmd.strip() in lines[0]:
            lines = lines[1:]
        output = "\n".join(lines).strip()
        self._last_output = output
        return output

    def send_raw(self, text: str) -> None:
        """Send raw text without appending newline."""
        self._child.send(text)

    def sendline(self, line: str) -> None:
        """Send a line with newline appended."""
        self._child.sendline(line)

    # ── Output inspection ──────────────────────────────────────────────────────

    def grep_output(self, pattern: str, text: str = None) -> Optional[str]:
        """
        Regex search on `text` (defaults to last captured output).
        Returns first match string or None.
        """
        haystack = text if text is not None else self._last_output
        m = re.search(pattern, haystack, re.MULTILINE)
        return m.group(0) if m else None

    def read_log_until(self, pattern: str, timeout: float = 60.0) -> str:
        """
        Read raw serial stream until `pattern` matches or timeout.
        Returns all text captured up to and including the match.
        """
        idx = self._child.expect([pattern, pexpect.TIMEOUT], timeout=timeout)
        captured = (self._child.before or "") + (self._child.after or "")
        self._last_output = captured
        if idx == 1:
            raise TimeoutError(
                f"Pattern {pattern!r} not seen in serial output after {timeout}s"
            )
        return captured

    def wait_for_prompt(self, timeout: float = 30.0) -> str:
        """Block until a shell prompt appears; return preceding output."""
        patterns = _SHELL_PROMPTS + [pexpect.TIMEOUT]
        idx = self._child.expect(patterns, timeout=timeout)
        if idx == len(_SHELL_PROMPTS):
            raise TimeoutError(f"Prompt not seen after {timeout}s")
        self._last_output = self._child.before or ""
        return self._last_output

    @property
    def last_output(self) -> str:
        """Last output captured by run_command or read_log_until."""
        return self._last_output
