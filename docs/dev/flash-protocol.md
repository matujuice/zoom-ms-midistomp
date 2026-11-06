# Zoom updater flash protocol (MS-70CDR, USB MIDI)

Captured 2026-11-06 on Luca's MS-70CDR with USBPcap (`scripts/flash_capture.py`) while the
MIDISTOMP V2.0.1 updater (plus `identity-tag`) flashed it. Same Zoom updater code as stock;
only the steps we skip (bootloader, file system) are missing from the capture. All 358 data
chunks were checked against the updater's own bytes.

## Messages

All SysEx, host -> pedal on EP 03 OUT, replies on EP 04 IN. `61` is the model byte from the
identity reply.

| Step | Host sends | Pedal replies |
|------|------------|---------------|
| Identity | `F0 7E 00 06 01 F7` | `F0 7E 00 06 02 52 61 00 00 00 v1 v2 v3 v4 F7` |
| Start | `F0 52 00 61 01 F7` | `F0 52 00 61 00 00 F7` |
| Erase | `F0 52 00 61 0A <addr:5> <len:5> F7` | ack (as above) |
| Write | `F0 52 00 61 02 <addr:5> <len:2> <data> <crc:5> F7` | ack |
| Finish | `F0 52 00 61 04 F7` | ack |

- Numbers (`addr`, `len`, `crc`) are 7-bit little-endian: `value = b0 | b1<<7 | b2<<14 ...`.
  Example: erase `00 60 3B 00 00` / `00 20 00 00 00` = 0x0EF000 +0x1000.
- Write `len` is `00 10` = 0x800: every chunk is 2048 bytes, address +0x800 each time.
- `data` is the 2048 bytes packed 7-in-8: each group of 8 bytes starts with a byte holding
  the top bits of the next 7 bytes, first byte's bit in bit 6, last one's in bit 0. 2048 bytes
  -> 2341 bytes (the last group has 4 data bytes).
- `crc` = CRC-32 of the 2048 unpacked bytes (zlib `crc32`) XOR 0xFFFFFFFF, i.e. CRC-32 without
  its final inversion. Matched on all 358 chunks.
- Message length on the wire: 2359 bytes per write.
- In update mode the identity reply comes from the bootloader: version `1.10`. The OS answers
  `2.10` (stock) or `M201` with `patches/identity-tag.yaml`. A flasher can use this to tell
  update mode from normal mode.

## Order and timing (this capture)

    identity -> "1.10"            t = 0
    01 start                      ack after 1 ms
    0A erase 0x0EF000 +0x1000     ack after 26 ms     (OS trailer)
    0A erase 0x3FD000 +0x3000     ack after 61 ms     (BIN/133: logo + model byte)
    02 x6  0x3FD000..0x3FF800     ~12-20 ms per chunk
    0A erase 0x040000 +0xB0000    ack after 2.86 s    (main OS)
    02 x352 0x040000..0x0EF800    ~12-17 ms per chunk
    04 finish                     ack at once

The host waits for each ack before the next message (one message in flight). The whole flash
takes about 9 s. No reboot command follows `04`; the user restarts the pedal. The capture has
no failure case (what a bad CRC or a dropped chunk returns): not tested.

Raw captures (`*.pcap`) hold Zoom's firmware: keep them local. The `flash-log.txt` the script
writes keeps only the 12-byte headers, lengths and hashes.
