# Roadmap: Luca's feature list, scoped

Base: the MS-50G v3.10 OS, which Luca's MS-60B already runs. Every feature is
a patch file applied to Zoom's OS and must apply to the MS-50G, MS-60B and
MS-70CDR builds. Only the MS-60B hardware is available for testing.

Feasibility is an estimate from the disassembly so far, not a promise.

| Feature | Where it lives in the OS | Feasibility | Notes |
|---|---|---|---|
| Flash a modified OS and boot it | build pipeline | **done, tested on MS-60B** | `patches/hello.yaml`, see flashing.md |
| MIDI: program change loads patch, CC controls parameters and on/off, MIDI clock sets tempo | `Task_MIDI`, USB MIDI | high | MS pedals only have USB MIDI, so this needs a computer or a USB-MIDI host box |
| Performance mode: remap buttons and knobs, faster toggling | `Task_UpdateUI`, button/knob handlers | high | |
| Better screen feedback (levels, LFO/tempo, what an effect is doing) | `Semaphore_LCDUpdate`, display driver | medium | needs the drawing routines mapped |
| More controls | knob pages, button combos, MIDI CC | medium | physical controls are fixed; more control comes from pages, combos and MIDI |
| Lift per-effect DSP limits | effect loader / DSP budget table | medium | the OS budget can be relaxed; the real CPU ceiling stays, so it needs measuring |
| Routing: parallel pairs, sub-chains, dry mixed back at the end | audio chain loop | medium-hard | core audio path; highest audio-glitch risk |
| Effects that talk to each other (modulation bus) | audio chain + custom effects | hard | builds on routing and custom ZDLs |
| Better looping | new audio buffer + UI | hard | depends on free RAM, not yet measured |
| MS-70CDR stereo mixer / independent L-R chains | audio chain, stereo I/O | hard | cannot be tested on an MS-60B |

## Order

1. Flash test with `hello` (proves build, flash, boot and recovery).
2. Map the MIDI task, button/knob handlers, patch loading and the audio chain
   loop in the MS-50G 3.10 build, with addresses for all three builds.
3. MIDI program change and CC, then MIDI clock.
4. Performance mode.
5. Screen feedback.
6. Routing, then effect intercommunication and looping.
