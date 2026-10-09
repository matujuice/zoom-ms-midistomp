# Builds the MIDISTOMP V1.0 logo from the stock MULTISTOMP MS-50G bitmap (BIN/133 pages 0-7).
# Usage: python3 scripts/midistomp_logo.py 133_data_133.bin preview.png logo.bin
# (133_data_133.bin from `zoomms updater-parts <stock updater> --out DIR`;
# logo.bin = the 1024 bytes in patches/boot-logo.yaml)
import sys
from PIL import Image
d=open(sys.argv[1],'rb').read()
W,H=128,64
src=[[d[(y//8)*W+x]>>(y%8)&1 for x in range(W)] for y in range(H)]
out=[[0]*W for _ in range(H)]
def blit(x0,x1,y0,y1,dx):  # copy stock columns x0..x1, rows y0..y1, shifted by dx
    for y in range(y0,y1+1):
        for x in range(x0,x1+1):
            if src[y][x]: out[y][x+dx]=1
def draw(rows,x,y):
    for j,r in enumerate(rows):
        for i,c in enumerate(r):
            if c=='#': out[y+j][x+i]=1
S=-5  # whole logo shift to stay centred
# top line: M from stock, then I D I, then the stock S...TOMP block
blit(5,19,6,14,15-5+S)          # M at 15
blit(51,54,6,14,31-51+S)        # I at 31
draw(["##########...","###########..","###......###.","###.......###","###.......###","###.......###","###......###.","###########..","##########..."],36+S,6)  # D
blit(51,54,6,14,S)              # I at 51 (stock position)
blit(55,127,6,17,S)             # S, bar, TOMP
for y in (16,17):               # S bottom bar: start under the new M
    for x in range(72+S): out[y][x]=0  # only the bar; TOMP's bottom rows stay
    for x in range(15+S, (72 if y==16 else 71)+S): out[y][x]=1
# bottom line: M O D (M and O are the stock "M" and "0" of MS-50G), centred;
# the OS prints the version under it
x=30
blit(11,38,20,40,x-11); x+=28+3   # stock "M" is columns 11-38
blit(80,96,20,40,x-80); x+=17+3   # stock "0" is columns 80-96
for y in range(21,41):            # D: straight left stroke, right half of the "0"
    for i in range(17):
        if i<6 or i>=8 and src[y][80+i] or i<10 and (y<=24 or y>=37): out[y][x+i]=1
img=Image.new('L',(W,H),20)
for y in range(H):
    for x in range(W):
        if out[y][x]: img.putpixel((x,y),230)
stock=Image.new('L',(W,H),20)
for y in range(H):
    for x in range(W):
        if src[y][x]: stock.putpixel((x,y),230)
sc=4; pad=12
sheet=Image.new('L',(W*sc+2*pad,2*(48*sc)+3*pad),200)
sheet.paste(stock.crop((0,0,W,48)).resize((W*sc,48*sc),Image.NEAREST),(pad,pad))
sheet.paste(img.crop((0,0,W,48)).resize((W*sc,48*sc),Image.NEAREST),(pad,2*pad+48*sc))
sheet.save(sys.argv[2])
# page-format bytes for the build thread
b=bytearray(W*8)
for y in range(H):
    for x in range(W):
        if out[y][x]: b[(y//8)*W+x]|=1<<(y%8)
open(sys.argv[3],'wb').write(b)
