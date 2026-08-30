# SPIRIT Carrier Board — Design Review
**Date:** 2026-03-25
**Tool:** kicad-happy / analyze_schematic.py + analyze_pcb.py
**Files:** `cm5-carrier.kicad_sch` (hierarchical, 10 sub-sheets), `cm5-carrier.kicad_pcb`

---

## Summary

The schematic design is largely complete but has several functional bugs that will prevent the board from working. The PCB layout is **significantly incomplete** — 79 of 431 nets are unrouted. Neither file is ready for fabrication.

| Area | Status |
|------|--------|
| Schematic — power tree | Mostly OK, flag on I2C pull-ups |
| Schematic — connectivity | **BUGS** — net name mismatch kills display I2C |
| Schematic — BOM completeness | 12 missing MPNs, 1 missing footprint |
| PCB routing | **INCOMPLETE** — 79 unrouted nets (18%) |
| PCB DFM | Advanced process required (fine pitch traces) |
| Automation scripts | **BUG** — set-dnp.py typo |

---

## Critical Issues (board will not function)

### 1. Display I2C net name mismatch — `DIS_SDA` ≠ `DIS SDA`
The CM5 module connects to `DIS_SDA` and `DIS_SCL` (underscore). The display connector DIS1 connects to `DIS SDA` and `DIS SCL` (space). These are **different nets**. The display I2C bus is broken — the two sides are not connected to each other.

- **CM5 side:** `Module1.30` → net `DIS_SDA`, `Module1.37` → net `DIS_SCL`
- **Display side:** `DIS1.26` → net `DIS SDA`, `DIS1.27` → net `DIS SCL`

**Fix:** Rename one set of labels to match the other in KiCad (pick one convention: `DIS_SDA` or `DIS SDA`).

---

### 2. DSI1 Lane 3 not connected to CM5 (single-pin nets)
`DSI1_D3_N` and `DSI1_D3_P` appear only on `DIS1` pins 17 and 18. There is no corresponding connection to the CM5 module. If the display requires all 4 DSI data lanes, this will cause display failure.

- **Affected nets:** `DSI1_D3_N` (DIS1 pin 17), `DSI1_D3_P` (DIS1 pin 18)

**Fix:** Verify the display's DSI lane count. If 4 lanes are needed, connect to CM5 `MIPI1_D3_N/P` (Module1 pins 193/195 per Raspberry Pi CM5 datasheet). If 2-lane mode is sufficient, add no-connect markers.

---

### 3. All I2C buses missing pull-up resistors
The analyzer detected 8 I2C buses, **none have pull-ups flagged**:

| Bus | SCL net | SDA net | Devices |
|-----|---------|---------|---------|
| Power I2C | `SCL PWR` | `SDA PWR` | U7 (BQ25792), U8 (TPS65023B) |
| Audio I2C | `AUDIO_SCL` | `AUDIO_SDA` | U4 (TLV320AIC3204) |
| Camera I2C | `CAM_SCL` | `CAM_SDA` | U12 |
| Display I2C | `DIS_SCL` | `DIS_SDA` | Module1 |
| Charger I2C | `SCL CH` | `SDA CH` | — |

Standard pull-up for 3.3V I2C: 4.7 kΩ to 3V3B. The BQ25792 and TPS65023B share the same bus (SCL PWR / SDA PWR) — confirm their I2C addresses don't conflict (BQ25792 default: 0x6B, TPS65023B: 0x48).

**Fix:** Add pull-up resistors to each I2C bus.

---

### 4. ~~CAM_SCL / CAM_SDA are single-pin nets~~ — FIXED
Camera I2C routed onto I2C5 (GPIO12/GPIO13), shared with the audio codec.

**Changes made:**
- `cm5-carrier.kicad_sch`: `GPIO13` label → `AUDIO_SCL` (GPIO13 is I2C5 SCL on BCM2712)
- `cm5-carrier.kicad_sch`: `AUDIO_SCL` label at GPIO15 → `GPIO15` (frees GPIO15)
- `camera.kicad_sch`: `CAM_SCL` → `AUDIO_SCL`, `CAM_SDA` → `AUDIO_SDA`
- `power.kicad_sch`: `CAM_SCL`/`CAM_SDA` pull-up labels (R48/R49) → `AUDIO_SCL`/`AUDIO_SDA`

**Note:** R46/R47 (audio) and R48/R49 (camera) are now both 4.7kΩ pull-ups on the same bus — effective 2.35kΩ per line. Functional for I2C Fast mode but redundant. Mark R48/R49 DNP once confirmed. Also note: `power.kicad_sch` already had pull-ups for both AUDIO and CAM buses — the design review finding of "missing pull-ups" was incorrect for these two buses.

**Verification required:** Confirm the camera module's I2C address does not conflict with TLV320AIC3204 (0x18/0x19) before assembly.

---

### 5. PCB routing is 18% incomplete — 79 unrouted nets
The board has 79 unrouted nets out of 431 total. Major unrouted subsystems include:

| Subsystem | Unrouted nets |
|-----------|--------------|
| Power rails (1V8, 3V3B, 5V, 22V, SYS) | All unrouted |
| Display (DSI1 lanes D0–D3, clock, I2C, backlight) | All unrouted |
| Audio (I2S clocks, data, codec I2C, reset) | All unrouted |
| Camera (MIPI CSI lanes, I2C, control) | All unrouted |
| USB-C (CC1, CC2) | Unrouted |
| GPIO/control signals | Many unrouted |

**This board cannot be sent for fabrication until routing is complete.** Resume in KiCad: open `cm5-carrier.kicad_pcb`, run DRC to see ratsnest, complete routing for all subsystems.

---

## High Priority Issues (functional risk)

### 6. Cross-domain I2C without level shifter — SCL PWR / SDA PWR
U7 (BQ25792) operates from the VAC PAIR domain; U8 (TPS65023B) from its own internal domain. The analyzer flags these as cross-domain signals requiring level shifting. Verify both ICs are 3.3V I2C compatible and the CM5 I2C lines are 3.3V — if so, a shared 3.3V pull-up to `3V3B` is sufficient and no level shifter is needed. If VAC PAIR is >3.3V, add a level shifter.

### 7. `3V3A` rail has only one connection
Net `3V3A` connects only to `R17 pin 2`. This rail appears to be the output of the TPS65023B DCDC1 converter, but nothing is consuming it. Either it is unused (add no-connect or remove it) or it needs to be connected to downstream loads.

**Context:** SW1 enables/disables DCDC1 via `EN3V3A → EN3V3A-SW-OUT → U8.DCDC1_EN`. If 3V3A is intentional but unused at this point, document it.

### 8. `GPIO13` is a single-pin net
`Module1 pin 28` (GPIO13) connects to nothing else. If this GPIO drives or monitors something (e.g., fingerprint sensor, kill switch), the other end is missing. If unused, add a no-connect marker.

### 9. R11 has no footprint assigned
`R11` (on the SYS rail) has no footprint. This component cannot be placed on the PCB.

**Fix:** Assign a footprint (likely 0402 or 0603 based on other passives in the design) in the schematic symbol properties.

---

## Medium Priority Issues (manufacturing / BOM)

### 10. 12 components missing MPNs — sourcing blocked
Without MPNs, the BOM cannot be submitted to a fab for PCBA quoting. Parts needing MPNs:

| Reference | Value | Type |
|-----------|-------|------|
| Module1 | ComputeModule5-CM5 | CM5 module |
| U7 | BQ25792RQMR | Charger IC |
| U8 | TPS65023BRSBR | PMIC |
| U9 | BAT-CONNECTOR-FLTS22WR00 | Battery connector |
| U10 | 22V-boost-AP3032KTR-G1 | Boost IC |
| SW1 | EG25-switch-CSS-1210MC | Privacy switch |
| SW2 | MIC-switch-CSS-1210MC | Privacy switch |
| SW3 | CAM-switch-CSS-1210MC | Privacy switch |
| L5 | 6.8uH | Inductor |
| F1 | 9A 6V | Fuse |
| LS1, LS2 | AS01506MS-SC15-WP-2-R | Speaker |

Note: U7 and U8 have part numbers in the Value field but need the `MPN` property populated for BOM export tools.

### 11. DFM: Advanced process required at JLCPCB
The tightest trace spacing is **0.1217mm**, below JLCPCB's standard tier limit (0.127mm). This forces the advanced process tier.

Additionally, the board size is **82mm × 155mm** — above the 100×100mm boundary for standard pricing. Expect higher fabrication costs. For first prototypes, this is acceptable; consider panel optimization for volume runs.

### 12. 6-layer stackup with 28 vias — verify layer assignment
The PCB uses 6 copper layers with only 28 vias. Confirm the inner layer assignments are correct for signal integrity (typical: L1=signal, L2=GND, L3=power, L4=signal, L5=GND, L6=signal). Verify controlled impedance for USB-C differential pairs (D+/D−, TX2+/TX2−) — these need 90Ω differential.

---

## Low Priority / Quality

### 13. `set-dnp.py` script has a typo
[automation-kicad-skip-python/set-dnp.py:5](automation-kicad-skip-python/set-dnp.py#L5):
```python
# Wrong:
'audio.kicad_sc.kicad_sch',
# Should be:
'audio.kicad_sch',
```
The script will crash when run. Fix the filename before using it.

### 14. Incomplete symbol file
`component-libs/SPIRIT-symbol-libs/0-1-uf-CAP0603-KRX7R7BB104.kicad_sym_` has a trailing underscore — likely a draft/incomplete file. Rename to `.kicad_sym` once complete, or remove if unused.

### 15. Deleted license files not committed
`licensing/LICENSE-DOCS-AND-WIKI.txt`, `LICENSE-HARDWARE.txt`, `LICENSE-SOFTWARE.txt` were deleted locally but the deletion was never staged/committed. Run `git rm licensing/LICENSE-*.txt && git commit` to clean up, or `git restore licensing/` to recover them.

### 16. `power.kicad_sch` excluded from set-dnp.py
Line 15 of `set-dnp.py` has `# 'power.kicad_sch'` commented out. This may be intentional (power components don't need DNP) or an oversight. Verify intent.

---

## Positive Findings

- Schematic is well-structured with hierarchical sub-sheets for each subsystem
- ESD protection is present on USB differential pairs (TVS-PUSB1) and camera MIPI lanes (U12)
- Differential pairs for MIPI DSI (display), MIPI CSI (camera), and USB are all correctly paired in the netlist
- Audio subsystem (TLV320AIC3204 codec + TPA2038D1 amplifiers) is fully connected to the CM5
- Decoupling capacitors are present on all IC power pins
- Resettable fuse (F1) on BAT+ is a good protection measure
- Power kill switches (SW1/SW2/SW3) for cellular, mic, and camera are implemented

---

## Recommended Fix Order

1. **Fix display I2C net naming** (`DIS_SDA` vs `DIS SDA`) — schematic edit, 5 min
2. **Add I2C pull-ups** to all 5 buses — schematic edit, 30 min
3. **Connect CAM_SCL/CAM_SDA** to CM5 GPIO — schematic edit, 10 min
4. **Verify DSI lane 3** — check display datasheet for lane count requirement
5. **Add MPN to all 12 components** — schematic properties, 30 min
6. **Assign footprint to R11** — schematic properties, 5 min
7. **Complete PCB routing** — KiCad layout, major effort
8. **Fix set-dnp.py typo** — one character fix

---

*Generated files: `schematic_analysis.json`, `pcb_analysis.json`, `design-review.md` — do not commit to git; regenerate as needed.*
