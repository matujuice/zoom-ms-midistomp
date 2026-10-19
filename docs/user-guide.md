<p align="center"><img src="img/banner.png" alt="MIDISTOMP MOD v1.2" width="720"></p>

<h1 align="center">MIDISTOMP V1.2 user guide</h1>

<p align="center"><b>MIDI control, MIDI clock and playing aids for the Zoom MultiStomp</b></p>

<p align="center">
<a href="#2-getting-it-onto-the-pedal">Install</a> ·
<a href="#3-recovery-and-going-back-to-stock">Recovery</a> ·
<a href="#4-features">Features</a> ·
<a href="#5-midi-cc-chart">MIDI chart</a> ·
<a href="#7-known-limits-and-faq">FAQ</a> ·
<a href="#8-custom-effects">Custom effects</a> ·
<a href="#9-feedback-and-bug-reports">Feedback</a> ·
<a href="../README.md#demo">Demo</a>
</p>

<sub>Screen pictures are drawn with the pedal's own font from the firmware; the photos are of a real MS-60B.</sub>

## 1. What MIDISTOMP is

MIDISTOMP is a modified version of Zoom's own MS-70CDR firmware 2.10. It keeps
everything the pedal does today and adds MIDI control, MIDI clock and a few
playing aids. It is not made or supported by Zoom.

One build runs on all three pedals:

| Pedal | Status |
|---|---|
| MS-70CDR | Runs it, with real **stereo input**. Tested. |
| MS-60B | Runs it. Tested. It behaves like an MS-70CDR with only the L input, so the input is mono. |
| MS-50G | Same as the MS-60B: runs it, mono input. Tested with the Mac updater. |
| "+" models (MS-50G+, MS-70CDR+) | No: different hardware. |

You get 6 effects per patch.

If you try it on an MS-50G or MS-70CDR, please [report how it went](https://github.com/matujuice/zoom-ms-modding/issues):
every report helps.

### What's new in v1.2

- Built on Zoom's MS-70CDR 2.10 firmware for every pedal: one builder and one
  Zoom updater for the MS-50G, MS-60B and MS-70CDR.
- The MS-70CDR gets real stereo input (on the MS-50G and MS-60B the input stays
  mono, as before).
- Your installed effects and patches are kept.
- The updater works whatever the pedal runs now: stock MS-50G, MS-60B or
  MS-70CDR firmware, or an older MIDISTOMP.
- The features are the same as v1.1: MIDI CC (including CC 80/81 patch
  up/down), MIDI clock and Start/Stop, MIDI menu, tempo screen, HOLD FOR,
  button combos, faster scrolling, boot logo.
- Works on a Mac too, see [On a Mac](#on-a-mac).
- The looper is not in v1.2.

## 2. Getting it onto the pedal

The release does not contain Zoom's firmware, so you make the MIDISTOMP
updater yourself from Zoom's official one. This needs Windows, or a Mac
(see [On a Mac](#on-a-mac) below).

1. Download [Zoom's **MS-70CDR v2.10** updater for Windows](https://zoomcorp.com/it/it/multi-effects/multistomp-pedals/ms-70cdr/ms-70cdr-support/) from zoomcorp.com
   (MS-70CDR support page, file like `MS-70CDR_v2.10_Win_E.zip`) and unzip it.
   Use this one for the MS-50G and MS-60B too.
2. Download **MIDISTOMP-builder.exe** from the
   [release page](https://github.com/matujuice/zoom-ms-modding/releases).
3. Drag `ZOOM MS-70CDR v2.10 Updater.exe` onto `MIDISTOMP-builder.exe`.
   It writes **MIDISTOMP V1.2 Updater.exe** in the same folder. It refuses any
   other file, so a wrong download can't produce a broken updater.
4. Windows may warn that the program is unknown (it is not signed). Choose
   "More info", then "Run anyway".
5. Pedal off. Hold the **up and down cursor keys** (above and below the
   footswitch, see the photo below) while you plug in the USB cable: the pedal shows the update screen.

   <img src="img/keys.jpg" alt="The four cursor keys around the footswitch" width="480">

7. Run `MIDISTOMP V1.2 Updater.exe` and let it finish. Don't unplug during the update.
8. Unplug and power on normally. The boot screen reads **MIDISTOMP MOD v1.2** and
   the last menu entry reads **V1.2**.

   <img src="img/boot-screen.png" alt="MIDISTOMP MOD v1.2 boot screen" width="400">

Your patches and installed effects stay as they are. The updater never
rewrites the pedal's effects area or its bootloader, which keeps the update mode always available.

### On a Mac

Zoom's Mac updater holds the same firmware files as the Windows one and runs
the same flash steps, so a MIDISTOMP version of it can be built too. The
build has been checked byte for byte against the Windows MIDISTOMP updater
and flashed to an MS-50G from an Apple Silicon Mac.

1. Download Zoom's **MS-70CDR v2.10** updater **for Mac** from the
   [MS-70CDR support page](https://zoomcorp.com/en/us/multi-effects/multistomp-pedals/ms-70cdr/ms-70cdr-support/)
   (file like `MS-70CDR_v2.10_Mac_E.zip`) and unzip it. Use this one for the
   MS-50G and MS-60B too.
2. Get this repository (`git clone`, or Code > Download ZIP on GitHub) and
   Python 3.10 or newer (from python.org or Homebrew; the `python3` that comes
   with macOS is too old). Then in the repository's folder:
   ```sh
   python3 -m venv .venv && .venv/bin/pip install -e .
   .venv/bin/python scripts/midistomp_builder.py "/path/to/ZOOM MS-70CDR v2.10 Updater.app"
   ```
   It writes **MIDISTOMP V1.2 Updater.app** next to Zoom's app, and refuses
   anything that is not Zoom's original.
3. Changing the app breaks Zoom's code signature, so sign it for your own Mac:
   ```sh
   xattr -cr "/path/to/MIDISTOMP V1.2 Updater.app"
   codesign --force --deep --sign - "/path/to/MIDISTOMP V1.2 Updater.app"
   ```
4. Put the pedal in update mode (step 5 above) and open the app. It is an
   Intel app, so Apple Silicon Macs run it through Rosetta (macOS offers to
   install it). Its window reads **MIDISTOMP V1.2 Updater**; click Execute.

After v1.2 the pedal reports itself as an MS-70CDR over USB, whichever pedal
it is. Zoom's MS-50G Mac updater only accepts model 0x58, so it will refuse
the pedal ("Illegal device connected"). On a Mac, recover with Zoom's
MS-70CDR Mac updater (checked: it accepts an MS-50G after v1.2) or the
MIDISTOMP one.

## 3. Recovery and going back to stock

If the pedal doesn't boot, or you want stock firmware back:

1. Enter update mode (step 5 above: hold up + down while plugging in USB).
   This works even when the firmware is broken.
2. Run Zoom's original updater for your pedal (the MS-70CDR 2.10 one, or the MS-50G 3.10 / MS-60B one you had before). It puts back the stock firmware and
   the stock boot screen. On a Mac, after v1.2, use the MS-70CDR one: Zoom's
   MS-50G updater won't accept the pedal (see [On a Mac](#on-a-mac)).

On an MS-60B you can also run Zoom's MS-60B updater to go back to the bass
firmware (4 effects per patch).

## 4. Features

All MIDI goes over the USB cable: from a computer, an iPad/iPhone, or a
USB-MIDI host box for hardware like a drum machine.

<p><img src="img/menu.png" alt="Menu with the MIDI entry" width="300"> <img src="img/midi-menu.png" alt="MIDI menu" width="300"></p>

**MIDI menu.** The menu (press the left knob in the effect chain view) has a
new **MIDI** entry:

| Row | Choices | Default |
|---|---|---|
| CLOCK RECEIVE | ON / OFF | ON |
| TRANSPORT RECEIVE (Start/Stop) | ON / OFF | ON |
| PROG CH RECEIVE | ON / OFF | ON |
| PROG CH START NO. | 0 / 1 | 1 |
| CC RECEIVE | ON / OFF | ON |
| MIDI CHANNEL | OMNI, 1-16 | OMNI |

Settings are kept after power-off. Clock, Start and Stop have no channel and
are never filtered by MIDI CHANNEL.

**Program Change** loads a patch: with START NO. 1, PC 1 = patch 1 ... PC 50 =
patch 50. With START NO. 0, PC 0 = patch 1.

**Control Change** turns effects on and off and moves knobs (chart in section 5).
The screen follows.

**MIDI clock** sets the patch tempo, like tap tempo does, so tempo-synced
delays and modulations follow your DAW or drum machine (40-250 BPM). The tempo
locks after about 2 beats and follows changes. Some stock effects (for example
Delay) restart their echoes on every tempo change, as they do with tap tempo;
TapeEcho changes smoothly.

**Start / Stop** reset and stop the beat count used by custom effects from
[zoom-ms-zdl-effects-pack](https://github.com/matujuice/zoom-ms-zdl-effects-pack),
so they stay on the beat and restart on the downbeat.

<img src="img/settings.png" alt="SETTINGS with TEMPO LOCK" width="300">

**TEMPO LOCK** (last row of SETTINGS, default OFF): changing patch keeps the
current tempo. Tap tempo, the tempo screen and MIDI clock still change it.

<p><img src="img/tempo-turn-tap.png" alt="Tempo screen: TURN OR TAP" width="300"> <img src="img/tempo-midi-clock.png" alt="Tempo screen while MIDI clock arrives" width="300"></p>

**Tempo screen.** Press the knob labelled **TEMPO**: the screen shows the BPM
and **TURN OR TAP**. Turn the knob for 1 BPM steps or tap the footswitch; it
closes 2 s after the last turn or tap. While MIDI clock arrives it reads
**MIDI CLOCK** and can't be changed by hand.

<img src="img/hold-for.png" alt="HOLD FOR choices" width="300">

**HOLD FOR** (SETTINGS): what holding the footswitch does.
- TUNER (default): opens the tuner, as stock.
- TEMPO: opens the tempo screen.
- MOMENTARY: a short press flips the effect as usual; hold it over half a
  second and it flips back when you let go. The flip-back is never saved.

**Button combos** (effect chain or effect screen):
- hold **down + right** about 1 s: tuner
- hold **down + left** about 1 s: tempo screen

The pedal already marks them: the note icon sits under down + left, the
tuning fork under down + right (photo in section 2).

In the tuner, pressing the middle knob (**EXIT**) goes back to the effects.

**Faster scrolling** (from v1.1): left and right move between the effects of
a patch several times faster than stock. At the last effect, one more
press slides quickly back across the chain to the first one, and the other
way round. Like stock, the move happens when you let go of the key.

## 5. MIDI CC chart

Any channel unless MIDI CHANNEL is set. Effect n is the n-th effect of the patch.

| | Effect 1 | Effect 2 | Effect 3 | Effect 4 | Effect 5 | Effect 6 |
|---|---|---|---|---|---|---|
| On/off (0-63 off, 64-127 on) | 14 | 24 | 34 | 44 | 54 | 64 |
| Knob 1 | 15 | 25 | 35 | 45 | 55 | 65 |
| Knob 2 | 16 | 26 | 36 | 46 | 56 | 66 |
| Knob 3 | 17 | 27 | 37 | 47 | 57 | 67 |
| Knob 4 | 18 | 28 | 38 | 48 | 58 | 68 |
| Knob 5 | 19 | 29 | 39 | 49 | 59 | 69 |
| Knob 6 | 20 | 30 | 40 | 50 | 60 | 70 |
| Knob 7 | 21 | 31 | 41 | 51 | 61 | 71 |
| Knob 8 | 22 | 32 | 42 | 52 | 62 | 72 |
| Knob 9 | 23 | 33 | 43 | 53 | 63 | 73 |

Knob values 0-127 cover the knob's whole range. A knob the effect doesn't
have, and any other CC, does nothing.

**Patch up/down** (from v1.1): CC 80 with a value of 64-127 loads the
previous patch, CC 81 the next one, wrapping between patch 50 and patch 1.
Values 0-63 do nothing, so a button that sends 127 when pressed and 0 when
released steps once. They follow CC RECEIVE and MIDI CHANNEL, not the PROG CH
settings.

## 6. Effect Manager

Zoom's Effect Manager and Zoom Effect Manager 2 work in **normal mode**
(adding, removing and ordering effects); MIDISTOMP stays installed.

**Never use an Effect Manager's firmware update mode** on a MIDISTOMP pedal:
it can rewrite the firmware and remove MIDISTOMP (inferred, not tested).

## 7. Known limits and FAQ

- **MIDI only over USB.** The pedal has no MIDI DIN jacks; hardware needs a
  USB-MIDI host box.
- **Clock through an app.** Apps that regenerate the clock (for example Loopy
  Pro) can add lag; pass the clock through unchanged if you can.
- **Some delays cut out on tempo changes.** That is the effect itself (see
  MIDI clock above).
- **Going back to an older MIDISTOMP or stock** may start the pedal on patch 1
  once.
- *Is my pedal at risk?* The bootloader is never rewritten, so update mode is
  always there to recover, as in section 3.
- *Why do I need Zoom's updater?* Zoom's firmware can't be shared here; the
  builder only changes your own copy.
- *Found a bug or something unclear in this guide?* Please
  [open an issue](https://github.com/matujuice/zoom-ms-modding/issues), see section 9.

## 8. Custom effects

Stock effects work with MIDISTOMP (clock sets their tempo, CC moves their
knobs), but they have limits: they ignore Start/Stop, some delays cut out on
tempo changes, and nothing locks to the bar.

The free effects in [zoom-ms-zdl-effects-pack](https://github.com/matujuice/zoom-ms-zdl-effects-pack) are built around
MIDISTOMP: they follow the pedal's tempo, lock to the clock's grid, restart on
the downbeat with MIDI Start and keep going after Stop. They are the best way
to use this firmware, and the pack is updated often with new effects. Install
them with Effect Manager in normal mode (section 6).

## 9. Feedback and bug reports

Please [open an issue](https://github.com/matujuice/zoom-ms-modding/issues) for anything that doesn't work, anything
confusing, or an idea. Say which pedal and MIDISTOMP version you have, what
you did and what happened; a phone photo of the screen helps. Reports from
MS-50G and MS-70CDR owners are especially welcome.
