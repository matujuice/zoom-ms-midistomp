// Zoom MS patch dumps (MS-50G, MS-70CDR: 146-byte SysEx) <-> the 122-byte packed patch,
// and MIDISTOMP's byte 17 (docs/dev/modwerk-research.md section 2, asm/mixer/pages.c mix_get/mix_put).
// Plain script: works in the page and in node (editor/test-patch.js).

var Patch = (function () {
  var DUMP_LEN = 146, HEAD = 5;                 // F0 52 00 dd 28, then 140 data bytes, F7

  // 7 bytes per group, led by their high bits (first byte's = 0x40), as Modwerk's unpack7.
  function unpack7(d) {
    var out = [];
    for (var i = 0; i < d.length; i += 8)
      for (var j = 1; j < 8 && i + j < d.length; j++) out.push(d[i + j] | (d[i] & (1 << (7 - j)) ? 0x80 : 0));
    return out;
  }
  function pack7(b) {
    var out = [];
    for (var i = 0; i < b.length; i += 7) {
      var g = b.slice(i, i + 7), high = 0;
      g.forEach(function (x, j) { if (x & 0x80) high |= 1 << (6 - j); });
      out.push(high);
      g.forEach(function (x) { out.push(x & 0x7f); });
    }
    return out;
  }

  function fromDump(msg) {
    if (msg.length !== DUMP_LEN || msg[0] !== 0xf0 || msg[1] !== 0x52 || msg[4] !== 0x28) return null;
    return unpack7(msg.slice(HEAD, DUMP_LEN - 1));      // 122 bytes
  }
  function toDump(rec, deviceId) {
    return [0xf0, 0x52, 0x00, deviceId, 0x28].concat(pack7(rec), [0xf7]);
  }

  // g200kg's id form, the key of EFFECT_NAMES
  function effectKey(rec, i) {
    var b = rec.slice(18 * i, 18 * i + 4);
    return (((b[0] & 0x80) << 23) | ((b[0] & 0x7e) << 16) | ((b[1] & 7) << 8) | (b[3] & 0x1f)) >>> 0;
  }
  // the effect id as the pedal hashes it: bits 1-28 of the block
  function effectId(rec, i) {
    var k = 18 * i;
    return ((rec[k] | rec[k + 1] << 8 | rec[k + 2] << 16 | rec[k + 3] << 24) >>> 1) & 0x0fffffff;
  }

  function name(rec) { return String.fromCharCode.apply(null, rec.slice(111, 121)).replace(/[\0 ]+$/, ''); }
  function setName(rec, s) {
    s = (s || '').replace(/[^\x20-\x7e]/g, ' ').slice(0, 10);
    for (var i = 0; i < 10; i++) rec[111 + i] = i < s.length ? s.charCodeAt(i) : 0x20;
  }

  // MIDISTOMP byte 17: bits 0-1 the slot's bus, bits 2-6 a 5-bit chunk of a 22-bit word
  var BUS = ['PRE', 'A', 'B', 'POST'], OUT = ['Ster', 'Mono', 'Split'], SOLO = ['Off', 'A', 'B'];
  function routing(rec) {
    var w = 0, bus = [], used = false;
    for (var i = 0; i < 6; i++) {
      var b = rec[18 * i + 17];
      if (b) used = true;
      bus.push(b & 3);
      w |= (b >> 2 & 31) << 5 * i;
    }
    return {
      used: used, bus: bus,
      inR: (w & 255) ^ 100, masterR: (w >> 8 & 255) ^ 100,
      out: w >> 16 & 3, muteA: w >> 18 & 1, muteB: w >> 19 & 1, solo: w >> 20 & 3,
    };
  }
  function setRouting(rec, r) {
    var w = ((r.inR ^ 100) & 255) | ((r.masterR ^ 100) & 255) << 8 | (r.out & 3) << 16
          | (r.muteA & 1) << 18 | (r.muteB & 1) << 19 | (r.solo & 3) << 20;
    for (var i = 0; i < 6; i++) rec[18 * i + 17] = (r.bus[i] & 3) | (w >> 5 * i & 31) << 2;
    rec[18 * 5 + 17] |= 0x40;          // layout marker; bit 7 stays 0
  }

  // Moves effects: order[k] = the old slot that goes to slot k, bus[k] = its new bus.
  // Bytes 0-16 are the effect's; byte 17 is rebuilt, since its bits 2-6 belong to the position.
  function reorder(rec, order, bus) {
    var r = routing(rec), old = rec.slice();
    order.forEach(function (from, k) { for (var j = 0; j < 17; j++) rec[18 * k + j] = old[18 * from + j]; });
    r.bus = bus;
    setRouting(rec, r);
  }

  // Effect parameters 1-9: [first bit, width] in the slot's 144-bit block (g200kg's apatch.js table, same for every slot).
  // Bit 126 is set while parameter 8 is not 0.
  var PARAM_BITS = [[29, 12], [42, 11], [55, 11], [68, 8], [76, 8], [84, 8], [92, 8], [100, 9], [128, 8]];
  function param(rec, i, p) {
    var a = PARAM_BITS[p], v = 0;
    for (var b = 0; b < a[1]; b++) { var x = 144 * i + a[0] + b; v |= (rec[x >> 3] >> (x & 7) & 1) << b; }
    return v;
  }
  function setBit(rec, x, on) { if (on) rec[x >> 3] |= 1 << (x & 7); else rec[x >> 3] &= ~(1 << (x & 7)); }
  function setParam(rec, i, p, v) {
    var a = PARAM_BITS[p];
    for (var b = 0; b < a[1]; b++) setBit(rec, 144 * i + a[0] + b, v >> b & 1);
    if (p === 7) setBit(rec, 144 * i + 126, v !== 0);
  }
  function setOn(rec, i, on) { setBit(rec, 144 * i, on); }

  // MIXER settings 0-10 live in record 50 (one entry per patch: hash, settings), read with the MIDISTOMP
  // SysEx 02 (docs/dev/modwerk-research.md section 1). Names, maxes, defaults: asm/mixer/pages.c, mixer.S.
  var MIXER = [['Mode', 3, 0, ['Serial', 'Parallel', 'Split', 'Mono Serial']], ['Route XFade', 100, 50], ['Input', 150, 100],
    ['Route A', 150, 100], ['Route B', 150, 100], ['Mix XFade', 100, 50], ['Master', 150, 100],
    ['Curve', 2, 1, ['Smooth', 'DJ', 'Cut']], ['Mix A', 150, 100], ['Mix B', 150, 100], ['Phase B', 1, 0, ['Normal', 'Invert']]];
  function fnv(h, c) { return Math.imul(h ^ c, 16777619) >>> 0; }
  function hash(rec) {                       // pages.c r50_hash: the six effect ids and the name
    var h = 2166136261;
    for (var i = 0; i < 6; i++) { var k = 18 * i; [rec[k] & 0xfe, rec[k + 1], rec[k + 2], rec[k + 3] & 0x1f].forEach(function (c) { h = fnv(h, c); }); }
    for (var j = 111; j < 122; j++) h = fnv(h, rec[j]);
    return h;
  }
  // F0 7D "MST" 43 nonce n <19 packed> F7 -> { hash, set: [11] }
  function mixerEntry(msg) {
    var e = unpack7(msg.slice(8, -1));
    return { hash: (e[0] | e[1] << 8 | e[2] << 16 | e[3] << 24) >>> 0, set: e.slice(4, 15) };
  }
  // As pages.c mix_get: entry n if its hash is this patch's, else the first entry with that hash (a copy), else defaults.
  // ponytail: skips mix_get's middle case (settings in bytes 14-15, saved by the M3b5 / M3b6 test builds only).
  function mixer(rec, n, entries) {
    var h = hash(rec), from = entries[n] && entries[n].hash === h ? n : entries.findIndex(function (e) { return e && e.hash === h; });
    var set = MIXER.map(function (m, i) { var v = from >= 0 ? entries[from].set[i] : m[2]; return v > m[1] ? m[2] : v; });
    return { set: set, from: from };          // from: the entry used, -1 = defaults
  }

  // F0 7D "MST" 03 nonce n <pack7(hash LE, settings 0-10)> F7: the pedal answers 44 nonce n status (0 = saved)
  function mixerWrite(n, h, set, nonce) {
    return [0xf0, 0x7d, 0x4d, 0x53, 0x54, 0x03, nonce, n].concat(pack7([h & 255, h >>> 8 & 255, h >>> 16 & 255, h >>> 24].concat(set)), [0xf7]);
  }

  // PERFORM: 208 bytes per patch after the mixer table (asm/perform/perform_store.c), read and written
  // 14 bytes at a time: 04 nonce n k -> 45 nonce n k ok <pack7 14>; 05 nonce n k <pack7 14> -> 46 nonce n k status.
  var PERF_LEN = 208, PERF_OK = 0xa5;          // byte 15 is PERF_OK once STORE wrote the entry
  function performRead(n, k, nonce) { return [0xf0, 0x7d, 0x4d, 0x53, 0x54, 0x04, nonce, n, k, 0xf7]; }
  function performWrite(n, k, e, nonce) {
    var c = e.slice(14 * k, 14 * k + 14);
    while (c.length < 14) c.push(0);
    return [0xf0, 0x7d, 0x4d, 0x53, 0x54, 0x05, nonce, n, k].concat(pack7(c), [0xf7]);
  }
  function performChunk(msg) { return unpack7(msg.slice(10, -1)); }
  // As perform_store.c find: entry n if its mixer entry has this patch's hash, else a copy's; null = none (empty PERFORM)
  function perform(rec, n, entries, perfs) {
    var h = hash(rec), ok = function (i) { return entries[i] && entries[i].hash === h && perfs[i]; };
    if (ok(n)) return perfs[n];
    for (var i = 0; i < 50; i++) if (ok(i)) return perfs[i];
    return null;
  }

  return { MIXER: MIXER, hash: hash, mixerEntry: mixerEntry, mixer: mixer, mixerWrite: mixerWrite,
           PERF_LEN: PERF_LEN, PERF_OK: PERF_OK, performRead: performRead, performWrite: performWrite, performChunk: performChunk, perform: perform, param: param, setParam: setParam, setOn: setOn, reorder: reorder, fromDump: fromDump, toDump: toDump, unpack7: unpack7, pack7: pack7, effectKey: effectKey,
           effectId: effectId, on: function (rec, i) { return rec[18 * i] & 1; }, name: name, setName: setName,
           routing: routing, setRouting: setRouting, BUS: BUS, OUT: OUT, SOLO: SOLO };
})();
if (typeof module === 'object') module.exports = Patch;
