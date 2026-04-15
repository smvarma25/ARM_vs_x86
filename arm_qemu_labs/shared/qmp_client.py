"""
qmp_client.py — ARM QEMU Lab Notebook Series
QEMU Machine Protocol (QMP) JSON socket client.

Responsibilities:
  - TCP connect to QMP port; capability negotiation handshake
  - send_command(cmd, args) → JSON response dict; raises on QMP error
  - Pre-built wrappers: query_cpus(), query_memory(), query_pci(),
    system_reset(), device_add(), device_del(), object_add()
  - Timeout-safe: all socket reads have configurable timeout
  - Drains async events (SHUTDOWN, RESET, DEVICE_*) transparently

Author: Aruna B Kumar | March 2026
Reference: https://qemu-project.gitlab.io/qemu/interop/qmp-spec.html
"""

import json
import socket
import time
from typing import Any, Dict, Optional


class QMPClient:
    """
    Synchronous QMP client over a TCP socket.

    Usage:
        qmp = QMPClient(port=launcher.qmp_port)
        qmp.connect()
        cpus = qmp.query_cpus()
        qmp.close()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = None):
        if port is None:
            raise ValueError("port is required")
        self.host = host
        self.port = port
        self._sock: Optional[socket.socket] = None
        self._buf: bytes = b""

    # ── Connection lifecycle ───────────────────────────────────────────────────

    def connect(self, timeout: float = 30.0) -> "QMPClient":
        """
        Connect to QMP socket and negotiate capabilities.
        Retries until `timeout` seconds have elapsed.
        """
        deadline = time.monotonic() + timeout
        last_exc = None
        while time.monotonic() < deadline:
            try:
                self._sock = socket.create_connection(
                    (self.host, self.port), timeout=5
                )
                self._sock.settimeout(15)
                # Read the QMP greeting banner
                greeting = self._recv_json(timeout=10)
                assert "QMP" in greeting, f"Unexpected greeting: {greeting}"
                # Negotiate capabilities (required before any command)
                self._send_json({"execute": "qmp_capabilities"})
                ack = self._recv_json(timeout=10)
                assert "return" in ack, f"qmp_capabilities failed: {ack}"
                print(f"[qmp_client] Connected to QMP on port {self.port}")
                return self
            except Exception as exc:
                last_exc = exc
                if self._sock:
                    try:
                        self._sock.close()
                    except Exception:
                        pass
                    self._sock = None
                self._buf = b""
                time.sleep(0.5)
        raise TimeoutError(
            f"QMP connect failed after {timeout}s: {last_exc}"
        )

    def close(self) -> None:
        """Close the QMP socket."""
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        print("[qmp_client] Socket closed")

    # ── Core command interface ─────────────────────────────────────────────────

    def send_command(
        self,
        cmd: str,
        args: Optional[Dict[str, Any]] = None,
        timeout: float = 20.0,
    ) -> Dict:
        """
        Send a QMP command and return the full response dict.

        The method drains asynchronous events (keys: 'event') until a
        'return' or 'error' response arrives.

        Raises RuntimeError on QMP error responses.
        Raises TimeoutError if no response within `timeout` seconds.
        """
        payload: Dict[str, Any] = {"execute": cmd}
        if args:
            payload["arguments"] = args
        self._send_json(payload)

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(1.0, deadline - time.monotonic())
            resp = self._recv_json(timeout=remaining)
            if "event" in resp:
                # Async notification — drain and continue
                continue
            if "error" in resp:
                raise RuntimeError(
                    f"QMP error for '{cmd}': {resp['error']}"
                )
            if "return" in resp:
                return resp
        raise TimeoutError(f"QMP command '{cmd}' timed out after {timeout}s")

    # ── Pre-built command wrappers ─────────────────────────────────────────────

    def query_cpus(self) -> list:
        """Return list of vCPU info dicts (query-cpus-fast)."""
        return self.send_command("query-cpus-fast")["return"]

    def query_memory(self) -> Dict:
        """Return memory size summary dict (query-memory-size-summary)."""
        return self.send_command("query-memory-size-summary")["return"]

    def query_memory_devices(self) -> list:
        """Return list of memory device info dicts (query-memory-devices)."""
        return self.send_command("query-memory-devices")["return"]

    def query_pci(self) -> list:
        """Return PCI bus topology list (query-pci)."""
        return self.send_command("query-pci")["return"]

    def query_machines(self) -> list:
        """Return supported machine types (query-machines)."""
        return self.send_command("query-machines")["return"]

    def query_version(self) -> Dict:
        """Return QEMU version dict (query-version)."""
        return self.send_command("query-version")["return"]

    def system_reset(self) -> Dict:
        """Issue system_reset command; guest performs warm reboot."""
        return self.send_command("system_reset", timeout=10)

    def system_powerdown(self) -> Dict:
        """Request guest ACPI power-down."""
        return self.send_command("system_powerdown", timeout=10)

    def quit(self) -> None:
        """Send QMP quit — terminates QEMU process."""
        try:
            self.send_command("quit", timeout=5)
        except Exception:
            pass  # Socket closes immediately; ignore disconnect errors

    def device_add(self, driver: str, device_id: str = None, **kwargs) -> Dict:
        """
        Hot-plug a device.
        driver     : e.g. 'virtio-blk-device', 'virtio-net-pci'
        device_id  : optional id= for subsequent device_del
        """
        args: Dict[str, Any] = {"driver": driver}
        if device_id:
            args["id"] = device_id
        args.update(kwargs)
        return self.send_command("device_add", args)

    def device_del(self, device_id: str) -> Dict:
        """Hot-remove a device by its id."""
        return self.send_command("device_del", {"id": device_id})

    def object_add(self, qom_type: str, obj_id: str, **props) -> Dict:
        """Add a QOM object (e.g. memory-backend-ram for hot-add RAM)."""
        args: Dict[str, Any] = {"qom-type": qom_type, "id": obj_id}
        args.update(props)
        return self.send_command("object-add", args)

    def object_del(self, obj_id: str) -> Dict:
        """Remove a QOM object by id."""
        return self.send_command("object-del", {"id": obj_id})

    def memsave(self, val: int, size: int, filename: str) -> Dict:
        """Save `size` bytes of guest physical memory starting at `val` to file."""
        return self.send_command(
            "memsave", {"val": val, "size": size, "filename": filename}
        )

    def human_monitor_command(self, command_line: str) -> str:
        """
        Execute a HMP (human monitor) command via QMP bridge.
        Returns the text output string.
        """
        resp = self.send_command(
            "human-monitor-command", {"command-line": command_line}
        )
        return resp["return"]

    # ── Internal I/O ──────────────────────────────────────────────────────────

    def _send_json(self, obj: Dict) -> None:
        data = (json.dumps(obj) + "\n").encode()
        self._sock.sendall(data)

    def _recv_json(self, timeout: float = 15.0) -> Dict:
        """
        Read one newline-delimited JSON object from the socket buffer.
        Accumulates partial data in self._buf.
        """
        self._sock.settimeout(timeout)
        deadline = time.monotonic() + timeout
        while True:
            nl = self._buf.find(b"\n")
            if nl >= 0:
                line = self._buf[:nl]
                self._buf = self._buf[nl + 1 :]
                return json.loads(line)
            try:
                chunk = self._sock.recv(65536)
            except socket.timeout:
                chunk = b""
            if chunk:
                self._buf += chunk
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"QMP recv timeout after {timeout}s; "
                    f"buffer: {self._buf[:200]!r}"
                )
