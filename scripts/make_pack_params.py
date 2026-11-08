"""Build editor/pack-params.js from zoom-ms-zdl-effects-pack's src/custom/*/manifest_pedal.json.

Usage: py scripts/make_pack_params.py [path to zoom-ms-zdl-effects-pack]
Default path: the sibling folder ../zoom-ms-zdl-effects-pack.
"""
import glob
import json
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
pack = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, '..', '..', 'zoom-ms-zdl-effects-pack')


def key(gid, fxid):
    """g200kg's id form (editor/patch.js effectKey) of effect id gid << 24 | fxid, as the patch stores it."""
    w = (gid << 24 | fxid) << 1            # bit 0 is the on bit
    b = [w >> 8 * i & 255 for i in range(4)]
    return (b[0] & 0x80) << 23 | (b[0] & 0x7e) << 16 | (b[1] & 7) << 8 | (b[3] & 0x1f)


out = {}
for f in sorted(glob.glob(os.path.join(pack, 'src', 'custom', '*', 'manifest_pedal.json'))):
    m = json.load(open(f, encoding='utf-8'))
    out[key(m['gid'], m['fxid'])] = {'n': m['effect_name'], 'p': [[p['name'], p['max'], p['default']] for p in m['params']]}
if not out:
    sys.exit('no manifests under ' + pack)

js = ('// zoom-ms-zdl-effects-pack effects: name and parameters [name, max, default] by g200kg key (effectKey in patch.js).\n'
      '// Built by scripts/make_pack_params.py from the pack\'s manifest_pedal.json files: do not edit.\n'
      'var PACK_EFFECTS=' + json.dumps(out, separators=(',', ':')) + ';\n')
open(os.path.join(here, '..', 'editor', 'pack-params.js'), 'w', encoding='utf-8', newline='\n').write(js)
print(len(out), 'pack effects')
