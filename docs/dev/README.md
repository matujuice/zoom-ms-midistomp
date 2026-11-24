# Developer docs

Plans, research and mockups behind MIDISTOMP. User docs are one level up: [user guide](../user-guide.md),
[flashing](../flashing.md), [safety](../safety.md).

## Start here
- [HANDOFF.md](HANDOFF.md): where the work stands now
- [v2.0-brief.md](v2.0-brief.md): the v2.0 design
- [roadmap.md](roadmap.md): the feature list, scoped
- [workflow.md](workflow.md): release trains and how work is organized

## Platform
- [ms70cdr-addresses.md](ms70cdr-addresses.md): MS-70CDR 2.10 address map
- [os-reverse-engineering.md](os-reverse-engineering.md): main OS and bootloader notes
- [formats.md](formats.md): updater and ZDL formats
- [flash-protocol.md](flash-protocol.md): the updater's USB MIDI flash protocol
- [record-50-51-layout.md](record-50-51-layout.md): records 50 and 51 (MIXER, PERFORM, MIDI settings)
- [transport-block.md](transport-block.md): the MIDI transport block effects read
- [feature-dependencies.md](feature-dependencies.md): which release patches need which
- [effect-compression.md](effect-compression.md): freeing flash for more effects
- [zoom-effect-manager.md](zoom-effect-manager.md): what Zoom Effect Manager 2 means for us

## Features
- Mixer: [plan](mixer-mode-plan.md), [M0](mixer-mode-m0.md), [M3 research](mixer-mode-m3-research.md), [screens](mixer-ui-mockup.html)
- Perform: [plan](perform-mode-plan.md), [P0 scope](perform-mode-p0.md), [P0 research](perform-mode-p0-research.md), [screens](perform-ui-mockup.html)
- Looper: [plan](looper-plan.md), [services block](looper-services.md)
- Master: [screens](master-ui-mockup.html)
- Diagnostics: [SYSTEM screen](diagnostics-plan.md)
- Overclock: [plan](overclock-plan.md) (shipped in v2.0.4)

## Open topics
- [patch-manager-plan.md](patch-manager-plan.md): patch manager and file format (the editor, on hold)
- [fonts-from-os-plan.md](fonts-from-os-plan.md): read the fonts from the OS at run time
- [future-effect-ids-and-categories.md](future-effect-ids-and-categories.md): effect IDs and the category screen
- [modwerk-research.md](modwerk-research.md): Modwerk's questions, the hello SysEx
- [repo-refresh-plan.md](repo-refresh-plan.md): the v2.0 README, guide and docs refresh (done but its Open list: effects cover, demo video)

## Done (kept for history)
- [ms70cdr-base.md](ms70cdr-base.md) and [ms70cdr-port.md](ms70cdr-port.md): the move to the MS-70CDR OS
- [joint-plan-v2.0.md](joint-plan-v2.0.md): the v2.0 firmware + effects pack plan
- [v2.0.1-bugs.md](v2.0.1-bugs.md): the v2.0.1 bug list
- [github-page.md](github-page.md): the GitHub About text set at v2.0
