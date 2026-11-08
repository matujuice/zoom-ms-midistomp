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

  return { param: param, setParam: setParam, setOn: setOn, reorder: reorder, fromDump: fromDump, toDump: toDump, unpack7: unpack7, pack7: pack7, effectKey: effectKey,
           effectId: effectId, on: function (rec, i) { return rec[18 * i] & 1; }, name: name, setName: setName,
           routing: routing, setRouting: setRouting, BUS: BUS, OUT: OUT, SOLO: SOLO };
})();
if (typeof module === 'object') module.exports = Patch;
