# ARM / QEMU Platform Architecture Lab Series

A 13-chapter hands-on lab series covering the full Arm platform stack on QEMU — from exception levels through interrupt controllers, power management, ACPI, PCIe, and Neoverse SVE extensions.

Each chapter is a Jupyter notebook that launches a QEMU aarch64 VM, interacts with it via QMP (QEMU Machine Protocol) and serial console, and validates behavior through assertions. All labs run on macOS Apple Silicon (HVF acceleration) or Linux (KVM).

**Author:** Aruna Kumar — Senior SoC Firmware Architect, ex-Intel Sr. Director

## The 13 Chapters

| # | Topic | What You Learn |
|---|-------|----------------|
| 01 | ARM Architecture Overview | ISA fundamentals, register model, instruction encoding |
| 02 | Memory Model | Hierarchy, coherency, memory ordering |
| 03 | Exception Levels | EL0-EL3 privilege levels, secure vs non-secure world |
| 04 | GIC Interrupt Controller | Generic Interrupt Controller, IRQ routing, priorities |
| 05 | PSCI | Power State Coordination Interface, CPU on/off/suspend |
| 06 | SCMI | System Control & Management Interface, clock/power domains |
| 07 | ACPI on ARM | MADT, GTDT, IORT tables — how ARM platforms describe hardware |
| 08 | Device Tree | DT parsing, boot-time hardware description, FDT overlays |
| 09 | SMMUv3 | System Memory Management Unit, IOMMU, DMA isolation |
| 10 | VirtIO | Device emulation, hot-plug, virtio-net/blk/rng on ARM |
| 11 | PCIe on ARM | PCIe MSI-X interrupts, BAR configuration, ECAM |
| 12 | Linux Boot Path | Kernel boot sequence, initramfs, device probing |
| 13 | Neoverse Specifics | SVE/SVE2, Neoverse V3/N3 features, performance counters |

## Shared Infrastructure

```
arm_qemu_labs/shared/
  qmp_client.py       QMP JSON socket client — query CPUs, memory, PCI; add/remove devices
  serial_console.py   Serial console over pexpect — pattern matching, timeout-safe reads
  qemu_launcher.py    QEMU lifecycle — free port allocation, accelerator detection (HVF/KVM)
  assert_lib.py       Test assertions — assert_true, assert_equal, assert_contains, assert_qmp_ok
```

## Tests

```bash
cd arm_qemu_labs && python3 test_shared_modules.py
```

37 tests across 4 modules + 1 cross-module integration test:
- `assert_lib`: 14 tests (assertion methods, summary, reset)
- `qemu_launcher`: 8 tests (port allocation, accelerator detection, lifecycle)
- `qmp_client`: 7 tests (connect, JSON I/O, error handling, fragmented data)
- `serial_console`: 6 tests (instantiation, connect, grep output)
- `cross-module`: 1 test (port collision detection)

## Setup

### Quick Start (macOS Apple Silicon)

```bash
# Install dependencies
pip install -r requirements.txt

# Full environment setup (QEMU, firmware, Ubuntu cloud image)
bash arm_qemu_labs/setup_qemu_labs.sh

# Run tests
cd arm_qemu_labs && python3 test_shared_modules.py

# Open labs
jupyter lab arm_qemu_labs/notebooks/
```

### Requirements

- **QEMU** >= 8.0 with `qemu-system-aarch64` (`brew install qemu`)
- **Python** >= 3.11
- **pexpect** (serial console interaction)
- **macOS**: HVF acceleration (Apple Silicon) or **Linux**: KVM

The setup script (`setup_qemu_labs.sh`) handles Homebrew dependencies, downloads Ubuntu 24.04 ARM64 cloud image, creates cloud-init seed ISO, and verifies the environment.

## Related

- [ARM Software Stack Series](https://github.com/cakesandcode/ARM_SW_Stack) — Arm HPC/AI software stack tutorials (compilers, math libraries, ML frameworks)
- [Silicon Photonics CPO](https://github.com/cakesandcode/CPO_Silicon_Photonics) — CPO platform architecture + Arm Neoverse firmware integration
- [armfirmware.substack.com](https://armfirmware.substack.com) — Published articles

## License

MIT
