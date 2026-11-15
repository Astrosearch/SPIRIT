# CM5 carrier — PCBA readiness report

Generated: 2026-11-15 · Toolchain: **awecad** (editor + `awe pcb` CLI) + KiCad 10.0.6 (kicad-cli DRC) · Board: `EDA-kicad/cm5-carrier.kicad_pcb` (6-layer HDI, 1.511 mm)

## What was done (this pass)

1. **Schematic↔PCB netlist resync** (awecad `resyncFromNetlist`, applied to the .kicad_pcb with the same rules):
   - dropped 9 stray/duplicate footprints not in the schematic netlist: `ZD2`, `G***` ×2, `REF**` ×2, duplicate `TP7`, `TP8`, `R8`, `R9`
   - rewrote **310 pad nets** to the schematic netlist authority (labeled net wins over auto-generated `Net-(...)`; e.g. `LCD PWM`→`LCD_PWM`, U14 SSTX/SSRX pin swap, `GPIO15`, `SSTX±`, `SSRX±`)
   - 2 genuine multi-net pin conflicts reported (R43: 3V3B vs `Net-(U14-EN)`, 3V3B vs `SCL PWR`) — schematic-side, needs a schematic decision
   - result: 129 footprints / 148 nets, matching the schematic exactly (net-audit PASS since 38fb87a)

2. **Auto-routing**, two awe stages (both run with the KiCad 10 pcbnew/kicad-cli inside the app-kicad container):
   - `awe pcb fw drive` (improve-only gate): purge-shorts 4 → **0**, stitch same-layer/power phases: unconnected 316 → **261**
   - `awecad_solver` (`python3 -m awecad_solver.solve`, numpy screen + windowed A*, gated batches via `awe pcb fab-ready --check`): unconnected 261 → **119 and falling** (short=0, cross=0 on every kept batch; batches that would raise a short are reverted/bisected automatically). Run log: session scratchpad `solver-repo2.log`; screening clearance set to the board's 0.2 mm rule.

3. **awecad verification (isolated CUA desktop, podman `cua-desktop`)**:
   - imported the board into awecad, "Resync from netlist" is idempotent on the resynced board (`0 pins rewired · removed 0`)
   - interactive routing verified end-to-end via CUA mouse (Route tool → click pads → Enter commits; toast + status bar + persisted track)
   - ECAD tools panel: DRC-lite (15 err / 84 warn), Connectivity report, and **Fab pack (BOM+PnP+health+full CAM)** export — 23 files, downloads land

4. **Fab pack** exported by awecad into `EDA-kicad/fab-pack/` (23 files): ActiveBOM CSV, pick&place CSV, design-health txt/json, BOM completeness, 13 gerbers (F/In1–In4/B Cu, masks, pastes, Edge_Cuts), 7 Excellon drills (npth, plated, per layer-pair).

## Metrics (full kicad-cli DRC, severity-all, uncapped)

| metric | before (02282b0) | after (solver in progress) |
|---|---:|---:|
| footprints | 138 (incl. 9 stray/dup) | 129 (netlist-exact) |
| nets | 449 (fragmented) | 148 (schematic-exact) |
| shorting_items | 2 (fab-ready counted 4 + 8 zero-distance) | **0** |
| unconnected_items | 302 | **119** (was 261 after fw drive; awecad_solver still running) |
| clearance violations | 340 | ~110–150 (tracks added by solver) |
| `awe pcb fab-ready --check` | NOT-FAB-READY (unconn 302, short 4) | NOT-FAB-READY (unconn ~119, short **0**) |

## Remaining work (bare fab = NO-GO until unconn = 0)

~119 unconnected items remain (deep_via / out_of_range / same_layer_long — the dense core). Top net: GND.

- `awecad_solver` continues gated rounds in the background (`solver-repo2.log`); each kept batch has short=0 cross=0 by gate.
- `awe pcb route-safe` (FreeRouting) **times out** on this dense 6L HDI board (900 s full-board; net batches of 10 complete but the improve-only guard rejects them — rip-up cost exceeds gain). Manual routing is the fallback for the residual.
- Route in **awecad** 2D layout editor (route toolbar: pick net → click pads → Enter; verified end-to-end via CUA in the isolated desktop) or Pcbnew; then re-run `awe pcb fab-ready --check`.
- 2 schematic-side pin conflicts on R43 to resolve in the schematic, then re-run the awecad resync.
- Non-blocking DRC noise (track_width 196, text_height 79, courtyard/mask items) — cosmetic/DRC-tuning, not fab blockers for bare board; review before PCBA.

## Reproducing

```bash
# resync PCB to schematic netlist (awecad rules, text-level)
kicad-cli sch export netlist -o cm5-carrier.net cm5-carrier.kicad_sch
python3 pcb_resync.py cm5-carrier.kicad_pcb cm5-carrier.net --write   # see session scratchpad
# auto-route + gate (inside a container with pcbnew)
awe pcb fw drive  EDA-kicad/cm5-carrier.kicad_pcb
awe pcb fab-ready --check EDA-kicad/cm5-carrier.kicad_pcb
kicad-cli pcb drc --severity-all --format report EDA-kicad/cm5-carrier.kicad_pcb
# in awecad: open project → 2D Layout → "Resync from netlist" / "Fab pack (full CAM)" in ECAD tools panel
```
