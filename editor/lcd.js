// The pedal's own screens, drawn as on its LCD: 64 rows, but as wide as the content needs.
// Primitives ported from the 2.10 firmware via docs/dev/perform-ui-mockup.html; the Effect Chain from
// asm/mixer/chain_draw.c (all columns at once instead of three); the look from scripts/screens/make_screens.py lcd().
// Built by hand; the font and bitmap strings are copied from those files.
var LCD = (function () {
  'use strict';
  var W = 128, H = 64, fb = new Uint8Array(128 * 64), SW = 0;   // SW: every screen's width, the widest Effect Chain (set at the end)
  function begin(w, h) { W = Math.max(128, w | 0); H = h || 64; fb = new Uint8Array(W * H); return W; }
  // screens put side by side: grab() keeps what was drawn, paste() puts it into the next begin(), shift() moves its hits
  function grab() { return { w: W, h: H, fb: fb }; }
  function paste(g, ox, oy) { for (var y = 0; y < g.h; y++) for (var x = 0; x < g.w; x++) if (g.fb[y * g.w + x]) px(ox + x, oy + y, 1, 'set'); }
  function shift(hits, ox, oy, tag) { return hits.map(function (h) { return Object.assign({}, h, { x: h.x + ox, y: h.y + oy }, tag); }); }

  const F7="0000000000000000005f5f00000003030003030000143e14143e1400242a7f7f2a12002333180c666200367f4957265000000b0700000000001c3e634100000041633e1c000024187e7e18240018187e7e1818000058380000000018181818181800006060000000002030180c0602003e7f594d7f3e0000427f7f400000466171594f4600224149497f36001814127f7f1000274745457d39003e7f49497930000101717d0f0300367f49497f3600064f49497f3e00000036360000000000563600000000081c36630000363636363636000063361c080000060151590f06003a7d457d423c00707c13137c70007f7f49497f36003e7f41414122007f7f41633e1c007f7f49494941007f7f09090901003e7f4149797a007f7f08087f7f0000417f7f4100000040417f3f00007f7f1c366341007f7f40404040007f0e3c3c0e7f007f7f0e1c7f7f003e7f41417f3e007f7f11111f0e003e7f31615f5e007f7f19396f4600264f4d5979320001017f7f0101003f7f40407f3f00071f78781f07003f703e3e703f0063771c1c776300030f7c7c0f03006171795d4f4700007f7f4141000002060c183020000041417f7f0000040603060400006060606060600000010306040000207454547c78007f7f44447c3800387c4444442800387c44447f7f00387c54545c580000047e7f050100085c54547c3c007f7f04047c780000007d7d0000000040447d3d00007f7f10386c440000007f7f0000007c047c780478007c7c04047c7800387c44447c38007c7c24243c1800183c24247c7c007c7c180c0c0400485c5c7474240000043f7f4400003c7c40407c7c000c3c70703c0c007c603c3c607c006c381010386c000c5c60203c0c00646454544c4c00083e774141000000007777000000004141773e080002010302010000";
  const OS6="00000000000000004f000000000700070000147f147f1400242a7f2a1200231308646200364955225000000503000000001c224100000041221c000014083e08140008083e0808000050300000000808080808000060600000002010080402003e5149453e0000427f4000004261514946002141454b31001814127f10002745454539003c4a49493000017109050300364949493600064949291e00003636000000005636000000081422410000141414141400412214080000020151090600324979413e007e1111117e007f49494936003e41414122007f4141221c007f49494941007f09090901003e4149497a007f0808087f0000417f4100002040413f01007f08142241007f40404040007f020c027f007f0408107f003e4141413e007f09090906003e4151215e007f091929460046494949310001017f0101003f4040403f001f2040201f003f4038403f00631408146300070870080700615149454300007f414100000204081020000041417f00000402010204004040404040000001020400002054545478007f4844443800384444442000384444487f00385454541800087e090102000c5252523e007f080404780000447d4000002040443d00007f102844000000417f4000007c04180478007c08040478003844444438007c1414140800081414187c007c0804040800485454542000043f444020003c4040207c001c2040201c003c4030403c004428102844000c5050503c004464544c4400000836410000000077000000004136080000000201020100";
  const SOFT="000000003e223e00243e20003a2a2e002a2a3e000e083e002e2a3a003e2a3a0006023e003e2a3e002e2a3e003e0a3e003e2a14003e2222003e221c003e2a2a003e0a0a003e223a003e083e00223e220030203e003e0836003e2020003e043e003c081e003e223e003e0a0e001e122e003e0a34002e2a3a00023e02003e203e001e201e003e103e003608360006380600322a2600100804000014000008080800002e00000a06000000200000081c08002a1c2a0038283800081c3e003e1c0800";
  const KNOB="80403008040402020101010101010101010101010102020404083040807f8000000000000000804020100804081020408000000000000000807f0000030408080402010000000000000000000000010204080804030000";
  const TOG0 = "00000000e0f8fcfcfce4e4d8f8f0c000000000000000000000000000000000000000000003070f1f3f7fff7f7f3f3e70c0408000000000000000000000000000000000000000000e1f336f4e5c5c5e5f4f6e311f0e0000000000000000";
  const TOG1 = "0000000000000000000000000000000000c0f0f8d8e4e4fcfcfcf8e00000000000000000000000000000008040c0703e3f7f7fff7f3f1f0f0703000000000000000000000000000e1f316e4f5f5e5c5c4e6f331f0e0000000000000000";
  const FAD = "000002020aaaaaaaaaaa000000ffffffff000000aaaaaaaaaa0a0202020000080808082aaaaaaaaaaa000000ffffffff000000aaaaaaaaaa2a080808080800002020282a2a2a2a2a0000007f7f7f7f0000002a2a2a2a2a282020200000";
  function hex(s, o, n) { var a = []; for (var i = 0; i < n; i++) a.push(parseInt(s.substr((o + i) * 2, 2), 16)); return a; }
  function px(x, y, v, op) {
    if (v === undefined) v = 1;
    if (x < 0 || x >= W || y < 0 || y >= H) return;
    var i = y * W + x; fb[i] = op === 'xor' ? fb[i] ^ 1 : op === 'set' ? v : fb[i] | v;
  }
  function line(x0, y0, x1, y1) {   // 0xC00A132C: a single point draws nothing; ORs; C integer division
    if (x0 === x1 && y0 === y1) return;
    var cl = function (v) { return Math.max(-1, Math.min(W, v)); }, x, y, t;
    if (y0 === y1) { for (x = Math.min(cl(x0), cl(x1)); x <= Math.max(cl(x0), cl(x1)); x++) px(x, y0); return; }
    if (x0 === x1) { for (y = Math.min(y0, y1); y <= Math.max(y0, y1); y++) px(x0, y); return; }
    if (y0 > y1) { t = x0; x0 = x1; x1 = t; t = y0; y0 = y1; y1 = t; }
    if (y1 - y0 + 1 < Math.abs(x1 - x0) + 1) { var st = x1 >= x0 ? 1 : -1; for (x = x0; x !== x1 + st; x += st) px(x, Math.trunc(((y1 - y0) * x + x1 * y0 - x0 * y1) / (x1 - x0))); }
    else for (y = y0; y <= y1; y++) px(Math.trunc(((x1 - x0) * y + x0 * y1 - x1 * y0) / (y1 - y0)), y);
  }
  function rect(x0, y0, x1, y1, mode) {   // 0xC00A0144: 0 fill, 1 outline + clear inside, 2 clear, 3 outline
    for (var y = Math.min(y0, y1); y <= Math.max(y0, y1); y++) for (var x = Math.min(x0, x1); x <= Math.max(x0, x1); x++) {
      var edge = x === x0 || x === x1 || y === y0 || y === y1;
      if (mode === 0) px(x, y, 1, 'set'); else if (mode === 2) px(x, y, 0, 'set');
      else if (edge) px(x, y, 1, 'set'); else if (mode === 1) px(x, y, 0, 'set');
    }
  }
  function invert(x0, y0, x1, y1) { for (var y = y0; y <= y1; y++) for (var x = x0; x <= x1; x++) px(x, y, 1, 'xor'); }
  function blit(x, y, w, h, b, or) {   // column bytes, bit 0 on top; replaces the area
    for (var r = 0; r < h; r++) for (var c = 0; c < w; c++) { var v = b[(r >> 3) * w + c] >> (r & 7) & 1; if (or) { if (v) px(x + c, y + r); } else px(x + c, y + r, v, 'set'); }
  }
  function pagebyte(page, x, b, shift) {
    var lo = (b << shift) & 255, hi = (b << shift) >> 8;
    for (var r = 0; r < 8; r++) { px(x, page * 8 + r, lo >> r & 1, 'set'); if (hi >> r & 1) px(x, page * 8 + 8 + r); }
  }
  function code(ch) { return Math.max(32, Math.min(126, ch.charCodeAt(0))) - 32; }
  function font7(s, x, y) { s = String(s); for (var i = 0; i < s.length; i++) { blit(x, y, 7, 8, hex(F7, 7 * code(s[i]), 7)); x += 7; } }
  function font7r(s, right, y) { font7(s, right - 7 * String(s).length, y); }
  function font7c(s, cx, y) { font7(s, cx - Math.trunc(7 * String(s).length / 2), y); }
  function os6(s, x, y) { s = String(s); for (var i = 0; i < s.length; i++) { blit(x, y, 6, 8, hex(OS6, 6 * code(s[i]), 6)); x += 6; } }
  var SOFT_IDX = { 47: 37, 58: 38, 45: 39, 33: 40, 39: 41, 46: 42, 43: 43, 42: 44, 111: 45, 3: 46, 4: 47 };
  var SOFT_WIDE = { M: [0x3C, 0x02, 0x1C, 0x02, 0x3C, 0], W: [0x1E, 0x20, 0x1C, 0x20, 0x1E, 0], N: [0x3E, 0x04, 0x08, 0x3E, 0], '\x05': [0x04, 0x0C, 0x1C, 0x0C, 0x04, 0] };
  function softCols(ch) { var c = ch.charCodeAt(0), i = c >= 48 && c <= 57 ? c - 47 : c >= 65 && c <= 90 ? c - 54 : SOFT_IDX[c] || 0; return SOFT_WIDE[ch] || hex(SOFT, 4 * i, 4); }
  function softW(s) { var n = 0; for (var i = 0; i < s.length; i++) n += softCols(s[i]).length; return n; }
  function small(s, x, y) {   // the softkey font at any row; ink rows y..y+4
    for (var i = 0; i < s.length; i++) { var cols = softCols(s[i]); cols.forEach(function (b, j) { for (var r = 0; r < 8; r++) if (b >> r & 1) px(x + j, y + r - 1); }); x += cols.length; }
  }
  function softText(s, x) { for (var i = 0; i < s.length; i++) { var cols = softCols(s[i]); cols.forEach(function (b, j) { pagebyte(7, x + j, b, 1); }); x += cols.length; } }
  // the looper's status box: FONT7 proportional, XORed so it always contrasts the fill
  function fontP(s, x, y, ink) {
    for (var i = 0; i < s.length; i++) {
      if (s[i] === ' ') { x += 2; continue; }
      hex(F7, 7 * code(s[i]), 7).forEach(function (b) { if (!b) return; for (var r = 0; r < 7; r++) if (b >> r & 1) { px(x, y + r, 1, 'xor'); if (ink) ink[(y + r) * W + x] = 1; } x++; });
      x++;
    }
  }
  function widthP(s) { var n = 0; for (var i = 0; i < s.length; i++) n += s[i] === ' ' ? 2 : hex(F7, 7 * code(s[i]), 7).filter(function (b) { return b; }).length + 1; return n - 1; }
  function statusBar(fill, left, right) {
    var ink = new Uint8Array(W * 11), w = Math.trunc((W - 2) * fill);
    rect(0, 0, W - 1, 10, 1); if (w > 0) rect(1, 1, w, 9, 0);
    fontP(left, 3, 2, ink); fontP(right, W - 3 - widthP(right), 2, ink);
    return ink;
  }
  function toggle(on, x, y) { blit(x, y, 31, 24, hex(on ? TOG1 : TOG0, 0, 93)); }
  function fader(x, y, v, lo, hi) { blit(x, y, 31, 24, hex(FAD, 0, 93)); var h = Math.trunc(20 * (v - lo) / (hi - lo)); rect(x + 6, y + 20 - h, x + 23, y + 22 - h, 1); }
  function softkey(x0, x1, rx, cx, s, brackets) {
    softText(s, cx - 2 * s.length);
    if (!brackets) return invert(x0, 57, x1, 63);
    [[x0, [0xfe, 0x82]], [rx, [0x82, 0xfe]]].forEach(function (e) { e[1].forEach(function (v, j) { pagebyte(7, e[0] + j, v, 0); }); });
  }
  function softkey40(k, s, br) { softkey(40 * k + 5, 40 * k + 41, 40 * k + 35, 40 * k + 23, s, br); }
  function softkey42(k, s, br) { softkey(42 * k + 2, 42 * k + 41, 42 * k + 40, 42 * k + 22, s, br); }
  function frame(x, y, w, h) { line(x, y, x + w - 1, y); rect(x, y, x + 1, y + h - 1, 0); rect(x + w - 2, y, x + w - 1, y + h - 1, 0); }
  function knob(frac, x, y) {   // 0xC00A95A4: the knob bitmap, then the filled wedge row by row
    blit(x, y, 29, 20, hex(KNOB, 0, 87));
    var k = 40 / 33, C = 5 * Math.PI / 4, D0 = 0.785398163395, D1 = 2.356194490185, D2 = 3.926990816975;
    var cx = x + 14, cy = y + 10, t = frac * 3 * Math.PI * 0.5, a = C - t, S = 10 * Math.sin(a), cs = 10 * Math.cos(a);
    var tana = cs ? S / cs : Math.sign(S) * 1e300, tanC = Math.tan(C), sC = 10 * Math.sin(C), i, ms, row;
    var R = function (v) { return Math.sign(v) * Math.floor(Math.abs(v) + 0.5); }, q = function (i) { return tana ? i / tana : Math.sign(i) * 1e300; };
    for (i = Math.trunc(sC); i < 0; i++) {
      ms = -Math.sqrt(100 - i * i);
      if (t < D0 && !(ms > q(i)) && Math.abs(t - D0) >= 1e-4) line(cx + R(k * q(i)), cy - i, cx + R(k * i / tanC), cy - i);
      else line(cx + R(k * ms), cy - i, cx + R(k * i / tanC), cy - i);
    }
    if (t < D0) return;
    for (i = 1; i <= 10; i++) {
      if (!(t > D1) && i > S) return;
      ms = -Math.sqrt(100 - i * i); row = cy - i + 1;
      if (!(D1 > t) && i > S) line(cx + R(k * ms), row, cx + R(-k * ms), row); else line(cx + R(k * ms), row, cx + R(k * q(i)), row);
    }
    if (t < D2) return;
    var A1 = Math.trunc(S); if (A1 >= 0) return;
    for (i = -1; i >= A1; i--) { if (i < S) return; line(cx + R(k * q(i)), cy - i, cx + R(k * Math.sqrt(100 - i * i)), cy - i); }
  }
  function tab(x, y, st, s) {   // 0 current (outlined), 1 after it, 2 before it; returns the width
    var w = 7 * s.length + 7; font7(s, x + 4, y + 2);
    if (st === 0) {
      line(x + 3, y, x, y + 3); line(x + 4, y, x, y + 4); line(x + w - 4, y, x + w - 1, y + 3); line(x + w - 5, y, x + w - 1, y + 4); line(x + 4, y, x + w - 5, y);
      [x, x + 1, x + w - 2, x + w - 1].forEach(function (xx) { line(xx, y + 4, xx, y + 11); }); rect(x + 2, y + 11, x + w - 3, y + 11, 2);
    } else if (st === 1) { line(x, y, x + w - 4, y); line(x + 1, y + 1, x + w - 3, y + 1); invert(x + 2, y + 2, x + w - 2, y + 9); line(x + w - 1, y + 3, x + w - 1, y + 9); }
    else { line(x + 3, y, x + w - 1, y); line(x + 2, y + 1, x + w - 2, y + 1); invert(x + 1, y + 2, x + w - 3, y + 9); line(x, y + 3, x, y + 9); }
    return w;
  }
  function title(s) { font7c(s, W >> 1, 1); invert(0, 0, W - 1, 8); }
  function cursor(r, short) { invert(0, 11 + 9 * r, short ? W - 7 : W - 1, 19 + 9 * r); }
  function turnArrows(x) { blit(x - 7, 53, 5, 3, [4, 6, 7, 6, 4]); blit(x + 2, 53, 5, 3, [1, 3, 7, 3, 1]); }
  function scrollbar(top, total, vis, x, y, w, h) {
    rect(x, y, x + w - 1, y + h - 1, 1);
    var s = Math.trunc(top * (h - 2) / total), e = top + vis > total ? h - 3 : Math.trunc(vis * (h - 2) / total) + s;
    rect(x + 1, y + s + 1, x + w - 2, y + e + 1, 0);
    blit(x, y + h + 1, 5, 8, [1, 3, 7, 3, 1], true); blit(x, y - 4, 5, 8, [4, 6, 7, 6, 4], true);
  }

  // ---- the LCD look (make_screens.py lcd()): bezel, glass, 6x9 cells, indigo ink fading across ----
  var CELLW = 6, CELLH = 9, MG = 18, BZ = 14;
  var STOPS = [[0, [40, 48, 128]], [0.5, [44, 44, 130]], [1, [52, 40, 128]]];
  function inkAt(t) {
    for (var i = 0; i < 2; i++) {
      var a = STOPS[i], b = STOPS[i + 1];
      if (t <= b[0]) { var f = (t - a[0]) / (b[0] - a[0]); return 'rgb(' + [0, 1, 2].map(function (k) { return Math.round(a[1][k] + (b[1][k] - a[1][k]) * f); }) + ')'; }
    }
  }
  function present(cv) {
    var sw = W * CELLW + 2 * MG, sh = H * CELLH + 2 * MG, g, x, y;
    cv.width = sw + 2 * BZ; cv.height = sh + 2 * BZ;
    g = cv.getContext('2d');
    g.clearRect(0, 0, cv.width, cv.height);
    g.fillStyle = 'rgb(24,24,27)'; g.beginPath(); g.roundRect(0, 0, cv.width, cv.height, 16); g.fill();
    g.fillStyle = 'rgb(220,222,226)'; g.beginPath(); g.roundRect(BZ, BZ, sw, sh, 4); g.fill();
    g.fillStyle = 'rgb(226,228,231)'; g.fillRect(BZ + MG, BZ + MG, W * CELLW, H * CELLH);
    g.fillStyle = 'rgb(209,212,218)';
    for (y = 0; y < H; y++) for (x = 0; x < W; x++) if (!fb[y * W + x]) g.fillRect(BZ + MG + x * CELLW, BZ + MG + y * CELLH, CELLW - 1, CELLH - 1);
    for (x = 0; x < W; x++) {
      g.fillStyle = inkAt(x / (W - 1));
      for (y = 0; y < H; y++) if (fb[y * W + x]) g.fillRect(BZ + MG + x * CELLW, BZ + MG + y * CELLH, CELLW - 1, CELLH - 1);
    }
  }
  // a click on the canvas, in LCD pixels
  function at(cv, e) {
    var r = cv.getBoundingClientRect(), s = cv.width / r.width;
    return { x: Math.floor(((e.clientX - r.left) * s - BZ - MG) / CELLW), y: Math.floor(((e.clientY - r.top) * s - BZ - MG) / CELLH) };
  }
  function hit(hits, p) { for (var i = hits.length - 1; i >= 0; i--) { var h = hits[i]; if (p.x >= h.x && p.x < h.x + h.w && p.y >= h.y && p.y < h.y + h.h) return h; } return null; }

  // ---- the Effect Chain (asm/mixer/chain_draw.c) ----------------------------------------
  var CW = 38, CH = 19, YC = 32, YA = 21, YB = 43, K_IN = 0, K_OUT = 1, K_EFF = 2, K_NODE = 3, K_BUS = 4, K_ADD = 5;
  var IT_ROUTE = 0x10, IT_MIX = 0x11, IT_IN = 0x12, IT_OUT = 0x13, PRE = 0, BUS_A = 1, BUS_B = 2, POST = 3;
  var K5 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 []-.!/';
  var G5 = [[14,17,17,31,17,17,17],[30,17,17,30,17,17,30],[14,17,16,16,16,17,14],[28,18,17,17,17,18,28],[31,16,16,30,16,16,31],[31,16,16,30,16,16,16],
    [14,17,16,23,17,17,15],[17,17,17,31,17,17,17],[14,4,4,4,4,4,14],[7,2,2,2,2,18,12],[17,18,20,24,20,18,17],[16,16,16,16,16,16,31],
    [17,27,21,21,17,17,17],[17,17,25,21,19,17,17],[14,17,17,17,17,17,14],[30,17,17,30,16,16,16],[14,17,17,17,21,18,13],[30,17,17,30,20,18,17],
    [15,16,16,14,1,1,30],[31,4,4,4,4,4,4],[17,17,17,17,17,17,14],[17,17,17,17,17,10,4],[17,17,17,21,21,21,10],[17,17,10,4,10,17,17],
    [17,17,10,4,4,4,4],[31,1,2,4,8,16,31],[0,0,14,1,15,17,15],[16,16,22,25,17,17,30],[0,0,14,16,16,17,14],[1,1,13,19,17,17,15],
    [0,0,14,17,31,16,14],[6,9,8,28,8,8,8],[0,15,17,17,15,1,14],[16,16,22,25,17,17,17],[4,0,12,4,4,4,14],[2,0,6,2,2,18,12],
    [16,16,18,20,24,20,18],[12,4,4,4,4,4,14],[0,0,26,21,21,17,17],[0,0,22,25,17,17,17],[0,0,14,17,17,17,14],[0,0,30,17,30,16,16],
    [0,0,13,19,15,1,1],[0,0,22,25,16,16,16],[0,0,14,16,14,1,30],[8,8,28,8,8,9,6],[0,0,17,17,17,19,13],[0,0,17,17,17,10,4],
    [0,0,17,17,21,21,10],[0,0,17,10,4,10,17],[0,0,17,17,15,1,14],[0,0,31,2,4,8,31],[14,17,19,21,25,17,14],[4,12,4,4,4,4,14],
    [14,17,1,2,4,8,31],[31,2,4,2,1,17,14],[2,6,10,18,31,2,2],[31,16,30,1,1,17,14],[6,8,16,30,17,17,14],[31,1,2,4,8,8,8],
    [14,17,17,14,17,17,14],[14,17,17,15,1,2,12],[0,0,0,0,0,0,0],[14,8,8,8,8,8,14],[14,2,2,2,2,2,14],[0,0,0,31,0,0,0],
    [0,0,0,0,0,12,12],[4,4,4,4,4,0,4],[0,1,2,4,8,16,0]];
  var K3 = 'ABCDEGILMNOPRSTUX/F? !H{}';
  var G3 = [[2,5,7,5,5],[6,5,6,5,6],[3,4,4,4,3],[6,5,5,5,6],[7,4,6,4,7],[3,4,5,5,3],
    [7,2,2,2,7],[4,4,4,4,7],[5,7,7,5,5],[6,5,5,5,5],[2,5,5,5,2],[6,5,6,4,4],
    [6,5,6,5,5],[3,4,2,1,6],[7,2,2,2,2],[5,5,5,5,7],[5,5,2,5,5],[1,1,2,4,4],
    [7,4,6,4,4],[6,1,2,0,2],[0,0,0,0,0],[2,2,2,0,2],[5,5,7,5,5],[1,3,7,3,1],
    [4,6,7,6,4]];
  function fill(x, y, w, h, ink) { for (var j = y; j < y + h; j++) for (var i = x; i < x + w; i++) px(i, j, ink ? 1 : 0, 'set'); }
  function inv(x, y, w, h) { for (var j = y; j < y + h; j++) for (var i = x; i < x + w; i++) px(i, j, 1, 'xor'); }
  function sq(x, y, w, h) { fill(x, y, w, 1, 1); fill(x, y + h - 1, w, 1, 1); fill(x, y + 1, 1, h - 2, 1); fill(x + w - 1, y + 1, 1, h - 2, 1); }
  function text(keys, g, bits, s, x, y, ink, bold) {
    for (var c = 0; c < s.length; c++) {
      var n = keys.indexOf(s[c]); if (n < 0) n = keys.indexOf(' ');
      for (var r = 0; r < g[n].length; r++) for (var i = 0; i < bits; i++) if (g[n][r] >> (bits - 1 - i) & 1) fill(x + i, y + r, bold ? 2 : 1, 1, ink);
      x += bits + 1 + (bold ? 1 : 0);
    }
  }
  function t5(s, x, y, ink, bold) { text(K5, G5, 5, s, x, y, ink, bold); }
  function t3(s, x, y, ink) { text(K3, G3, 3, s, x, y, ink, 0); }
  function t7(s, x, y) { t5(s, x, y, 1, 1); }
  function w5(s, bold) { return s.length * (bold ? 7 : 6) - 1; }
  function w3(s) { return s.length * 4 - 1; }
  function clear(x, y, w, h, cur) { if (cur) fill(x - 2, y - 2, w + 4, h + 4, 0); else fill(x, y, w, h, 0); }
  function mark(x, y, w, h, sel) { if (sel) inv(x - 2, y - 2, w + 4, h + 4); else sq(x - 2, y - 2, w + 4, h + 4); }
  function prect(l, y, dot, x, yy, w, h) { for (var i = 0; i < w; i++) for (var j = 0; j < h; j++) if (!dot || ((x + i + yy + j) & 1) === 0) fill(l + x + i, y + yy + j, 1, 1, 1); }
  function pill(l, y, dot, t) {
    prect(l, y, dot, 1, 0, CW - 2, 1); prect(l, y, dot, 0, 1, CW, t - 1); prect(l, y, dot, 0, CH - t, CW, t - 1); prect(l, y, dot, 1, CH - 1, CW - 2, 1);
    prect(l, y, dot, 0, t, 1, CH - 2 * t); prect(l, y, dot, CW - 1, t, 1, CH - 2 * t);
    prect(l, y, dot, 1, t, 1, 1); prect(l, y, dot, CW - 2, t, 1, 1); prect(l, y, dot, 1, CH - 1 - t, 1, 1); prect(l, y, dot, CW - 2, CH - 1 - t, 1, 1);
  }
  function label(c, slot, l, y) {
    var nm = c.name[slot] || '', a = nm.substr(0, 5), z = nm.substr(5, 5);
    t7(a, l + 1 + Math.trunc((CW - 2 - w5(a, 1)) / 2), y + 2);
    if (c.full && c.full[slot]) z = 'FULL';
    t7(z, l + 1 + Math.trunc((CW - 2 - w5(z, 1)) / 2), y + 10);
  }
  function cover(d, slot, l, cy) {
    var y = cy - 9, cur = d.cur === slot, c = d.c;
    if (slot === -2) { d.hits.push({ it: 'land', x: l, y: y, w: CW, h: CH }); return clear(l, y, CW, CH, 0); }   // where it lands: an empty frame, drawn last (chain)
    d.hits.push({ it: slot, x: l, y: y, w: CW, h: CH });
    if (c.drag && c.drag.slot === slot) { clear(l, y, CW, CH, 0); pill(l, y, c.land ? 1 : 0, 1); return; }   // dragged away: a dotted outline stays (solid: it stays here)
    clear(l, y, CW, CH, cur);
    pill(l, y, !c.on[slot], cur && c.sel ? 1 : 2);
    label(c, slot, l, y);
    if (cur) { mark(l, y, CW, CH, c.sel); d.delX = l; d.delY = cy; }
  }
  // the dragged effect, inverted as when chosen, under the pointer; c.drag: { slot, x, y } in LCD pixels
  function floating(c) {
    var g = c.drag, l = g.x - (CW >> 1), y = Math.max(11, Math.min(64 - CH - 2, g.y - (CH >> 1)));
    fill(l - 2, y - 2, CW + 4, CH + 4, 0); pill(l, y, 0, 1); label(c, g.slot, l, y); inv(l - 2, y - 2, CW + 4, CH + 4);
  }
  // a "+" or "-" box (at x, y), 13 x 9 pixels: square on the 6 x 9 cells; hit is its click region
  var AW = 13, PAD = 15;
  function btn(d, x, y, plus, hit) {
    fill(x, y, 13, 9, 0); sq(x, y, 13, 9); fill(x + 3, y + 4, 7, 1, 1); if (plus) fill(x + 6, y + 2, 1, 5, 1);
    hit.x = x - 1; hit.y = y - 1; hit.w = 15; hit.h = 11; d.hits.push(hit);
  }
  // "+": add an effect at this zone's output end (only on an empty chain)
  function addBox(d, z, l, cy) { btn(d, l + 1, cy - 4, 1, { it: 'add', z: z }); }
  var IC_SERIAL = [2, 0, 6, 29, 6, 0], IC_SPLIT = [2, 0, 2, 29, 2, 2, 0, 10, 29, 10, 0];
  var IC_PARAL = [4, 0, 2, 11, 2, 19, 6, 29, 6, 4, 0, 10, 11, 10, 19, 6, 29, 6, 0];
  var IC_MONO = [4, 0, 6, 10, 6, 18, 2, 29, 2, 4, 0, 6, 10, 6, 18, 10, 29, 10, 0];
  var IC_STEREO = [6, 0, 2, 5, 2, 13, 6, 16, 6, 24, 2, 29, 2, 6, 0, 10, 5, 10, 13, 6, 16, 6, 24, 10, 29, 10, 0];
  var IC_ROUTE = [IC_SERIAL, IC_PARAL, IC_SPLIT, IC_MONO], IC_MIX = [IC_STEREO, IC_MONO, IC_SPLIT];
  function icon(p, x, y) {
    var o = 0;
    while (p[o]) {
      var n = p[o++];
      for (var i = 1; i < n; i++) {
        var x0 = p[o + 2 * i - 2], y0 = p[o + 2 * i - 1], x1 = p[o + 2 * i], y1 = p[o + 2 * i + 1], dx = x1 - x0;
        for (var cx = x0; cx <= x1; cx++) fill(x + cx, y + Math.floor((2 * (y0 * dx + (y1 - y0) * (cx - x0)) + dx) / (2 * dx)), 1, 2, 1);
      }
      var t = p[o + 1];
      fill(x + 1, y + t - 1, 2, 4, 1); fill(x + 3, y + t - 2, 2, 6, 1);   // arrowhead pointing left
      o += 2 * n;
    }
  }
  function node(d, n, l) {   // stock EXIT box as wide as a cover, as tall as both bus rows
    var top = YA - 9, h = YB - YA + CH, cur = d.cur === n, name = n === IT_ROUTE ? 'ROUTE' : 'MIX';
    clear(l, top, CW, h, cur);
    sq(l, top, CW, h);
    t7(name, l + 1 + Math.trunc((CW - 2 - w5(name, 1)) / 2), top + 2);
    icon(n === IT_MIX ? IC_MIX[d.c.out % 3] : IC_ROUTE[d.c.mode & 3], l + 4, YC - 6);
    if (n === IT_MIX && d.c.silent) t7('!', l + 16, top + 31);
    if (cur) mark(l, top, CW, h, d.c.sel);
    d.hits.push({ it: n === IT_ROUTE ? 'route' : 'mix', x: l, y: top, w: CW, h: h });
  }
  function lane(y, st) { return st ? [y - 1, y + 1] : [y]; }
  function isPar(c) { return c.mode === 1 || c.mode === 2; }
  function lanesM(c) { return lane(YC, c.stereo); }
  function lanesBus(c, y) { return lane(y, c.stereo && c.mode !== 2); }
  function lanesAB(c) { return lanesBus(c, YA).concat(lanesBus(c, YB)); }
  function lanesL(c) { return c.mode === 3 ? [YC] : lanesM(c); }
  function lanesP(c) { return c.out === 1 || c.mode === 3 ? [YC] : c.out === 2 && isPar(c) ? [YC - 1, YC + 1] : lane(YC, c.stereo); }
  function zoneOf(c, slot) { for (var b = 0; b < 4; b++) if (c.z[b].indexOf(slot) >= 0) return b; return -1; }
  function leftOf(c, col) {
    if (col.kind === K_IN) return lanesM(c);
    if (col.kind === K_OUT) return [];
    if (col.kind === K_BUS) return lanesAB(c);
    if (col.kind === K_NODE) return isPar(c) ? lanesAB(c) : lanesL(c);
    if (col.kind === K_ADD) return col.e === PRE ? lanesM(c) : col.e === POST ? lanesP(c) : isPar(c) ? lanesAB(c) : lanesL(c);
    var z = zoneOf(c, col.e);
    return z === PRE ? lanesM(c) : z === POST ? lanesP(c) : lanesL(c);
  }
  function plugs(c, out, n) { return n > 1 || (out && c.out === 0) ? [YA, YB] : [YC]; }
  function fanKind(c, cols, j) {   // 1 split (before Parallel / Split [ROUTE]), 2 sum (Mono Serial), 3 join (after [MIX], or Serial into a mono Output)
    if (j < 0 || j + 1 >= cols.length) return 0;
    if (cols[j + 1].kind === K_NODE && cols[j + 1].e === IT_ROUTE) return isPar(c) ? 1 : c.mode === 3 && c.stereo ? 2 : 0;
    if (cols[j].kind === K_NODE && cols[j].e === IT_MIX) return 3;
    return cols[j].jn && lanesP(c).length < lanesL(c).length ? 3 : 0;
  }
  function groups(c, kind) {
    var m = lanesM(c), g = [];
    if (kind === 1) return m.map(function (y, i) { return { y: y, t: c.mode === 2 ? [i ? YB : YA] : [y - YC + YA, y - YC + YB] }; });
    if (kind === 2) return [{ y: YC, t: m.slice() }];
    var p = lanesP(c);
    return p.map(function (py) {
      var t = [];
      if (!isPar(c)) return { y: py, t: lanesL(c) };
      [YA, YB].forEach(function (mm) {
        var b = lanesBus(c, mm);
        b.forEach(function (by) { if (c.out === 2 ? mm === (py < YC ? YA : YB) : p.length < 2 || b.length < 2 || by - mm === py - YC) t.push(by); });
      });
      return { y: py, t: t };
    });
  }
  function wires(h, v) {   // a horizontal that crosses a vertical mid-way hops over it
    v.forEach(function (s) { fill(s[0], s[1], 1, s[2] - s[1] + 1, 1); });
    h.forEach(function (r) {
      var x0 = Math.min(r[1], r[2]), x1 = Math.max(r[1], r[2]);
      v.forEach(function (s) { if (s[0] > x0 && s[0] < x1 && r[0] > s[1] && r[0] < s[2]) { fill(s[0], r[0] - 1, 1, 1, 0); fill(s[0], r[0] + 1, 1, 1, 0); } });
      fill(x0, r[0], x1 - x0 + 1, 1, 1);
    });
  }
  function fan(g, w, gr, split) {
    var lo = gr.map(function (q) { return Math.min.apply(null, [q.y].concat(q.t)); }), hi = gr.map(function (q) { return Math.max.apply(null, [q.y].concat(q.t)); });
    var one = 1, h = [], v = [];
    for (var i = 0; i < gr.length; i++) for (var j = 0; j < gr.length; j++) if (i !== j && !(hi[i] < lo[j] || hi[j] < lo[i])) one = 0;
    gr.forEach(function (q, i) {
      var dd = one ? 1 : 2 * i, x = split ? g + 2 + dd : g + w - 3 - dd;
      h.push([q.y, split ? g + w - 1 : g, x]);
      q.t.forEach(function (t) { h.push([t, split ? g : g + w - 1, x]); });
      v.push([x, lo[i], hi[i]]);
    });
    wires(h, v);
  }
  function hline(x, y, w, dot) { if (!dot) return fill(x, y, w, 1, 1); for (var i = 0; i < w; i += 2) fill(x + i, y, 1, 1, 1); }
  function dead(c, col, y) { var k = y < YC ? BUS_A : BUS_B; return col.bi >= 0 && c.mute[k - 1] && col.bi >= c.z[k].length - 1; }
  var PLUG = [[0, 3, 4, 4], [3, 7, 1, 1], [4, 1, 1, 2], [4, 7, 1, 2], [5, 0, 13, 1], [5, 9, 13, 1], [18, 0, 1, 10],
    [19, 2, 5, 1], [19, 7, 5, 1], [21, 3, 2, 4], [24, 3, 1, 1], [24, 6, 1, 1], [25, 2, 2, 1], [25, 7, 2, 1], [27, 3, 1, 4]];
  function mx(out, l, x, w) { return out ? l + CW - 1 - (x - l) - (w - 1) : x; }
  function jack(d, out, l, ln) {
    var ys = plugs(d.c, out, ln.length), x0 = l + 5, h = [], v = [];
    ys.forEach(function (yy, i) {
      var top = yy - 4, lv = i < ln.length ? ln[i] : ln[0], x = mx(out, l, l + 2, 1);
      PLUG.forEach(function (p) { fill(mx(out, l, x0 + p[0], p[2]), top + p[1], p[2], p[3], 1); });
      for (var r = 1; r <= 8; r++) { fill(mx(out, l, x0 + 7 + (r % 2 ? 0 : 1), 1), top + r, 1, 1, 1); fill(mx(out, l, x0 + 14 + (r % 2 ? 0 : 1), 1), top + r, 1, 1, 1); }
      h.push([yy, x, mx(out, l, x0, 1)]); h.push([lv, mx(out, l, l, 1), x]);
      v.push([x, Math.min(yy, lv), Math.max(yy, lv)]);
    });
    wires(h, v);
    var y0 = ys[0] - 4, hh = ys[ys.length - 1] - ys[0] + 10;
    if (d.cur === (out ? IT_OUT : IT_IN)) mark(l, y0, CW, hh, d.c.sel);
    if (out && d.c.limit) { var k = ys.length > 1 ? YC - 3 : 12; fill(l + 9, k, w3('LIMIT') + 2, 7, 1); t3('LIMIT', l + 10, k + 1, 0); }
    d.hits.push({ it: out ? 'out' : 'in', x: l, y: 12, w: CW, h: 42 });
  }
  function jackLanes(c, cols, i) {
    var out = cols[i].kind === K_OUT, nb = out ? i - 1 : i + 1;
    var n = !out ? lanesM(c) : fanKind(c, cols, i - 1) ? lanesP(c) : leftOf(c, cols[nb]);
    return cols[nb].kind === K_NODE ? plugs(c, out, n.length) : n;
  }
  // c: { mode 0-3, stereo, out 0-2, mute [A, B], name[6], on[6], z [Pre, A, B, Post] slot lists, cur (slot or IT_*), sel }
  // Every column, IN at the right edge. Returns the click regions: { it: slot | 'route' | 'mix' | 'in' | 'out' | 'bus', z, x, y, w, h }.
  // c.add: show a "+" at each zone's output end (empty chain); c.ins: "+" beside the chosen item (room for an effect);
  // c.del: a "-" under the chosen effect; c.drag / c.land: see floating. As wide as its columns, centered in SW.
  function chain(c) {
    var cols = [], par = isPar(c), d = { c: c, cur: c.cur, hits: [], delX: -1 }, i, j, n;
    function push(kind, e, a, b, bi) { cols.push({ kind: kind, e: e, a: a, b: b, bi: bi, jn: 0 }); }
    function cw(col) { return col.kind === K_ADD ? AW : CW; }
    if (!par && d.cur === IT_MIX) d.cur = IT_ROUTE;   // Serial has no [MIX]
    if (c.drag && c.land) {   // c.land: { z, i } the landing frame goes before entry i of zone z
      c = Object.assign({}, c, { z: c.z.map(function (l) { return l.slice(); }) }); d.c = c;
      c.z[c.land.z].splice(c.land.i, 0, -2);
    }
    push(K_IN, IT_IN, -1, -1, -1);
    c.z[PRE].forEach(function (s) { push(K_EFF, s, -1, -1, -1); });
    if (c.add) push(K_ADD, PRE, -1, -1, -1);
    push(K_NODE, IT_ROUTE, -1, -1, -1);
    if (par) {
      n = Math.max(c.z[BUS_A].length, c.z[BUS_B].length, c.add ? 0 : 1);
      for (i = 0; i < n; i++) push(K_BUS, -1, i < c.z[BUS_A].length ? c.z[BUS_A][i] : -1, i < c.z[BUS_B].length ? c.z[BUS_B][i] : -1, i);
      if (c.add) push(K_ADD, BUS_A, -1, -1, n);
      push(K_NODE, IT_MIX, -1, -1, -1);
    } else {
      c.z[BUS_A].concat(c.z[BUS_B]).forEach(function (s) { push(K_EFF, s, -1, -1, -1); });
      if (c.add) push(K_ADD, c.z[BUS_B].length ? BUS_B : BUS_A, -1, -1, -1);
      cols[cols.length - 1].jn = 1;
    }
    c.z[POST].forEach(function (s) { push(K_EFF, s, -1, -1, -1); });
    if (c.add) push(K_ADD, POST, -1, -1, -1);
    push(K_OUT, IT_OUT, -1, -1, -1);
    var gap = cols.map(function (_, j) { return j + 1 < cols.length ? (fanKind(c, cols, j) ? 7 : 4) : 0; }), pc = -1;
    if (!c.drag && d.cur >= 0) cols.forEach(function (col, j) { if (col.kind !== K_ADD && (col.e === d.cur || col.kind === K_BUS && (col.a === d.cur || col.b === d.cur))) pc = j; });
    var plus = pc >= 0 && c.ins && !c.add;
    if (plus) { if (pc + 1 < cols.length) gap[pc] += PAD; if (pc > 0) gap[pc - 1] += PAD; }   // room for the "+" on each side
    var w = 6 + cols.reduce(function (a, col) { return a + cw(col); }, 0) + gap.reduce(function (a, b) { return a + b; }, 0), X = [];
    begin(Math.max(w, SW), 67);
    X[0] = W - 3 - CW - ((W - w) >> 1);
    for (i = 1; i < cols.length; i++) X[i] = X[i - 1] - cw(cols[i]) - gap[i - 1];
    for (j = 0; j + 1 < cols.length; j++) {   // the lines in the gap between column j and j + 1
      var g = X[j + 1] + cw(cols[j + 1]), gw = X[j] - g, f = fanKind(c, cols, j), s = -1;
      if (cols[j].kind <= K_OUT && cols[j + 1].kind === K_NODE) s = j;
      else if (cols[j + 1].kind <= K_OUT && cols[j].kind === K_NODE) s = j + 1;
      if (s >= 0) jackLanes(c, cols, s).forEach(function (y) { hline(g, y, gw, 0); });
      else if (f) fan(g, gw, groups(c, f), f === 1);
      else leftOf(c, cols[j]).forEach(function (y) { hline(g, y, gw, dead(c, cols[j], y)); });
    }
    cols.forEach(function (col, i) {
      var l = X[i];
      if (col.kind <= K_OUT) jack(d, col.kind === K_OUT, l, jackLanes(c, cols, i));
      else if (col.kind === K_NODE) node(d, col.e, l);
      else if (col.kind === K_EFF) cover(d, col.e, l, YC);
      else if (col.kind === K_ADD) {
        leftOf(c, col).forEach(function (y) { hline(l, y, AW, dead(c, col, y)); });
        if (col.e === BUS_A && par) { addBox(d, BUS_A, l, YA); addBox(d, BUS_B, l, YB); } else addBox(d, col.e, l, YC);
      }
      else [[col.a, YA, BUS_A], [col.b, YB, BUS_B]].forEach(function (e) {
        if (e[0] >= 0 || e[0] === -2) return cover(d, e[0], l, e[1]);
        lanesBus(c, e[1]).forEach(function (y) { hline(l, y, CW, c.mute[e[2] - 1]); });
        d.hits.push({ it: 'bus', z: e[2], x: l, y: e[1] - 9, w: CW, h: CH });
      });
    });
    fill(0, 0, W, 9, 1);
    t5('EFFECT CHAIN', (W >> 1) - Math.trunc(w5('EFFECT CHAIN', 1) / 2), 1, 0, 1);
    function boxX(j) {   // a box in gap j, clear of a fan's vertical lines
      var g = X[j + 1] + cw(cols[j + 1]), gw = X[j] - g, f = fanKind(c, cols, j);
      return f === 1 ? g + gw - AW - 3 : f ? g + 3 : g + ((gw - AW) >> 1);
    }
    function one(j, y, z, end) { btn(d, boxX(j), y - 4, 1, { it: 'ins', z: z, end: end }); }
    var k = pc >= 0 ? cols[pc].kind : -1;
    if (pc >= 0 && d.delX >= 0) {   // "+" before (right, nearer IN) and after the chosen effect, "-" under it
      var l0 = d.delX, cy = d.delY, by = cy === YA ? 57 : cy + 14;
      if (plus) { btn(d, boxX(pc - 1), cy - 4, 1, { it: 'ins', after: 0 }); btn(d, boxX(pc), cy - 4, 1, { it: 'ins', after: 1 }); }
      if (c.del) btn(d, l0 + ((CW - AW) >> 1), by, 0, { it: 'del' });
    } else if (plus && k !== K_EFF && k !== K_BUS) {   // beside IN, ROUTE, MIX or OUT: the start or end of the zones next to it
      var e = cols[pc].e;
      if (e === IT_IN) one(0, YC, PRE, 0);
      else if (e === IT_OUT) one(pc - 1, YC, POST, 1);
      else if (e === IT_ROUTE) { one(pc - 1, YC, PRE, 1); if (par) { one(pc, YA, BUS_A, 0); one(pc, YB, BUS_B, 0); } else one(pc, YC, BUS_A, 0); }
      else { one(pc - 1, YA, BUS_A, 1); one(pc - 1, YB, BUS_B, 1); one(pc, YC, POST, 0); }
    }
    if (c.drag) {   // the landing frame shows through the dragged effect
      floating(c);
      d.hits.forEach(function (h) { if (h.it === 'land') { inv(h.x + 1, h.y, CW - 2, 1); inv(h.x + 1, h.y + CH - 1, CW - 2, 1); inv(h.x, h.y + 1, 1, CH - 2); inv(h.x + CW - 1, h.y + 1, 1, CH - 2); } });
    }
    return d.hits;
  }

  // ---- a stock knob page, as wide as its parameters: tabs, frame, one column per parameter ----
  // tabs: names, cur the outlined one; ps: [{ name, look: 'knob' | 'fader' | 'toggle', v, max, text }]. Returns click regions.
  // on (1/0, null: none): an ON/OFF softkey top right, filled when on, as the play screen's keys
  function knobPage(tabs, cur, ps, w, on) {   // w (default SW) wide; the knobs centered, each in a column up to 60 wide
    var hits = [], x = 0, n = ps.length, cell, x0;
    begin(w || Math.max(SW, 40 * n + 8, tabs.reduce(function (a, s) { return a + 7 * s.length + 6; }, 1)));
    cell = Math.min(60, Math.floor((W - 8) / Math.max(1, n))); x0 = (W - n * cell) >> 1;
    frame(0, 11, W, 53); line(0, 63, W - 1, 63);
    tabs.forEach(function (s, i) { var tw = tab(x, 0, i < cur ? 2 : i === cur ? 0 : 1, s); hits.push({ it: 'tab', i: i, x: x, y: 0, w: tw, h: 11 }); x += tw - 1; });
    ps.forEach(function (p, i) {
      var cx = x0 + cell * i + ((cell - 31) >> 1);
      font7(p.name, cx, 16);
      if (p.look === 'toggle') toggle(p.v >= 1, cx, 24);
      else if (p.look === 'fader') fader(cx, 24, p.v, 0, p.max);
      else knob(p.max ? p.v / p.max : 0, cx, 24);
      font7r(p.text, cx + 30, 48);
      hits.push({ it: 'param', i: i, x: x0 + cell * i, y: 12, w: cell, h: 52 });
    });
    if (on != null) {
      var s = on ? 'ON' : 'OFF', bw = 7 * 3 + 9, bx = W - bw;   // flush right as the frame, as tall as the tab, 1 row above the frame
      font7c(s, bx + (bw >> 1), 2);   // the tab's font, on the tab's text rows
      if (on) invert(bx, 0, W - 1, 9); else rect(bx, 0, W - 1, 9, 3);
      hits.push({ it: 'onoff', x: bx, y: 0, w: bw, h: 11 });
    }
    return hits;
  }

  // ---- PERFORM (asm/perform/perform_draw.c) ----------------------------------------------
  // the play screen, 128 wide. s: { left, right, fill 0-1, cycle, cols [3] { fx, lab, look, v, max, text } or null,
  // keys [3] { name, ftsw, on }, sel: 'bar' or control 0-5 } (shown inverted, as a waiting move). Returns click regions.
  var AR = [[4, 14, 31], [1, 3, 7, 3, 1], [31, 14, 4]];
  function control(look, v, max, x, y) {
    if (look === 'toggle') toggle(v >= 1, x, y);
    else if (look === 'fader') fader(x, y, Math.max(0, Math.min(max, v)), 0, max);
    else knob(max ? Math.max(0, Math.min(max, v)) / max : 0, x, y);
  }
  function play(s) {
    var hits = [], C = s.cycle, i, x, y, ink;
    begin(128);
    ink = statusBar(s.sel === 'bar' ? 1 : s.fill || 0, s.left, s.right);
    var near = function (x, y) { for (var dx = -1; dx <= 1; dx++) for (var dy = -1; dy <= 1; dy++) if (ink[(y + dy) * W + x + dx]) return 1; return 0; };
    for (i = 1; i < C; i++) {   // a gap in the top and bottom edge at each bar line, a dotted line across
      x = Math.trunc((i * 252 + C) / (2 * C));
      px(x, 0, 1, 'xor'); px(x, 10, 1, 'xor');
      for (y = 2; y <= 8; y += 2) if (!near(x, y)) px(x, y, 1, 'xor');
    }
    hits.push({ it: 'bar', x: 0, y: 0, w: 128, h: 11 });
    s.cols.forEach(function (c, i) {
      var mid = function (t, y) { small(t, 42 * i + 22 - ((softW(t) - 1) >> 1), y); };
      if (!c) mid('-', 19);
      else {
        mid(c.fx, 13); mid(c.lab, 19);
        control(c.look, c.v, c.max, 42 * i + 7, c.look === 'fader' ? 25 : c.look === 'knob' ? 27 : 24);
        mid(c.text, 50);
      }
      if (s.sel === i) invert(42 * i + 2, 12, 42 * i + 41, 55);
      hits.push({ it: 'ctl', i: i, x: 42 * i + 2, y: 12, w: 40, h: 44 });
    });
    s.keys.forEach(function (k, i) {
      var a = k.name;
      while (softW(a) - 1 > 30) a = a.slice(0, -1);
      softText(a, 42 * i + 26 - ((softW(a) - 1) >> 1));
      if (k.ftsw && !k.on) rect(42 * i + 2, 57, 42 * i + 41, 63, 3); else invert(42 * i + 2, 57, 42 * i + 41, 63);
      if (s.sel === 3 + i) invert(42 * i + 3, 58, 42 * i + 40, 62);   // chosen: the box turns over
      var h = AR[i].length === 3 ? 5 : 3;
      AR[i].forEach(function (col, j) { for (var y = 0; y < h; y++) if (col >> y & 1) px(42 * i + 5 + j, 60 - (h >> 1) + y, 1, 'xor'); });
      hits.push({ it: 'ctl', i: 3 + i, x: 42 * i + 2, y: 57, w: 40, h: 7 });
    });
    return hits;
  }
  // the stock list: title, 4 OS-font rows, cursor, scroll bar. rows [[label, value]], top the first row shown.
  // Returns { hits, top }: { it: 'row', i } and { it: 'up' | 'down' } on the scroll bar.
  function list(name, rows, cur, top, w) {   // w wide (128 on the pedal)
    var n = rows.length, bar = n > 4, hits = [], i, e;
    w = w || 128; begin(w); e = bar ? w - 7 : w - 1;
    top = Math.max(0, Math.min(top, n - 4));   // the caller keeps cur in view when it moves it; the scroll bar may scroll it out
    font7c(name, w >> 1, 1); invert(0, 0, w - 1, 8);
    for (i = 0; i < 4 && top + i < n; i++) {
      var l = rows[top + i][0], v = rows[top + i][1];
      os6(l, 1, 12 + 9 * i);
      os6(v, e - 6 * v.length, 12 + 9 * i);
      hits.push({ it: 'row', i: top + i, x: 0, y: 11 + 9 * i, w: e + 1, h: 9 });
    }
    if (cur >= top && cur < top + 4) invert(0, 11 + 9 * (cur - top), e, 19 + 9 * (cur - top));
    if (bar) {
      rect(w - 6, 11, w - 1, 54, 2); rect(w - 5, 16, w - 1, 41, 1);
      var s0 = Math.trunc(top * 24 / n), e0 = top + 4 > n ? 23 : Math.trunc(96 / n) + s0;
      rect(w - 4, 17 + s0, w - 2, 17 + e0, 0);
      blit(w - 5, 43, 5, 8, [1, 3, 7, 3, 1], true); blit(w - 5, 12, 5, 8, [4, 6, 7, 6, 4], true);
      hits.push({ it: 'up', x: w - 6, y: 11, w: 6, h: 22 }, { it: 'down', x: w - 6, y: 33, w: 6, h: 22 });
    }
    return { hits: hits, top: top };
  }
  // a list on one SW-wide screen, with another list or a knob page beside it and a line between them;
  // G blank columns at the screen's edges and on both sides of the line.
  // a: [name, rows, cur, top]; b: null, [name, rows, cur, top] or { tabs, cur, ps } (a knob page).
  // Returns { hits (side 0 or 1), top: [a's, b's], div: the line's x (SW: none) }
  function lists(a, b) {
    var G = 3, ra, rb = null, hb, ga, gb, L, R, x2;
    if (!b) { ra = list(a[0], a[1], a[2], a[3], SW - 2 * G); ga = grab(); begin(SW); paste(ga, G, 0); return { hits: shift(ra.hits, G, 0, { side: 0 }), top: [ra.top], div: SW }; }
    L = (SW - 1 - 4 * G) >> 1; R = SW - 1 - 4 * G - L; x2 = SW - G - R;
    ra = list(a[0], a[1], a[2], a[3], L); ga = grab();
    if (Array.isArray(b)) { rb = list(b[0], b[1], b[2], b[3], R); hb = rb.hits; } else hb = knobPage(b.tabs, b.cur, b.ps, R);
    gb = grab();
    begin(SW); paste(ga, G, 0); paste(gb, x2, 0); line(2 * G + L, 0, 2 * G + L, 63);
    return { hits: shift(ra.hits, G, 0, { side: 0 }).concat(shift(hb, x2, 0, { side: 1 })), top: [ra.top, rb ? rb.top : 0], div: 2 * G + L };
  }
  // the footswitch key, w x 24, drawn as a softkey: dark, white in a frame when chosen.
  // The stomp is seen at an angle: a base ring, the cap's top face and its side; the cap hides the ring behind it.
  function ellipse(cx, cy, rx, ry, lower, clr) {
    if (clr) { for (var yy = -ry; yy <= ry; yy++) if (!lower || yy >= 0) { var hw = Math.round(rx * Math.sqrt(1 - yy * yy / (ry * ry))); fill(cx - hw, cy + yy, 2 * hw + 1, 1, 0); } return; }
    for (var a = 0; a < 360; a += 2) {
      var t = a * Math.PI / 180, y = Math.round(cy + ry * Math.sin(t));
      if (!lower || y >= cy) px(Math.round(cx + rx * Math.cos(t)), y);
    }
  }
  function ftsw(target, on, w) {
    w = w || 128; begin(w, 24);
    ellipse(15, 14, 10, 4, 0);                       // base ring
    ellipse(15, 12, 6, 2, 1, 1); fill(9, 7, 13, 6, 0); ellipse(15, 7, 6, 2, 0, 1);   // the cap is solid
    ellipse(15, 12, 6, 2, 1);                        // the cap's lower edge
    line(9, 7, 9, 12); line(21, 7, 21, 12);          // the cap's sides
    ellipse(15, 7, 6, 2, 0);                         // the cap's top face
    font7('FOOTSWITCH', 32, 4);
    var t = String(target || 'OFF').toUpperCase(); while (softW(t) > w - 38) t = t.slice(0, -1);
    small(t, 32, 15);
    if (on) rect(0, 0, w - 1, 23, 3); else invert(0, 0, w - 1, 23);
    return [{ it: 'ftsw', x: 0, y: 0, w: w, h: 24 }];
  }
  // the play screen with the footswitch key under it (one blank row between, the softkeys' side margins), SW wide
  function perform(s, target, on) {
    var h1 = play(s), a = grab(), h2 = ftsw(target, on, 124), b = grab(), ox;
    begin(SW, 89); ox = (W - 128) >> 1;
    paste(a, ox, 0); paste(b, ox + 2, 65);
    return shift(h1, ox, 0).concat(shift(h2, ox + 2, 65));
  }

  SW = (function () {   // the widest Effect Chain: 6 effects before ROUTE, or 5 with room for "+"
    var m = 0, e = [];
    [0, 1, 2, 3].forEach(function (mode) {
      [5, 6].forEach(function (n) {
        chain({ mode: mode, stereo: 1, out: 0, mute: [0, 0], name: [], on: [1, 1, 1, 1, 1, 1], z: [[0, 1, 2, 3, 4, 5].slice(0, n), e, e, e], cur: 0, sel: 1, del: 1, ins: n < 6 });
        m = Math.max(m, W);
      });
    });
    return m;
  })();

  return {
    play: play, list: list, lists: lists, control: control, ftsw: ftsw, perform: perform, SW: SW,
    begin: begin, present: present, at: at, hit: hit, px: px, line: line, rect: rect, invert: invert, blit: blit,
    font7: font7, font7r: font7r, font7c: font7c, os6: os6, small: small, softText: softText, softW: softW,
    statusBar: statusBar, widthP: widthP, toggle: toggle, fader: fader, knob: knob, tab: tab, frame: frame,
    softkey40: softkey40, softkey42: softkey42, title: title, cursor: cursor, turnArrows: turnArrows, scrollbar: scrollbar,
    chain: chain, knobPage: knobPage, IT_ROUTE: IT_ROUTE, IT_MIX: IT_MIX, IT_IN: IT_IN, IT_OUT: IT_OUT,
    width: function () { return W; }
  };
})();
