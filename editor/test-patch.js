// Self-check for patch.js: node editor/test-patch.js
// Round trip, byte 17 round trip, and ids, on/off and name against g200kg's bit table.
var assert = require('assert');
var P = require('./patch.js');

function rnd(n) { var a = []; for (var i = 0; i < n; i++) a.push(Math.random() * 256 | 0); return a; }

for (var t = 0; t < 200; t++) {
  var rec = rnd(122);
  for (var i = 0; i < 6; i++) rec[18 * i + 17] &= 0x7f;
  var dump = P.toDump(rec, 0x61);
  assert.strictEqual(dump.length, 146);
  assert.ok(dump.slice(1, -1).every(function (b) { return b < 0x80; }));
  assert.deepStrictEqual(P.fromDump(dump), rec);

  var r = { bus: [0, 1, 2, 1, 0, 2], inR: t % 151, masterR: (t * 7) % 151, out: t % 3, muteA: t & 1, muteB: t >> 1 & 1, solo: t % 3 };
  P.setRouting(rec, r);
  var back = P.routing(rec);
  ['inR', 'masterR', 'out', 'muteA', 'muteB', 'solo'].forEach(function (k) { assert.strictEqual(back[k], r[k], k); });
  assert.deepStrictEqual(back.bus, r.bus);
  for (i = 0; i < 6; i++) assert.strictEqual(rec[18 * i + 17] & 0x80, 0);
  assert.strictEqual(rec[18 * 5 + 17] & 0x40, 0x40);
}
// reorder: effects move with their bytes, routing settings stay
rec = rnd(122);
for (i = 0; i < 6; i++) rec[18 * i + 17] &= 0x7f;
P.setRouting(rec, { bus: [0, 0, 0, 0, 0, 0], inR: 77, masterR: 120, out: 2, muteA: 1, muteB: 0, solo: 1 });
var before = rec.slice();
P.reorder(rec, [5, 0, 1, 2, 3, 4], [3, 0, 1, 1, 2, 3]);
assert.deepStrictEqual(rec.slice(0, 17), before.slice(90, 107));
assert.deepStrictEqual(rec.slice(18, 35), before.slice(0, 17));
var rr = P.routing(rec);
assert.deepStrictEqual([rr.bus, rr.inR, rr.masterR, rr.out, rr.muteA, rr.solo], [[3, 0, 1, 1, 2, 3], 77, 120, 2, 1, 1]);
assert.deepStrictEqual(rec.slice(108), before.slice(108));

var z = P.routing(new Array(122).fill(0));       // stock patch: unity, stereo, no mutes
assert.deepStrictEqual([z.inR, z.masterR, z.out, z.muteA, z.solo, z.used], [100, 100, 0, 0, 0, false]);

// g200kg/zoom-ms-utility js/apatch.js (MIT): [dump index, mask, shift] for on/off and id of each slot,
// and the name's dump indexes. Our 7-in-8 decode must agree with this independent table.
var G_STATE = [6, 26, 47, 67, 88, 108];
var G_ID = [
  [[5, 0x40, 24], [6, 0x7e, 16], [7, 0x07, 8], [9, 0x1f, 0]],
  [[21, 0x4, 28], [26, 0x7e, 16], [27, 0x07, 8], [30, 0x1f, 0]],
  [[45, 0x20, 25], [47, 0x7e, 16], [48, 0x07, 8], [50, 0x1f, 0]],
  [[61, 0x2, 29], [67, 0x7e, 16], [68, 0x07, 8], [71, 0x1f, 0]],
  [[85, 0x10, 26], [88, 0x7e, 16], [89, 0x07, 8], [91, 0x1f, 0]],
  [[101, 0x1, 30], [108, 0x7e, 16], [110, 0x07, 8], [112, 0x1f, 0]],
];
// parameters 1-9 of slots 0 and 5 (the "NZ" flag entry left out)
var G_P0 = [
  [[9, 0x60, -5], [5, 0x8, -1], [10, 0x7f, 3], [5, 0x4, 8], [11, 0x1, 11]],
  [[11, 0x7c, -2], [5, 0x2, 4], [12, 0x1f, 6]],
  [[5, 0x1, 0], [14, 0x7f, 1], [13, 0x40, 2], [15, 0x3, 9]],
  [[15, 0x70, -4], [13, 0x20, -2], [16, 0x0f, 4]],
  [[16, 0x70, -4], [13, 0x10, -1], [17, 0x0f, 4]],
  [[17, 0x70, -4], [13, 0x08, 0], [18, 0x0f, 4]],
  [[18, 0x70, -4], [13, 0x04, 1], [19, 0x0f, 4]],
  [[19, 0x70, -4], [13, 0x02, 2], [20, 0x1f, 4]],
  [[24, 0x7f, 0], [21, 0x10, 3]],
];
var G_P5 = [
  [[112, 0x60, -5], [109, 0x10, -2], [113, 0x7f, 3], [109, 0x8, 7], [114, 0x1, 11]],
  [[114, 0x7c, -2], [109, 0x4, 3], [115, 0x1f, 6]],
  [[109, 0x2, -1], [116, 0x7f, 1], [109, 0x1, 8], [118, 0x3, 9]],
  [[118, 0x70, -4], [117, 0x40, -3], [119, 0x0f, 4]],
  [[119, 0x70, -4], [117, 0x20, -2], [120, 0x0f, 4]],
  [[120, 0x70, -4], [117, 0x10, -1], [121, 0x0f, 4]],
  [[121, 0x70, -4], [117, 0x8, 0], [122, 0x0f, 4]],
  [[122, 0x70, -4], [117, 0x4, 1], [123, 0x1f, 4]],
  [[127, 0x7f, 0], [125, 0x20, 2]],
];
var G_NAME = [132, 134, 135, 136, 137, 138, 139, 140, 142, 143];
function gbits(msg, bits) {
  return bits.reduce(function (v, b) { var x = msg[b[0]] & b[1]; return v | (b[2] >= 0 ? x << b[2] : x >> -b[2]); }, 0) >>> 0;
}
for (t = 0; t < 200; t++) {
  var msg = [0xf0, 0x52, 0x00, 0x61, 0x28].concat(rnd(140).map(function (b) { return b & 0x7f; }), [0xf7]);
  rec = P.fromDump(msg);
  for (i = 0; i < 6; i++) {
    assert.strictEqual(P.effectKey(rec, i), gbits(msg, G_ID[i]), 'id slot ' + i);
    assert.strictEqual(P.on(rec, i), msg[G_STATE[i]] & 1, 'on slot ' + i);
  }
  G_NAME.forEach(function (m, k) { assert.strictEqual(rec[111 + k] & 0x7f, msg[m], 'name ' + k); });
  [[0, G_P0], [5, G_P5]].forEach(function (s) {
    s[1].forEach(function (bits, p) { assert.strictEqual(P.param(rec, s[0], p), gbits(msg, bits), 'slot ' + s[0] + ' param ' + (p + 1)); });
  });
}
// setParam writes only its own bits (and bit 126 for parameter 8)
for (t = 0; t < 50; t++) {
  rec = rnd(122);
  var s = t % 6, p = t % 9, v = Math.random() * 256 | 0, was = rec.slice();
  P.setParam(rec, s, p, v);
  assert.strictEqual(P.param(rec, s, p), v);
  for (i = 0; i < 9; i++) if (i !== p) assert.strictEqual(P.param(rec, s, i), P.param(was, s, i));
  assert.deepStrictEqual(rec.slice(0, 18 * s), was.slice(0, 18 * s));
  assert.deepStrictEqual(rec.slice(18 * s + 17), was.slice(18 * s + 17));
}
// MIXER: the hash as pages.c r50_hash (value from a separate Python FNV-1a), the 02 reply, and mix_get's choice
rec = []; for (i = 0; i < 122; i++) rec.push(i * 7 & 255);
assert.strictEqual(P.hash(rec), 0xba8022cd);
var ent = [0xcd, 0x22, 0x80, 0xba, 1, 50, 140, 100, 100, 50, 100, 2, 100, 150, 1, 0];
var reply = [0xf0, 0x7d, 0x4d, 0x53, 0x54, 0x43, 7, 7].concat(P.pack7(ent), [0xf7]);
assert.strictEqual(reply.length, 28);
var e = P.mixerEntry(reply);
assert.deepStrictEqual([e.hash, e.set], [0xba8022cd, ent.slice(4, 15)]);
var other = { hash: 1, set: ent.slice(4, 15) }, defs = P.MIXER.map(function (m) { return m[2]; });
assert.deepStrictEqual(P.mixer(rec, 3, [other, other, other, e]), { set: e.set, from: 3 });        // its own entry
assert.deepStrictEqual(P.mixer(rec, 0, [other, e]).from, 1);                                       // a copy's
assert.deepStrictEqual(P.mixer(rec, 0, [other, other]), { set: defs, from: -1 });                 // none: defaults
var bad = { hash: e.hash, set: [9].concat(e.set.slice(1)) };                                        // Mode 9 > max 3
assert.strictEqual(P.mixer(rec, 0, [bad]).set[0], 0);
console.log('patch.js OK');
