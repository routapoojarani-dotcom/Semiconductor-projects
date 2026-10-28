# RISC-V SoC Integration & FPGA Performance Analysis

This project builds and analyzes a lightweight RISC-V SoC prototype on FPGA. The work focuses on understanding how a small RISC-V CPU core is integrated with memory, firmware, and memory-mapped peripherals, and how different SPI Flash access modes affect instruction-fetch performance.

The project is based on the PicoRV32 / PicoSoC architecture and reorganized as an FPGA-oriented SoC study, covering CPU instruction verification, SoC integration, bare-metal boot flow, peripheral access, simulation, and storage performance analysis.

---

## Project Motivation

The purpose of this project is to understand how a small chip-level system works from reset to program execution. Instead of only checking whether firmware can run, this project focuses on the hardware mechanisms behind the software execution process, including CPU instruction execution, memory access, peripheral mapping, boot initialization, and instruction-fetch performance.

Through this project, I studied how a RISC-V soft CPU is connected with SRAM, SPI Flash, UART, LED/user I/O, and firmware to form a complete lightweight SoC prototype.

---

## Key Features

- Lightweight RISC-V soft-core SoC prototype based on PicoRV32 / PicoSoC
- RV32I / RV32M instruction-level verification
- SRAM, SPI Flash, UART, and LED/user I/O integration
- Memory-mapped I/O address decoding
- Bare-metal boot flow analysis from reset to `main()`
- SPI Flash instruction-fetch performance comparison
- RTL simulation and trace-based debugging

---

## System Overview

The system integrates a PicoRV32 RISC-V CPU with on-chip SRAM, external SPI Flash, UART, LED/user I/O, and firmware running in a bare-metal environment.

The main memory-mapped regions used in the project are:

| Component | Address Region / Register | Purpose |
|---|---:|---|
| Internal SRAM | `0x00000000` | Scratchpad memory and runtime data |
| SPI Flash executable region | `0x00100000` | Firmware reset entry and code storage |
| SPI control register | `0x02000000` | SPI Flash mode and configuration control |
| UART data register | `0x02000008` | Serial output and input |
| LED / user I/O | `0x03000000` | Debug status output and external I/O |

In the default PicoSoC configuration, the scratchpad SRAM is configured as **256 words**, which equals **1 KB**. The CPU reset entry is mapped to the Flash address `0x00100000`.

---

## CPU Verification

In the processor verification stage, I focused on the key instruction paths of the RISC-V core. The verification covered arithmetic, memory access, branch/jump behavior, multiplication/division extension, and data dependency cases.

Representative instruction tests include:

```text
add / sub / lw / sw / mul / div / rem
```

These tests helped verify that the CPU could correctly execute:

- ALU arithmetic and logic operations
- load/store memory access
- branch and jump control flow
- RV32M multiplication and division extension
- data dependency and register write-back scenarios

This stage confirmed that the processor core could correctly execute key RISC-V instruction paths before being integrated into the full SoC.

---

## SoC Integration

After CPU-level verification, I integrated the processor into the PicoSoC architecture. The processor was connected with SRAM, SPI Flash, UART, LED/user I/O, and external memory-mapped interfaces.

A key part of this stage was understanding how the CPU accesses hardware peripherals through fixed memory addresses. For example, writing to the UART data register sends serial output, while writing to the LED/user I/O address can be used to observe system status during boot.

This step helped me understand that an SoC is not only a CPU, but a complete system where processor, memory, firmware, and peripherals must work together through address mapping and bus control logic.

---

## Bare-Metal Boot Flow

Because this system does not run an operating system, the CPU cannot directly enter the C `main()` function after reset. Instead, it first executes the low-level startup code in `start.S`.

The boot process includes:

1. General-purpose register initialization
2. Scratchpad memory clearing
3. `.data` section copying from Flash to RAM
4. `.bss` section clearing
5. Jumping into firmware `main()`

During boot debugging, I used LED status values to identify which boot stage the system reached. For example, different values such as `1`, `3`, `7`, and `15` were written to the LED/user I/O address `0x03000000` at different initialization stages. This made it easier to locate where the system stopped when UART output was not yet available.

---

## Firmware and Peripheral Testing

The firmware was used to test the interaction between CPU, memory, and peripherals. It included UART output, SPI Flash configuration, memory testing, and benchmark routines.

The firmware provided a practical way to check whether:

- UART output was working correctly
- SRAM could be written and read correctly
- SPI Flash modes could be configured
- benchmark counters could record cycles and retired instructions
- the SoC could complete the full reset-to-firmware execution path

---

## SPI Flash Performance Analysis

A major part of this project was analyzing how SPI Flash access mode affects instruction-fetch performance. Since the firmware can be executed from memory-mapped SPI Flash, Flash read bandwidth directly affects CPU execution speed.

The benchmark used `rdcycle` and `rdinstret` to measure execution cycles and retired instructions.

Representative result:

| Mode | Instructions | Cycles | Relative Performance |
|---|---:|---:|---:|
| Default SPI | `0x0003df2d` / 253,741 | `0x010f52ef` / 17,781,487 | 1.0× |
| `qspi-ddr-crm-1` | `0x0003df2d` / 253,741 | `0x00233a01` / 2,308,609 | ~7.7× |

The result shows that under the same instruction count, switching from default SPI mode to `qspi-ddr-crm-1` reduced execution cycles by about **87%** and improved instruction-fetch performance by approximately **7.7×**.

This demonstrates that storage access mode can significantly affect the performance of a RISC-V SoC, especially when code is executed directly from external Flash.

---

## Simulation and Debugging

The project uses simulation and trace-based debugging to verify hardware behavior before FPGA deployment.

Main debugging methods include:

- RTL simulation with Verilog testbenches
- waveform inspection using VCD files
- instruction trace analysis
- firmware output through UART
- LED status debugging during boot
- benchmark analysis through cycle and instruction counters

These methods helped verify both functional correctness and performance behavior.

---

## Project Structure

```text
.
├── picorv32.v          # PicoRV32 RISC-V CPU core and related modules
├── picosoc/            # PicoSoC system integration files
├── firmware/           # Bare-metal firmware and startup code
├── tests/              # RISC-V instruction-level tests
├── dhrystone/          # Dhrystone benchmark firmware
├── scripts/            # Tool and synthesis helper scripts
├── testbench.v         # Standard Verilog testbench
├── testbench_ez.v      # Simple standalone testbench
├── testbench_wb.v      # Wishbone testbench
├── showtrace.py        # Trace decoding script
├── Makefile            # Build and simulation targets
└── README.md           # Project documentation
```

---

## Tools and Technologies

- Verilog RTL
- RISC-V RV32I / RV32M
- PicoRV32 / PicoSoC
- Memory-mapped I/O
- SRAM / SPI Flash / UART
- Bare-metal firmware
- RISC-V GCC toolchain
- Icarus Verilog / Verilator
- VCD waveform analysis
- Cycle and instruction counter based benchmarking

---