// Runs docs/master-ui-mockup.html's script headless for the host test: 60 s of the made-up music at 50 ms frames, then the
// shots (like scratchpad shots.js). Writes <out>/audio.bin (per frame: int32 page, int32 scope span, then 2205 x (L, R, limiter, input L, input R)
// float32) and <out>/meta.json (the shots: name, frame, framebuffer string of 0 / 1).
const fs = require("fs");
const [html, out] = process.argv.slice(2);
const src = fs.readFileSync(html, "utf8");
let js = src.slice(src.lastIndexOf("<script>") + 8, src.lastIndexOf("</script>"));
js = js.replace("function analyse(L, R, iL, iR) {", "function analyse(L, R, iL, iR) { DUMP(L, R, lim, iL, iR);");
const el = () => ({ getContext: () => ({ fillRect() {} }), addEventListener() {}, setAttribute() {}, textContent: "", click() {} });
global.T = 0;
global.document = { getElementById: el, querySelectorAll: () => [] };
global.requestAnimationFrame = () => {};
global.performance = { now: () => T };
let buf = [];
global.DUMP = (L, R, l, a, b) => buf.push(L, R, l, a, b);
const api = new Function(js + `
return { step(ms) { T += ms; frameTick(T); }, set(p, h, v) { page = p; hot = h; if (v !== undefined) PAGES[1].v = v; }, fb, page: () => page, v: () => PAGES[1].v };`)();
const shots = [["spectrum", 0, false], ["scope", 1, false], ["scope-12ms", 1, false, 7], ["stereo", 2, false], ["loudness", 3, false], ["meters", 5, false], ["meters-hot", 5, true], ["in-meters", 4, false], ["in-meters-hot", 4, true]];
const frames = [], res = [];
const fd = fs.openSync(out + "/audio.bin", "w");
function frame() {
  buf = [];
  api.step(50);
  const hdr = new Int32Array([api.page(), api.v(), buf.length / 5]);
  fs.writeSync(fd, hdr); fs.writeSync(fd, new Float32Array(buf));
  return frames.push(0) - 1;
}
for (let i = 0; i < 1200; i++) frame();
for (const [name, p, h, v] of shots) {
  api.set(p, h, v);
  let f;
  for (let i = 0; i < (h ? 60 : 8); i++) f = frame();
  res.push({ name, frame: f, fb: Array.from(api.fb).join("") });
}
fs.closeSync(fd);
fs.writeFileSync(out + "/meta.json", JSON.stringify({ frames: frames.length, shots: res }));
