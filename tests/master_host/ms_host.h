#pragma once
/* Host stand-ins for asm/master/master.c (compiled with -DMS_HOST): the OS, the buffers and the C6000 intrinsics. */
#include <math.h>
#include <stdint.h>
#include <string.h>

#define RING_M_N 4096
#define RING_S_N 2048
static unsigned host_lcd[256];
static float host_fft[1024], host_sin[257], host_bars[252], host_f[16], host_glim = 1.0f, host_acc[16], host_snap[16], host_pmg[3] = { 1, 0, 1 };
static short host_rm[4096], host_rs[2048];
static unsigned short host_hist[1408];
static long long host_st[256];
static int host_on, host_mode = 11, host_screen = 11, host_patch, host_posts, host_scr_calls;
static unsigned char host_entry = 5;
static unsigned host_zt[8];
#define MS_ZT host_zt

#define LCD0 (host_lcd)
#define LCD_DIRTY(f) ((void)0)
#define EVENT_POST(a, b) (host_posts++)
#define SET_SCREEN(a, b) (host_scr_calls++)
#define MAILBOX 0
#define MS_ON host_on
#define MS_FFT host_fft
#define MS_SIN host_sin
#define MS_RING_M host_rm
#define MS_RING_S host_rs
#define MS_HIST host_hist
#define MS_ST ((St *)host_st)
#define MS_BARS host_bars
static unsigned host_ink[128];
#define MS_INK host_ink
#define MS_F ((const volatile float *)host_f)
#define MS_GLIM (*(const volatile float *)&host_glim)
#define MS_ACC ((const volatile float *)host_acc)
#define MS_SNAP ((const volatile float *)host_snap)
#define MS_PMG ((const volatile float *)host_pmg)
#define MS_MODE host_mode
#define MS_SCREEN host_screen
#define MS_CUR_PATCH host_patch
#define MS_MENU_ENTRY host_entry

static int F2I(float x) { int i; memcpy(&i, &x, 4); return i; }
static float I2F(int i) { float x; memcpy(&x, &i, 4); return x; }
/* the DSP's reciprocal estimates are good to about 8 bits: truncate so the Newton steps are really tested */
static float _rcpsp(float x) { return I2F(F2I(1.0f / x) & ~0x7FFF); }
static float _rsqrsp(float x) { return I2F(F2I(1.0f / sqrtf(x)) & ~0x7FFF); }
static int _spint(float x) { return (int)nearbyintf(x); }
static int _sat16(int a) { return a > 32767 ? 32767 : a < -32768 ? -32768 : a; }
static int _spack2(int a, int b) { return (int)(((unsigned)_sat16(a) << 16) | ((unsigned)_sat16(b) & 0xFFFFu)); }
static uint64_t host_d8(const void *p) { uint64_t v; memcpy(&v, p, 8); return v; }
#define _amemd8_const(p) host_d8(p)
#define _lo(x) ((int)(unsigned)(x))
#define _hi(x) ((int)(unsigned)((x) >> 32))
#define _amem4(p) (*(unsigned *)(p))
#define _packh2(a, b) (((unsigned)(a) & 0xFFFF0000u) | ((unsigned)(b) >> 16))
#define _pack2(a, b) (((unsigned)(a) << 16) | ((unsigned)(b) & 0xFFFFu))
#define MS_D8 uint64_t
#define _itof I2F
