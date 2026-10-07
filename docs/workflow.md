# Workflow: release trains

One pedal, one tester, one build at a time. Work moves in cycles instead of
many threads changing the firmware in parallel.

## 1. Backlog

Every feature, idea and bug is a GitHub Issue. New ideas from chat are filed
as issues, not started straight away.

Labels:

| Label | Meaning |
|---|---|
| `feature` | new capability |
| `bug` | something broken, usually found in a flash test |
| `research` | read-only reverse engineering; output goes to `docs/`, never firmware code |
| `area:core`, `area:midi`, `area:ui`, `area:dsp`, `area:routing`, `area:looping`, `area:ms70cdr` | part of the OS it touches |
| `cycle:vX.Y` | the cycle the issue is batched into |

The cycle label is the batch. A GitHub milestone with the same name can be
added on top if wanted; the label is what threads read.

## 2. Cycle

Luca picks a batch of issues and labels them `cycle:vX.Y`. One build thread
implements the whole batch on one branch (`cycle/vX.Y`), then produces one
test firmware (updater .exe) for the MS-60B, built for all three models.

Only the build thread changes firmware code. Research threads run alongside,
read-only, and write their findings to `docs/os-reverse-engineering.md`.

## 3. Test and fix

Luca flashes the test firmware and reports problems in the build thread or
with the **Flash test bug** issue template. The thread fixes and rebuilds
until Luca is happy. Recovery is always the boot-time updater mode
(see `docs/flashing.md` and `docs/safety.md`).

## 4. Ship or continue

The branch is merged into `main` through a PR. Then either:

- tag a release `vX.Y` and attach the updaters to a GitHub release, or
- start the next cycle from `main`.

The cycle's issues are closed by the merge and the thread is resolved.

## Keeping it cheap

Knowledge lives in `docs/` and project memory, not in chat history. Each
cycle starts in a fresh thread that reads these docs, so threads stay short.
