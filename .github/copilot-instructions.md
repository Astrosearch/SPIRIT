# SPIRIT Smartphone Project AI Instructions

SPIRIT is an open-source smartphone project built around the Raspberry Pi Compute Module 5 (CM5), focusing on user experience, performance, control, repairability, innovation, and privacy.

## Project Architecture

### Core Design Philosophy
- **Modular hierarchical design**: Hardware is organized into functional subsystems (power, audio, GSM-GPS, camera, etc.)
- **CM5-centric**: All designs revolve around the Raspberry Pi Compute Module 5 as the main computing unit
- **Component availability first**: Uses readily available components rather than custom chips
- **Repairability and modularity**: External add-ons system allows for optional features

### Hardware Structure (KiCad EDA)
- **Main project**: `EDA-kicad/cm5-carrier.kicad_pro` - the primary carrier board design
- **Hierarchical schematics**: Each subsystem has its own `.kicad_sch` file:
  - `power.kicad_sch` - Power management (battery, charging, regulation)
  - `audio.kicad_sch` - Audio codec and amplification
  - `GSM-GPS.kicad_sch` - Cellular and GPS communication
  - `camera.kicad_sch` - Camera interface and control
  - `screen.kicad_sch` - Display interface
  - `USB-C.kicad_sch` - USB-C connectivity
  - `buttons.kicad_sch`, `fingerprint.kicad_sch`, `flashlight.kicad_sch`, `vibration.kicad_sch`

### Component Library Management
- **Custom libraries**: `component-libs/SPIRIT-footprints.pretty/`, `SPIRIT-symbol-libs/`, `SPIRIT-3D-models/`
- **Library merger**: Use `component-libs/library-merger.py` to consolidate symbol libraries from component manufacturers
- **CM5 integration**: `ComputeModule5-libs/` contains official CM5 symbols and footprints

## Development Workflow

### KiCad Design Rules
- **Component preferences**: Panasonic first, then Yageo for passives; minimum 0603 package size for SMD components
- **Required fields**: All components must have Value, Datasheet (except R/C), and MPN fields properly filled
- **Synchronization**: Schematics and PCB must always be in sync - use "Update PCB from Schematic" tool
- **Annotation**: Properly annotate all components in schematics before PCB work
- **Latest KiCad**: Always use the newest major release of KiCad

### Git and Contribution Workflow
1. Check existing issues before starting work
2. Open issue for discussion if one doesn't exist
3. Comment on issue when starting work
4. Create focused, atomic PRs (avoid massive changes)
5. Only modify files you need to change
6. Provide detailed PR descriptions

### External Add-ons System
Located in `external-addons/`: modular optional features like FM radio, SDR recorder, barcode scanner, etc. Each should be self-contained with its own documentation.

## Multi-License Structure
- **Hardware**: CERN Open Hardware Licence Version 2 - Strongly Reciprocal
- **Software/code**: GNU GPLv3
- **Documentation**: Creative Commons BY-SA 4.0
- **Trademarks**: V Electronics logos are NOT open source

## Key Resources
- [SPIRIT Wiki](https://github.com/V3lectronics/SPIRIT/wiki) - Primary documentation
- [CM5 Datasheet](https://datasheets.raspberrypi.com/cm5/cm5-datasheet.pdf)
- [Interactive CM5/CM4 Pinout](https://atctwo.net/projects/pinout/index.html)
- Discord: https://discord.gg/zBG4KdHJWx

## Development Phase Status
Currently in component selection and schematic design phase. Power system is in progress, followed by audio, GPS/GSM, LCD, camera, and peripheral systems. The project follows a roadmap from electronic systems → integration → mechanical chassis → operating system.

When working on this project, always consider the modular design philosophy, component availability constraints, and the focus on repairability and user control.