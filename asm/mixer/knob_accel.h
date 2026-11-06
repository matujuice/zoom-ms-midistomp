/* SETTINGS > KNOB ACCEL (global, saved once for the pedal): speed-sensitive knob turns on our value
 * screens, Perform play (perform_keys.c turn) and the node knob pages (pages.c). Never on lists.
 * Effect parameters need nothing: the stock step (0xC00ABE58) already speeds up fast turns.
 * Callers: pages.c pages_key and perform_keys.c turn(), each with its own state. */
#ifndef KNOB_ACCEL_H
#define KNOB_ACCEL_H

#define KNOB_ACCEL() 0          /* wired to the SETTINGS bit at merge */

/* knob_accel: a turn of `steps` detents at `now` ms -> the steps to apply. 1 step per detent while slow, more as
 * the knob turns faster, up to KA_MAX quarter steps (8 steps) per detent. Speed: detents x 32, minus
 * 1/8 every 16 ms (about the last 130 ms). Fractions carry over; turning back starts slow again.
 * st[4] (zeroed at boot): [0] quarter steps not applied yet, [1] speed, [2] when [1] last decayed,
 * [3] last direction. */
int knob_accel(int *st, int steps, int now);   /* pages.c; -ms0 callers, so two call sites are fine */
#endif
