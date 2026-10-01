/*
 * DUG OUT  -  a GameTank game
 *
 * Doug tunnels through the strata, pumps up the critters underground and
 * drops boulders on them.  Grid logic runs on 8x8 cells with pixel-smooth
 * movement; everything is drawn through the blitter draw queue.
 */
#include "gt/gametank.h"
#include "gt/input.h"
#include "gt/gfx/draw_queue.h"
#include "gt/gfx/sprites.h"
#include "gt/gfx/draw_direct.h"
#include "gt/audio/music.h"
#include "gt/feature/persist/persist.h"
#include "gen/assets/spr.h"
#include "gen/assets/bg.h"
#include "gen/assets/end.h"
#include "gen/assets/over.h"
#include "gen/assets/spr2.h"
#include "gen/assets/audio.h"
#include "gen_art.h"
#include "gt/banking.h"
#include "gen/bank_nums.h"

/* All game code lives in the banked PROG0 segment; only main() below stays in
 * the fixed bank (it switches PROG0 in and never returns). */
#pragma code-name (push, "PROG0")

/* ------------------------------------------------------------ constants -- */
#define COLS 14
#define ROWS 13
#define FX 8                /* field origin on screen */
#define FY 16
#define MAXE 6
#define MAXR 5
#define INNINGS 9           /* clear this many innings to win */

enum { ST_TITLE, ST_READY, ST_PLAY, ST_DYING, ST_CLEAR, ST_OVER, ST_PAUSE, ST_INTRO, ST_WIN, ST_ATTRACT };
enum { ES_NONE, ES_WALK, ES_GHOST, ES_INFL, ES_POP, ES_SQUASH, ES_FLAME };
enum { RS_STILL, RS_WOBBLE, RS_FALL, RS_CRUMBLE };
enum { DIR_R, DIR_L, DIR_U, DIR_D };

#define SFX_CH 3
/* sound effects share one FM channel; higher priority wins */
#define SFXP(id, pri) play_sound_effect(id, SFX_CH | SFX_PRIORITY(pri))
#define SFX(id) SFXP(id, 0)

static const signed char DX[4] = { 1, -1, 0, 0 };
#define WINDUP 10           /* frames a Heater stands still before the fire comes out */
#define FLAME_END 30
/* one fireball circles every Heater: offsets of an 8x8 sprite around its owner */
static const signed char ORB_X[8] = { 0, 6, 9, 6, 0, -6, -9, -6 };
static const signed char ORB_Y[8] = { -9, -6, 0, 6, 9, 6, 0, -6 };
#define ORB_K(n) ((unsigned char)(((frame_ct >> 2) + ((n) << 2)) & 7))
static const signed char DY[4] = { 0, 0, -1, 1 };
static const unsigned char LEADX[4] = { 8, 0, 4, 4 };
static const unsigned char LEADY[4] = { 4, 4, 0, 8 };

/* -------------------------------------------------------------- globals -- */
SpriteSlot slot_bg, slot_spr, slot_spr2 = 0xFF, slot_end = 0xFF, slot_over = 0xFF, slot_pri = 0xFF;   /* slot_pri: untouched copy of the dirt page */
unsigned int scene_t, idle_t;
unsigned char icur;                     /* which 'new enemy' intro is showing (index into the tables) */                 /* frames spent on the win / game over screens */
unsigned int hi_saved, hi_at_start;
unsigned char new_best;
unsigned char sbuf[5];
unsigned char save_peek(unsigned int off);   /* fixed-bank helper, defined at the end */

/* every vsync, counted by the NMI handler in shared audio RAM so none are lost while the draw queue's RAM bank is mapped */
#define vsync_raw (*(volatile unsigned char*)0x3210)

/* Code banks: PROG0 = gameplay, PROG1 = scenes. Calls between them go through bank_call (fixed bank),
 * which the compiler inserts for every function declared inside a wrapped-call block. */
void bank_call(void);
#pragma wrapped-call (push, bank_call, BANK_PROG1)
static void title_scene(void);
static void over_scene(void);
static void win_scene(void);
static void attract_scene(void);
static void intro_scene(void);
static unsigned char intro_for_level(unsigned char lv);
#pragma wrapped-call (pop)
#pragma wrapped-call (push, bank_call, BANK_PROG2)       /* PROG2 = the enemies: behaviour, contact and drawing */
static void enemies_update_all(void);
static unsigned char enemies_touch_player(void);
static void enemies_draw_all(void);
#pragma wrapped-call (pop)
#pragma wrapped-call (push, bank_call, BANK_PROG0)
static void draw_field(void);
static void need_page(SpriteSlot* slot, const SpritePage* page);
#pragma wrapped-call (pop)

/* 0 = tunnel, 1 = dirt, 2 = boulder cell.  16-wide rows so index = r<<4|c.
 * Columns 14/15 and row 13 are permanent solid padding. */
unsigned char map[(ROWS + 1) * 16];
unsigned char paid[(ROWS + 1) * 16];         /* tens of points Doug was paid for digging each cell (0 = none), so the Groundskeeper takes back exactly that */
#define M(c, r) map[(((unsigned char)(r)) << 4) | ((unsigned char)(c))]

unsigned char state, state_timer, frame_ct;
unsigned char level, lives;
unsigned int score_h, hi_h, next_life_h;   /* score in hundreds */
unsigned char score_t, hi_t;               /* the tens digit of the score and of the best score */
char score_str[9], hi_str[9];
unsigned char score_dirty;
unsigned int lfsr = 0xACE1u;
unsigned int run_seed = 0x1357u;      /* new every game: the cave layouts differ from run to run */

/* player */
unsigned char px, py, pdir, panim, pmoving;
unsigned char ball_on, ball_x, ball_y, ball_dir, ball_dist, throw_cd, ball_dirt;   /* Doug's thrown baseball */

/* enemies (structure of arrays: cheaper on a 6502) */
unsigned char e_state[MAXE], e_type[MAXE], e_x[MAXE], e_y[MAXE], e_dir[MAXE], e_face[MAXE];
unsigned char e_infl[MAXE], e_timer[MAXE], e_acc[MAXE], e_homec[MAXE], e_homer[MAXE], e_flen[MAXE];
unsigned char e_flee[MAXE], e_pts[MAXE];      /* running for the top (the last two enemies), and what it would cost if they get there (hundreds) */
unsigned char e_prevc[MAXE], e_prevr[MAXE];

/* headstones of struck-out Vumpires; a living Vumpire that reaches one raises it again */
#define MAXC 3
unsigned char c_on[MAXC], c_slot[MAXC], c_x[MAXC], c_y[MAXC];
unsigned char enemies_left, espeed;

/* boulders */
unsigned char r_on[MAXR], r_c[MAXR], r_r[MAXR], r_y[MAXR], r_state[MAXR], r_timer[MAXR], r_kills[MAXR];

/* score popups */
#define MAXP 4
unsigned char pop_t[MAXP], pop_x[MAXP], pop_y[MAXP];
unsigned int pop_v[MAXP];
unsigned int beat_acc, song_t;                /* where the music's beat is (see beat_tick) */
unsigned char beat_on, bob;                   /* bob: the player and the walkers nod their heads while it is 1 */
unsigned char gold_on, gold_c, gold_r;      /* a gold bar lying in one enemy cave: 500 points */

static void add_popup(unsigned char x, unsigned char y, unsigned int v)
{
    unsigned char i, best = 0, oldest = 255;
    for (i = 0; i < MAXP; ++i)
        if (pop_t[i] == 0) { best = i; break; }
        else if (pop_t[i] < oldest) { oldest = pop_t[i]; best = i; }
    pop_x[best] = x; pop_y[best] = y; pop_v[best] = v; pop_t[best] = 28;
}

static const unsigned int rock_pts[6] = { 10, 25, 40, 60, 80, 100 };   /* hundreds */

/* ---------------------------------------------------------------- utils -- */
#pragma code-name (push, "CODE")     /* used from every bank */
static unsigned char rng(void)
{
    unsigned char i;
    for (i = 0; i < 8; ++i) {
        unsigned char lsb = lfsr & 1;
        lfsr >>= 1;
        if (lsb) lfsr ^= 0xB400u;
    }
    return (unsigned char)lfsr;
}

static unsigned char absdiff(unsigned char a, unsigned char b)
{
    return a > b ? a - b : b - a;
}
#pragma code-name (pop)

static void fmt_score(char* s, unsigned int v, unsigned char t)
{
    /* v is hundreds, t the tens digit; output 7 digits: 5 digits, the tens digit and a 0 */
    unsigned char i;
    for (i = 5; i > 0; --i) {
        s[i - 1] = '0' + (v % 10);
        v /= 10;
    }
    s[5] = '0' + t; s[6] = '0'; s[7] = 0;
}

static void add_score(unsigned int h)
{
    score_h += h;
    if (score_h > hi_h || (score_h == hi_h && score_t > hi_t)) { hi_h = score_h; hi_t = score_t; }
    if (score_h >= next_life_h) {
        next_life_h += 100;
        if (lives < 5) ++lives;
        SFXP(ASSET__audio__oneup_sfx_ID, 2);
    }
    score_dirty = 1;
}

/* tunnelling pays in tens of points */
static void add_tens(unsigned char t)
{
    score_t += t;
    if (score_t >= 10) { score_t -= 10; add_score(1); }
    else add_score(0);
}

/* ------------------------------------------------ live field image (sprite RAM)
 * The dirt/tunnel picture is baked into a page of sprite RAM.  Digging patches
 * 8x8 tiles in that page (CPU writes), so drawing the whole field is one blit. */
static unsigned char dirty_flag[(ROWS + 1) * 16];
static unsigned char dirty_list[40], dirty_n, refresh_all;

#pragma code-name (push, "CODE")
static void mark_dirty(signed char c, signed char r)
{
    unsigned char idx;
    if (c < 0 || c >= COLS || r < 1 || r >= ROWS) return;
    idx = (r << 4) | c;
    if (dirty_flag[idx]) return;
    dirty_flag[idx] = 1;
    if (dirty_n < 40) dirty_list[dirty_n++] = idx; else refresh_all = 1;
}

static void mark_around(signed char c, signed char r)
{
    mark_dirty(c, r); mark_dirty(c - 1, r); mark_dirty(c + 1, r);
    mark_dirty(c, r - 1); mark_dirty(c, r + 1);
}

/* cells the Groundskeeper has refilled: copy the original dirt pixels back from the pristine page */
unsigned char rest_list[16], rest_n, rbuf[64];

static void mark_restore(unsigned char c, unsigned char r)
{
    if (rest_n < 16) rest_list[rest_n++] = (r << 4) | c;
}
#pragma code-name (pop)

static void restore_cell(unsigned char idx)
{
    unsigned char c = idx & 15, r = idx >> 4, i, j;
    unsigned char* p;
    unsigned int off = ((unsigned)r << 10) + BG_FIELD_OX + ((unsigned)c << 3);
    direct_prepare_sprite_ram_array_mode(slot_pri);
    p = rbuf;
    for (j = 0; j < 8; ++j) {
        for (i = 0; i < 8; ++i) *p++ = vram[off + ((unsigned)j << 7) + i];
    }
    direct_prepare_sprite_ram_array_mode(slot_bg);
    p = rbuf;
    for (j = 0; j < 8; ++j) {
        for (i = 0; i < 8; ++i) vram[off + ((unsigned)j << 7) + i] = *p++;
    }
}

static void patch_cell(unsigned char idx)
{
    unsigned char c = idx & 15, r = idx >> 4, m = 0, i, j;
    const unsigned char* src;
    unsigned char* dst;
    if (M(c, r) != 0) return;
    if (M(c, r - 1)) m |= 1;
    if (M(c + 1, r)) m |= 2;
    if (M(c, r + 1)) m |= 4;
    if (c == 0 || M(c - 1, r)) m |= 8;
    src = tunnel_px[m];
    dst = vram + ((unsigned)r << 10) + BG_FIELD_OX + ((unsigned)c << 3);
    for (j = 0; j < 8; ++j) {
        for (i = 0; i < 8; ++i) dst[i] = src[i];
        src += 8; dst += 128;
    }
}

static void field_flush(void)
{
    unsigned char i, r, c;
    if (!refresh_all && !dirty_n && !rest_n) return;
    if (rest_n && !refresh_all) {
        for (i = 0; i < rest_n; ++i) restore_cell(rest_list[i]);
    }
    rest_n = 0;
    direct_prepare_sprite_ram_array_mode(slot_bg);
    if (refresh_all) {
        for (r = 1; r < ROWS; ++r)
            for (c = 0; c < COLS; ++c)
                patch_cell((r << 4) | c);
        refresh_all = 0;
        for (i = 0; i < (ROWS + 1) * 16; ++i) dirty_flag[i] = 0;
        dirty_n = 0;
        return;
    }
    for (i = 0; i < dirty_n; ++i) {
        patch_cell(dirty_list[i]);
        dirty_flag[dirty_list[i]] = 0;
    }
    dirty_n = 0;
}

/* fresh dirt page + every existing tunnel repainted on the next flush */
/* loading sprite RAM briefly drops the video page bit, so put a clean blank on both pages first */
static void blank_screen(void)
{
    unsigned char k;
    for (k = 0; k < 2; ++k) {
        queue_draw_box(0, 0, 127, 127, COL_INK);
        await_draw_queue();
        await_vsync(1);
        flip_pages();
    }
    await_draw_queue();
}

/* big art pages are loaded the first time they're needed, which keeps the boot quick */
static void need_page(SpriteSlot* slot, const SpritePage* page)
{
    if (*slot != 0xFF) return;
    blank_screen();
    *slot = allocate_sprite(page);
}

static void field_reload(void)
{
    unsigned char i;
    blank_screen();
    load_spritesheet(ASSET__bg__bg_bmp, slot_bg);
    for (i = 0; i < (ROWS + 1) * 16; ++i) dirty_flag[i] = 0;
    dirty_n = 0;
    refresh_all = 1;
}

/* ---------------------------------------------------------- draw helpers -- */
#define BLIT(sl, X, Y, W, H, GX, GY) \
    do { rect.x = (X); rect.y = (Y); rect.w = (W); rect.h = (H); \
         rect.gx = (GX); rect.gy = (GY); rect.b = (sl); queue_draw_sprite_rect(); } while (0)
/* a sprite whose top HD rows (the head) drop a pixel on the beat: the body first, then the head over it */
#define BLIT_BOB(sl, X, Y, W, H, GX, GY, HD) \
    do { if (bob) { BLIT(sl, X, (Y) + (HD), W, (H) - (HD), GX, (GY) + (HD)); BLIT(sl, X, (Y) + 1, W, HD, GX, GY); } \
         else BLIT(sl, X, Y, W, H, GX, GY); } while (0)

#pragma code-name (push, "CODE")     /* shared by every bank, so it lives in the fixed one */
/* The beat. The theme's snare hits fall on a grid 52.15 frames apart (26.075 game ticks), the first 26.9 frames into the song, and the song
 * (8371 frames) loops. beat_acc is how far into a beat it is, in 1/256 ticks; bob is set for the first part of each beat. */
#define BEAT_FP    6675u
#define BEAT_START (6675u - 3443u)
#define BEAT_WIN   1280u
#define SONG_LEN   8371u
static void beat_start(void) { beat_acc = BEAT_START; song_t = 0; beat_on = 1; }

static void beat_tick(void)
{
    if (beat_on) {
        beat_acc += 256; song_t += 2;
        if (beat_acc >= BEAT_FP) beat_acc -= BEAT_FP;
        if (song_t >= SONG_LEN) { song_t -= SONG_LEN; beat_acc = BEAT_START + song_t * 128u; }      /* the song starts again, and so does the grid */
    }
    bob = (beat_on && (state == ST_PLAY || state == ST_PAUSE) && beat_acc < BEAT_WIN);
}

static void text(unsigned char x, unsigned char y, const char* s, unsigned char set)
{
    unsigned char ch, idx, cell, gx, gy;
    while ((ch = (unsigned char)*s++) != 0) {
        if (ch >= 'A' && ch <= 'Z') idx = ch - 'A';
        else if (ch >= '0' && ch <= '9') idx = 26 + ch - '0';
        else if (ch == '-') idx = 36;
        else if (ch == ':') idx = 37;
        else if (ch == '!') idx = 38;
        else if (ch == '.') idx = 39;
        else if (ch == '\'') idx = 40;
        else { x += 4; continue; }
        cell = set * 41 + idx;
        gx = SP_FONT_X + ((cell & 31) << 2);
        gy = SP_FONT_Y + (cell >> 5) * 6;
        BLIT(slot_spr, x, y, 4, 6, gx, gy);
        x += 4;
    }
}

static unsigned char text_w(const char* s)
{
    unsigned char n = 0;
    while (*s++) ++n;
    return n << 2;
}

static void text_center(unsigned char y, const char* s, unsigned char set)
{
    text(64 - (text_w(s) >> 1), y, s, set);
}
#pragma code-name (pop)

static void banner(const char* a, const char* b)
{
    unsigned char w = text_w(a);
    if (text_w(b) > w) w = text_w(b);
    w += 12;
    queue_draw_box(64 - (w >> 1), FY + 38, w, 22, COL_INK);
    queue_draw_box(64 - (w >> 1) + 1, FY + 39, w - 2, 1, COL_RIM);
    queue_draw_box(64 - (w >> 1) + 1, FY + 58, w - 2, 1, COL_RIM);
    text_center(FY + 43, a, 1);
    if (b) text_center(FY + 51, b, 0);
}

/* ---------------------------------------------------------------- level -- */
static void clear_map(void)
{
    unsigned char r, c;
    for (r = 0; r < ROWS + 1; ++r)
        for (c = 0; c < 16; ++c)
            { M(c, r) = (r == 0 && c < COLS) ? 0 : 1; paid[(r << 4) | c] = 0; }
}

static void carve(unsigned char c, unsigned char r, unsigned char w, unsigned char h)
{
    unsigned char i, j;
    for (j = 0; j < h; ++j)
        for (i = 0; i < w; ++i)
            M(c + i, r + j) = 0;
}

static void build_title_map(void)
{
    gold_on = 0;
    clear_map();
    carve(0, 9, 14, 1);
    carve(3, 3, 1, 7);
    carve(10, 5, 1, 5);
    carve(3, 5, 8, 1);
    carve(6, 11, 5, 1);
    carve(6, 9, 1, 3);
    field_reload();
}

static void reset_player(void)
{
    px = 6 << 3; py = 2 << 3; pdir = DIR_D; panim = 0; pmoving = 0;
    ball_on = 0; throw_cd = 0;
    carve(6, 1, 1, 2);
}

static void reset_enemies_home(void)
{
    unsigned char i;
    for (i = 0; i < MAXE; ++i) {
        if (e_state[i] == ES_NONE) continue;
        e_state[i] = (e_type[i] == 2) ? ES_GHOST : ES_WALK; e_flee[i] = 0;
        e_x[i] = e_homec[i] << 3; e_y[i] = e_homer[i] << 3;
        e_dir[i] = DIR_R; e_face[i] = DIR_R; e_prevc[i] = 255; e_prevr[i] = 255;
        e_infl[i] = 0; e_timer[i] = 0; e_acc[i] = 0;
    }
}

static void build_level(void)
{
    unsigned char i, ne, nr, tries, c, r, w, c0;

    if (level >= 5) need_page(&slot_pri, &ASSET__bg__bg_bmp_load_list);            /* pristine dirt for the Groundskeeper */
    if (level >= INNINGS) need_page(&slot_spr2, &ASSET__spr2__spr2_bmp_load_list); /* the Mascot's art */
    clear_map();
    lfsr = run_seed + level * 977u;

    ne = 2 + level;
    if (ne > MAXE) ne = MAXE;
    if (level >= INNINGS) ne = 1;               /* the final inning is the Mascot, alone */

    for (i = 0; i < MAXE; ++i) { e_state[i] = ES_NONE; e_flee[i] = 0; }
    for (i = 0; i < MAXC; ++i) c_on[i] = 0;
    for (i = 0; i < ne; ++i) {
        /* each pocket gets its own row, width, column and sometimes a shaft: nothing sits in a fixed slot */
        for (tries = 0; tries < 30; ++tries) {
            r = 3 + rng() % 9;
            w = 2 + rng() % 4;
            if (level >= 2 && (i & 1) && w < 4) w = 4;                  /* a Heater's pocket is at least 4 wide, or you could not get to it */
            c0 = rng() % (COLS - w + 1);
            if (c0 <= 6 && c0 + w > 6 && r < 7) continue;               /* not under Doug's shaft */
            for (c = 0; c < i; ++c)                                     /* keep pockets a row apart if we can */
                if (absdiff(e_homer[c], r) < 2) break;
            if (c == i) break;
        }
        carve(c0, r, w, 1);
        if (r < 11 && (c0 & 1)) carve(c0 + (w >> 1), r, 1, 2);            /* a shaft down */
        e_state[i] = ES_WALK;
        e_type[i] = (level >= 2 && (i & 1)) ? 1 : 0;
        e_homec[i] = c0 + (w >> 1); e_homer[i] = r;
    }
    if (level >= 3) e_type[ne - 1] = 2;          /* a baseball bat joins from inning 3 */
    if (level >= 5 && ne >= 5) e_type[ne - 2] = 3; /* a Groundskeeper from inning 5 */
    if (level >= INNINGS) e_type[0] = 4;
    enemies_left = ne;                          /* every enemy, the Groundskeeper included, must be struck out */

    /* boulders */
    for (i = 0; i < MAXR; ++i) r_on[i] = 0;
    nr = 3 + (level > 2);
    if (nr > MAXR) nr = MAXR;
    for (i = 0; i < nr; ++i) {
        for (tries = 0; tries < 40; ++tries) {
            c = 1 + rng() % 12;
            r = 2 + rng() % 9;
            if (M(c, r) != 1 || M(c, r + 1) != 1) continue;
            if (M(c - 1, r) == 0 || M(c + 1, r) == 0 || M(c, r - 1) == 0) continue;
            if (c == 6 && r < 5) continue;
            r_on[i] = 1; r_c[i] = c; r_r[i] = r; r_y[i] = r << 3;
            r_state[i] = RS_STILL; r_timer[i] = 0; r_kills[i] = 0;
            M(c, r) = 2;
            break;
        }
    }
    i = rng() % ne;                             /* a gold bar lies in one of the enemy caves, near its middle */
    c = e_homec[i] + rng() % 3 - 1; r = e_homer[i];
    if (M(c, r) != 0) c = e_homec[i];
    gold_c = c; gold_r = r; gold_on = 1;
    reset_player();
    reset_enemies_home();
    field_reload();
    espeed = 8 + level;
    if (espeed > 13) espeed = 13;
}

/* --------------------------------------------------------------- player -- */
static unsigned char can_move(unsigned char x, unsigned char y, unsigned char d)
{
    switch (d) {
    case DIR_R:
        if (x >= 104) return 0;
        if (!(x & 7) && M((x >> 3) + 1, y >> 3) == 2) return 0;
        return 1;
    case DIR_L:
        if (x == 0) return 0;
        if (!(x & 7) && M((x >> 3) - 1, y >> 3) == 2) return 0;
        return 1;
    case DIR_U:
        if (y == 0) return 0;
        if (!(y & 7) && M(x >> 3, (y >> 3) - 1) == 2) return 0;
        return 1;
    default:
        if (y >= 96) return 0;
        if (!(y & 7) && M(x >> 3, (y >> 3) + 1) == 2) return 0;
        return 1;
    }
}

static void enemy_pop(unsigned char i)
{
    e_state[i] = ES_POP;
    e_timer[i] = 0;
    SFXP(ASSET__audio__pop_sfx_ID, 3);
}

static unsigned char vumpires_alive(void)
{
    unsigned char k;
    for (k = 0; k < MAXE; ++k)
        if (e_type[k] == 0 && (e_state[k] == ES_WALK || e_state[k] == ES_INFL || e_state[k] == ES_FLAME)) return 1;
    return 0;
}

static void add_corpse(unsigned char k)
{
    unsigned char c;
    for (c = 0; c < MAXC; ++c)
        if (!c_on[c]) { c_on[c] = 1; c_slot[c] = k; c_x[c] = e_x[k]; c_y[c] = e_y[k]; return; }
}

/* a thrown ball connects: one strike; three strikes (six for the Mascot) and the enemy is out */
static void strike(unsigned char k)
{
    unsigned char need = (e_type[k] == 4) ? 6 : 3;
    unsigned char row = e_y[k] >> 3;
    unsigned int pts;
    if (e_type[k] != 4) e_state[k] = ES_INFL;   /* everyone but Mad Scott is stunned by a hit */
    e_timer[k] = 0;
    ++e_infl[k];
    if (e_infl[k] >= need) {
        pts = (e_type[k] == 4) ? 50 : row <= 3 ? 2 : row <= 6 ? 3 : row <= 9 ? 4 : 5;
        enemy_pop(k);
        add_score(pts);
        add_popup(e_x[k], e_y[k], pts);
        if (e_type[k] == 0) add_corpse(k);      /* Vumpires can be raised again; crushed ones can't */
        --enemies_left;
    } else {
        SFXP(e_infl[k] == 1 ? ASSET__audio__pump1_sfx_ID : ASSET__audio__pump2_sfx_ID, 1);
    }
}

/* the ball flies 4 px/frame. It keeps going through dirt, but once it has been in dirt it can only tag the
 * enemies that move through dirt (baseball bats, Groundskeeper, Mad Scott) - never a Vumpire sealed in a pocket */
static void ball_step(void)
{
    unsigned char s, k, over;
    for (s = 0; s < 2 && ball_on; ++s) {
        ball_x += DX[ball_dir] * 2; ball_y += DY[ball_dir] * 2;
        ball_dist += 2;
        over = (ball_dist > 40 || ball_x >= 112 || ball_y >= 104);
        if (over) { ball_on = 0; break; }
        if (M(ball_x >> 3, ball_y >> 3) != 0) ball_dirt = 1;
        for (k = 0; k < MAXE; ++k) {
            if (e_state[k] != ES_WALK && e_state[k] != ES_GHOST && e_state[k] != ES_FLAME && e_state[k] != ES_INFL) continue;
            if (ball_dirt && e_type[k] < 2) continue;
            if (absdiff(e_x[k] + 4, ball_x) < 6 && absdiff(e_y[k] + 4, ball_y) < 6) {
                strike(k);
                ball_on = 0;
                break;
            }
        }
        if (ball_on && ball_dirt) ball_on = 0;      /* the ball stops at dirt (after one last chance to hit a bat or the boss right there) */
    }
}

static void player_update(void)
{
    unsigned char want = 255, misal, d, moved = 0, c, r, slow, pay;
    int b = player1_buttons;

    if (pdir < 2) {
        if (b & INPUT_MASK_UP) want = DIR_U;
        else if (b & INPUT_MASK_DOWN) want = DIR_D;
        else if (b & INPUT_MASK_LEFT) want = DIR_L;
        else if (b & INPUT_MASK_RIGHT) want = DIR_R;
    } else {
        if (b & INPUT_MASK_LEFT) want = DIR_L;
        else if (b & INPUT_MASK_RIGHT) want = DIR_R;
        else if (b & INPUT_MASK_UP) want = DIR_U;
        else if (b & INPUT_MASK_DOWN) want = DIR_D;
    }

    if (want != 255) {
        if ((want >> 1) != (pdir >> 1)) {
            /* turning a corner: slide onto the grid first */
            misal = (want < 2) ? (py & 7) : (px & 7);
            if (misal) {
                if (want < 2) d = (misal <= 4) ? DIR_U : DIR_D;
                else          d = (misal <= 4) ? DIR_L : DIR_R;
                if (can_move(px, py, d)) {
                    px += DX[d]; py += DY[d];
                    moved = 1;
                }
                want = 255;
            } else {
                pdir = want;
            }
        } else {
            pdir = want;
        }
    }

    if (want != 255 && can_move(px, py, pdir)) {
        c = (px + LEADX[pdir]) >> 3;
        r = (py + LEADY[pdir]) >> 3;
        slow = (M(c, r) == 1);
        if (!slow || (frame_ct & 1)) {
            px += DX[pdir]; py += DY[pdir];
            moved = 1;
        }
    }

    pmoving = moved;
    if (moved) {
        ++panim;
        c = (px + 4) >> 3; r = (py + 4) >> 3;
        if (M(c, r) == 1) {
            M(c, r) = 0;
            pay = (r <= 3) ? 1 : (r <= 6) ? 2 : (r <= 9) ? 3 : 4;    /* 10, 20, 30, 40 points, by depth */
            paid[(r << 4) | c] = pay;
            add_tens(pay);
            mark_around(c, r);
            SFX(ASSET__audio__dig_sfx_ID);
        }
    }

    if (gold_on && ((px + 4) >> 3) == gold_c && ((py + 4) >> 3) == gold_r) {      /* the gold bar: enemies walk over it, Doug picks it up */
        gold_on = 0;
        add_score(5); add_popup(px, py, 5);
        SFXP(ASSET__audio__oneup_sfx_ID, 1);
    }

    /* --- throw a baseball ---------------------------------------------- */
    if (throw_cd) --throw_cd;
    if ((player1_new_buttons & INPUT_MASK_A) && !ball_on && !throw_cd) {
        ball_on = 1; ball_dir = pdir; ball_dist = 0; ball_dirt = 0;
        ball_x = px + 4; ball_y = py + 4;
        throw_cd = 4;
        SFXP(ASSET__audio__shoot_sfx_ID, 1);
    }
    if (ball_on) ball_step();
}

/* -------------------------------------------------------------- enemies -- */
/* (this section lives in its own bank, PROG2) */
#pragma code-name (push, "PROG2")

static unsigned char open_cell(signed char c, signed char r)
{
    if (c < 0 || c >= COLS || r < 0 || r >= ROWS) return 0;
    return M(c, r) == 0;
}

static void choose_dir(unsigned char i)
{
    signed char c = e_x[i] >> 3, r = e_y[i] >> 3;
    signed char tc = (px + 4) >> 3, tr = (py + 4) >> 3;
    unsigned char cur = e_dir[i], rev = cur ^ 1, d, best = 255, bd = rev, n = 0, dist, opt[4];
    signed char nc, nr, dc, dr;

    if (e_type[i] == 0 && rng() < 110) {          /* a Vumpire: go and raise a fallen friend */
        for (d = 0; d < MAXC; ++d)
            if (c_on[d]) { tc = (c_x[d] + 4) >> 3; tr = (c_y[d] + 4) >> 3; break; }
    }
    dist = rng();                                /* aim a few cells off Doug so the routes are not the same every time */
    tc += (dist & 7) - 3;
    tr += ((dist >> 3) & 7) - 3;
    for (d = 0; d < 4; ++d) {
        if (d == rev) continue;
        nc = c + DX[d]; nr = r + DY[d];
        if (!open_cell(nc, nr)) continue;
        opt[n++] = d;
        dc = nc - tc; dr = nr - tr;
        if (dc < 0) dc = -dc;
        if (dr < 0) dr = -dr;
        dist = dc + dr;
        if (dist < best) { best = dist; bd = d; }
    }
    if (n == 0) {
        /* dead end: turn around if we can, else stay put */
        nc = c + DX[rev]; nr = r + DY[rev];
        e_dir[i] = open_cell(nc, nr) ? rev : cur;
        return;
    }
    if (n > 1 && rng() < (e_type[i] ? 70 : 50)) bd = opt[rng() % n];      /* mostly they head straight for Doug */
    e_dir[i] = bd;
}

static unsigned char orb_hits_player(unsigned char i)
{
    unsigned char k;
    if (e_type[i] != 1) return 0;
    k = ORB_K(0);                                   /* the one fireball: its box is where it is drawn */
    return (absdiff((unsigned char)(e_x[i] + ORB_X[k]), px) < 5 && absdiff((unsigned char)(e_y[i] + ORB_Y[k]), py) < 5);
}


static unsigned char line_clear(unsigned char c, unsigned char r, unsigned char dir, unsigned char len)
{
    unsigned char k;
    signed char cc = c;
    for (k = 0; k < len; ++k) {
        cc += DX[dir];
        if (!open_cell(cc, r)) return k;
    }
    return len;
}

/* scratch for the two searches over the tunnels: the Groundskeeper's (which caves is it joined to) and the fleeing enemies' (the way to the top) */
static unsigned char fl_par[(ROWS + 1) << 4], fl_q[(ROWS + 1) << 4];

/* mark in fl_par every open cell that is joined to the start cell by open cells */
static void region_mark(unsigned char start)
{
    unsigned char head = 0, tail = 0, cur, d, nc, nr, n;
    for (n = 0; n < sizeof fl_par; ++n) fl_par[n] = 0;
    fl_q[tail++] = start; fl_par[start] = 1;
    while (head != tail) {
        cur = fl_q[head++];
        for (d = 0; d < 4; ++d) {
            nc = (cur & 15) + DX[d]; nr = (cur >> 4) + DY[d];
            if (!open_cell((signed char)nc, (signed char)nr)) continue;
            n = (nr << 4) | nc;
            if (fl_par[n]) continue;
            fl_par[n] = 1; fl_q[tail++] = n;
        }
    }
}

/* --- Groundskeeper ---------------------------------------------------------------------- */
static unsigned char gk_ok(signed char c, signed char r)
{
    if (c < 0 || c >= COLS || r < 0 || r >= ROWS) return 0;
    return M(c, r) != 2;                       /* walks through dirt, but not through home plates */
}

static void choose_dir_g(unsigned char i)
{
    signed char c = e_x[i] >> 3, r = e_y[i] >> 3;
    signed char tc = (px + 4) >> 3, tr = (py + 4) >> 3;
    unsigned char rev = e_dir[i] ^ 1, d, best = 255, bd = rev, n = 0, dist, opt[4], rr, cc, pass, any = 0;
    signed char nc, nr, dc, dr;

    if (e_type[i] == 3) {
        /* Groundskeeper: go straight (digging, see enemy_update) for the nearest open cell that is not joined to where it is, which is
         * a sealed cave, or failing that the nearest open cell. Never the surface. */
        unsigned char bestd = 255;
        region_mark((unsigned char)((r << 4) | c));
        for (pass = 0; pass < 2 && !any; ++pass)
        for (rr = 1; rr < ROWS; ++rr)
            for (cc = 0; cc < COLS; ++cc) {
                if (M(cc, rr) != 0 || (cc == c && rr == r)) continue;
                if (!pass && fl_par[(rr << 4) | cc]) continue;
                dc = cc - c; dr = rr - r;
                if (dc < 0) dc = -dc;
                if (dr < 0) dr = -dr;
                dist = dc + dr;
                if (dist < bestd) { bestd = dist; tc = cc; tr = rr; any = 1; }
            }
    }
    for (d = 0; d < 4; ++d) {
        if (d == rev) continue;
        nc = c + DX[d]; nr = r + DY[d];
        if (!gk_ok(nc, nr)) continue;
        opt[n++] = d;
        dc = nc - tc; dr = nr - tr;
        if (dc < 0) dc = -dc;
        if (dr < 0) dr = -dr;
        dist = dc + dr;
        if (dist < best) { best = dist; bd = d; }
    }
    if (n == 0) { e_dir[i] = rev; return; }
    if (e_type[i] == 4 && n > 1 && rng() < 24) bd = opt[rng() % n];
    e_dir[i] = bd;
}

/* rake the cell just left back into dirt (never with Doug or another enemy standing in it) */
static void sub_tens(unsigned char t)
{
    if (score_t >= t) score_t -= t;
    else if (score_h) { --score_h; score_t += 10 - t; }
    else score_t = 0;
    score_dirty = 1;
}

static void refill_cell(unsigned char c, unsigned char r, unsigned char self)
{
    unsigned char k;
    if (r == 0 || M(c, r) != 0) return;
    if (paid[(r << 4) | c] - 1u > 3u) return;                 /* it only takes back what Doug dug: never a cave, never a tunnel it dug itself */
    if (absdiff(px, c << 3) < 8 && absdiff(py, r << 3) < 8) return;
    for (k = 0; k < MAXE; ++k) {
        if (k == self || e_state[k] == ES_NONE || e_state[k] == ES_POP || e_state[k] == ES_SQUASH) continue;
        if (absdiff(e_x[k], c << 3) < 8 && absdiff(e_y[k], r << 3) < 8) return;
    }
    M(c, r) = 1;
    k = (r << 4) | c;
    if (paid[k]) { sub_tens(paid[k]); paid[k] = 0; }      /* the Groundskeeper takes back what the dig paid */
    mark_restore(c, r);
    mark_around(c, r);
}

/* an enemy made it off the top of the screen: Doug loses what it would have been worth */
static void enemy_escape(unsigned char i)
{
    if (score_h > e_pts[i]) score_h -= e_pts[i]; else { score_h = 0; score_t = 0; }
    score_dirty = 1;
    add_popup(e_x[i], 0, e_pts[i] | 0x8000);
    SFXP(ASSET__audio__thud_sfx_ID, 2);
    e_state[i] = ES_NONE;
    --enemies_left;
}

/* the way to the top along open tunnels (breadth first search from the enemy's cell to any cell of row 0).
 * Sets e_dir and returns 1, or returns 0 if there is no way: a sealed cave stays sealed. */
static unsigned char flee_dir(unsigned char i)
{
    unsigned char head = 0, tail = 0, cur, c, r, d, nc, nr, n, start, d0 = 0;
    for (n = 0; n < sizeof fl_par; ++n) fl_par[n] = 0;
    start = ((e_y[i] >> 3) << 4) | (e_x[i] >> 3);
    fl_q[tail++] = start; fl_par[start] = 5;
    while (head != tail) {
        cur = fl_q[head++]; c = cur & 15; r = cur >> 4;
        if (r == 0 && cur != start) {                       /* found the top: walk back to the first step */
            while (cur != start) {
                d = fl_par[cur] - 1; d0 = d;
                cur = (unsigned char)(((((signed char)(cur >> 4)) - DY[d]) << 4) | (((signed char)(cur & 15)) - DX[d]));
            }
            e_dir[i] = d0;
            return 1;
        }
        for (d = 0; d < 4; ++d) {
            nc = c + DX[d]; nr = r + DY[d];
            if (!open_cell((signed char)nc, (signed char)nr)) continue;
            n = (nr << 4) | nc;
            if (fl_par[n]) continue;
            fl_par[n] = d + 1;
            fl_q[tail++] = n;
        }
    }
    return 0;
}

static void enemy_update(unsigned char i)
{
    unsigned char st = e_state[i], x = e_x[i], y = e_y[i], d, c, r, tc, tr;

    if (enemies_left <= 2 && e_type[i] <= 2 && !e_flee[i] && (st == ES_WALK || st == ES_GHOST)) {
        /* only two left: they give up the chase and run for the top, along the tunnels if there is a way (bats fly straight up) */
        e_flee[i] = 1;
        r = y >> 3;
        e_pts[i] = (r <= 3) ? 2 : (r <= 6) ? 3 : (r <= 9) ? 4 : 5;      /* what a kill here would pay */
    }

    switch (st) {
    case ES_WALK:
        if (e_type[i] == 0 && !e_flee[i]) {
            /* standing over a fallen Vumpire starts the ritual */
            for (c = 0; c < MAXC; ++c)
                if (c_on[c] && e_state[c_slot[c]] == ES_NONE && absdiff(x, c_x[c]) < 6 && absdiff(y, c_y[c]) < 6) {
                    e_state[i] = ES_FLAME; e_timer[i] = 0; e_flen[i] = c;
                    SFXP(ASSET__audio__ready_sfx_ID, 2);
                    return;
                }
        }
        if (e_type[i] >= 3) {
            if (e_type[i] == 4) {
                /* Mad Scott never stops for a hit: he gets faster with every strike, and strikes wear off */
                if (e_infl[i] && ++e_timer[i] > 150) { e_timer[i] = 0; --e_infl[i]; }
                e_acc[i] += 9 + e_infl[i];
            } else {
                e_acc[i] += 14;                               /* the Groundskeeper is brisk */
            }
            if (e_acc[i] < 16) return;
            e_acc[i] -= 16;
            if (!((x | y) & 7)) {
                if (e_type[i] == 3) {
                    /* rake shut the cell behind and any open cell beside the path */
                    if (e_prevc[i] != 255) refill_cell(e_prevc[i], e_prevr[i], i);
                    for (c = 0; c < 4; ++c) {
                        if (c == e_dir[i]) continue;
                        tc = (x >> 3) + DX[c]; tr = (y >> 3) + DY[c];
                        if (tc >= 0 && tc < COLS && tr >= 1 && tr < ROWS && M(tc, tr) == 0) refill_cell(tc, tr, i);
                    }
                }
                e_prevc[i] = x >> 3; e_prevr[i] = y >> 3;
                choose_dir_g(i);
                {
                    /* the Mascot smashes through the dirt ahead of it, leaving a tunnel; so does the Groundskeeper (quietly), which is
                     * how it opens up the sealed caves. Its tunnel is marked in paid[] so that it never rakes it shut. */
                    signed char mc = (x >> 3) + DX[e_dir[i]], mr = (y >> 3) + DY[e_dir[i]];
                    if (mc >= 0 && mc < COLS && mr >= 1 && mr < ROWS && M(mc, mr) == 1) {
                        M(mc, mr) = 0;
                        mark_around(mc, mr);
                        if (e_type[i] == 3) paid[(mr << 4) | mc] = 0x10;
                        else SFX(ASSET__audio__dig_sfx_ID);
                    }
                }
            }
            d = e_dir[i];
            e_x[i] = x + DX[d]; e_y[i] = y + DY[d];
            if (d < 2) e_face[i] = d;
            break;
        }
        e_acc[i] += espeed + (enemies_left == 1 ? 3 : 0);
        if (e_acc[i] < 16) return;
        e_acc[i] -= 16;
        if (!((x | y) & 7)) {
            c = x >> 3; r = y >> 3;
            tc = (px + 4) >> 3; tr = (py + 4) >> 3;
            /* heaters spit fire when lined up with Doug */
            if (e_type[i] == 1 && !e_flee[i] && r == tr && (tc != c) && rng() < 130) {
                d = (tc > c) ? DIR_R : DIR_L;
                if (absdiff(tc, c) <= 5 && line_clear(c, r, d, absdiff(tc, c)) == absdiff(tc, c)) {
                    e_state[i] = ES_FLAME; e_timer[i] = 0; e_face[i] = d;
                    e_flen[i] = line_clear(c, r, d, 3);
                    return;
                }
            }
            if (!(e_flee[i] && flee_dir(i))) choose_dir(i);
        }
        d = e_dir[i];
        /* enemies only walk through tunnels (choose_dir guarantees the next cell) */
        e_x[i] = x + DX[d]; e_y[i] = y + DY[d];
        if (d < 2) e_face[i] = d;
        if (e_flee[i] && e_y[i] == 0) enemy_escape(i);      /* out through the top of Doug's shaft */
        break;

    case ES_GHOST:
        if (e_timer[i] < 250) ++e_timer[i];
        if (e_flee[i]) {
            e_acc[i] += espeed - 2;                        /* a little slower than Doug, so he can cut them off */
            if (e_acc[i] < 16) return;
            e_acc[i] -= 16;
            if (y) --y;
            e_y[i] = y;
            if (y == 0) enemy_escape(i);
            break;
        }
        if (e_type[i] == 2) {
            /* baseball bat: flies straight at Doug through dirt, diagonally, never lands.
             * It hovers in its pocket for a few seconds (100 ticks) at the start of a round. */
            if (e_timer[i] < 100) return;
            e_acc[i] += 11 + (level >> 1);                 /* bats get quicker in later innings */
            if (e_acc[i] < 16) return;
            e_acc[i] -= 16;
            if (x < px) { ++x; e_face[i] = DIR_R; }
            else if (x > px) { --x; e_face[i] = DIR_L; }
            if (frame_ct & 1) { if (y < py) ++y; else if (y > py) --y; }
            e_x[i] = x; e_y[i] = y;
            break;
        }
        break;

    case ES_INFL:
        ++e_timer[i];
        if (e_timer[i] > ((e_type[i] == 4) ? 120 : 90)) {
            e_timer[i] = 0;
            if (--e_infl[i] == 0) {
                e_state[i] = (e_type[i] == 2) ? ES_GHOST : ES_WALK; e_acc[i] = 0;
            }
        }
        break;

    case ES_POP:
        if (++e_timer[i] > 8) e_state[i] = ES_NONE;
        break;

    case ES_SQUASH:
        if (++e_timer[i] > 24) e_state[i] = ES_NONE;
        break;

    case ES_FLAME:
        if (e_type[i] == 0) {                          /* Vumpire raising a fallen one */
            c = e_flen[i];
            if (!c_on[c]) { e_state[i] = ES_WALK; e_acc[i] = 0; break; }
            if (++e_timer[i] > 45) {
                r = c_slot[c];
                if (e_state[r] == ES_NONE) {
                    e_state[r] = ES_WALK; e_type[r] = 0;
                    e_x[r] = c_x[c]; e_y[r] = c_y[c];
                    e_infl[r] = 0; e_timer[r] = 0; e_acc[r] = 0;
                    ++enemies_left;
                    SFXP(ASSET__audio__oneup_sfx_ID, 2);
                }
                c_on[c] = 0;
                e_state[i] = ES_WALK; e_acc[i] = 0;
            }
            break;
        }
        ++e_timer[i];
        if (e_timer[i] == WINDUP) SFXP(ASSET__audio__flame_sfx_ID, 2);
        if (e_timer[i] > FLAME_END) { e_state[i] = ES_WALK; e_acc[i] = 0; }
        break;
    }
}

static unsigned char flame_hits_player(unsigned char i)
{
    unsigned char len = e_flen[i] * 8;              /* exactly as long as it is drawn */
    unsigned char fx;
    if (e_type[i] != 1 || e_state[i] != ES_FLAME || e_timer[i] < WINDUP) return 0;
    if (absdiff(e_y[i], py) > 5) return 0;          /* the flame's solid rows are 1-6 of its 8; Doug's body is the middle 6x6 of his sprite */
    if (e_face[i] == DIR_R) {
        fx = e_x[i] + 8;
        return (px + 7 > fx && px + 1 < fx + len);
    }
    fx = e_x[i] > len ? e_x[i] - len : 0;
    return (px + 7 > fx && px + 1 < e_x[i]);
}

static void enemies_update_all(void)
{
    unsigned char i;
    for (i = 0; i < MAXE; ++i)
        if (e_state[i] != ES_NONE) enemy_update(i);
}

static unsigned char enemies_touch_player(void)
{
    unsigned char i, k;
    for (i = 0; i < MAXE; ++i) {
        k = e_state[i];
        if ((k == ES_WALK || k == ES_GHOST || k == ES_FLAME || k == ES_INFL) && e_type[i] != 3) {   /* a stunned enemy still kills on touch */
            if (absdiff(e_x[i], px) < 6 && absdiff(e_y[i], py) < 6) return 1;
            if (k != ES_INFL && (flame_hits_player(i) || orb_hits_player(i))) return 1;
        }
    }
    return 0;
}
#pragma code-name (pop)

/* -------------------------------------------------------------- boulders -- */
static void rocks_update(void)
{
    unsigned char i, k, c, r, below;
    for (i = 0; i < MAXR; ++i) {
        if (!r_on[i]) continue;
        c = r_c[i]; r = r_r[i];
        switch (r_state[i]) {
        case RS_STILL:
            if (M(c, r + 1) == 0) { r_state[i] = RS_WOBBLE; r_timer[i] = 0; }
            break;
        case RS_WOBBLE:
            if (++r_timer[i] >= 26) {
                r_state[i] = RS_FALL;
                r_kills[i] = 0;
                M(c, r) = 0;
                mark_around(c, r);
                SFXP(ASSET__audio__fall_sfx_ID, 1);
            }
            break;
        case RS_FALL:
            r_y[i] += 2;
            if (!(r_y[i] & 7)) {
                below = (r_y[i] >> 3) + 1;
                r_r[i] = r_y[i] >> 3;
                if (below >= ROWS || M(c, below) != 0) {
                    r_state[i] = RS_CRUMBLE; r_timer[i] = 0;
                    SFXP(ASSET__audio__thud_sfx_ID, 2);
                }
            }
            /* crush things underneath */
            for (k = 0; k < MAXE; ++k) {
                if (e_state[k] == ES_NONE || e_state[k] == ES_POP || e_state[k] == ES_SQUASH) continue;
                if (absdiff(e_x[k], c << 3) < 7 && absdiff(e_y[k], r_y[i]) < 7) {
                    if (e_type[k] == 4) {
                        /* the Mascot is padded: a home plate counts as three strikes, then shatters */
                        e_timer[k] = 0;
                        e_infl[k] += 3;
                        r_state[i] = RS_CRUMBLE; r_timer[i] = 0;
                        SFXP(ASSET__audio__thud_sfx_ID, 3);
                        if (e_infl[k] >= 6) {
                            enemy_pop(k); add_score(50); add_popup(e_x[k], e_y[k], 50);
                            --enemies_left;
                        }
                        break;
                    }
                    e_state[k] = ES_SQUASH; e_timer[k] = 0;
                    e_x[k] = c << 3; e_y[k] = r_y[i] + 3;
                    if (e_y[k] > 96) e_y[k] = 96;
                    add_score(rock_pts[r_kills[i] < 5 ? r_kills[i] : 5]);
                    add_popup(e_x[k], e_y[k] > 8 ? e_y[k] - 8 : 0, rock_pts[r_kills[i] < 5 ? r_kills[i] : 5]);
                    ++r_kills[i];
                    --enemies_left;
                    SFXP(ASSET__audio__squash_sfx_ID, 3);
                }
            }
            break;
        case RS_CRUMBLE:
            if (++r_timer[i] > 12) r_on[i] = 0;
            break;
        }
    }
}

/* ---------------------------------------------------------------- render -- */
static void draw_field(void)
{
    field_flush();
    BLIT(slot_bg, 1, FY, BG_W, 104, 0, 0);
}

static void draw_rocks(void)
{
    unsigned char i, x, y, f;
    for (i = 0; i < MAXR; ++i) {
        if (!r_on[i]) continue;
        x = FX + (r_c[i] << 3);
        y = FY + ((r_state[i] == RS_FALL || r_state[i] == RS_CRUMBLE) ? r_y[i] : (r_r[i] << 3));
        switch (r_state[i]) {
        case RS_WOBBLE:
            f = (r_timer[i] >> 1) & 1;
            BLIT(slot_spr, x, y, 8, 8, rockw_x[f], rockw_y[f]);
            break;
        case RS_CRUMBLE:
            f = r_timer[i] > 5;
            BLIT(slot_spr, x, y, 8, 8, rockc_x[f], rockc_y[f]);
            break;
        default:
            BLIT(slot_spr, x, y, 8, 8, SP_ROCK_X, SP_ROCK_Y);
        }
    }
}

static void draw_ball(void)
{
    unsigned char bx, by;
    if (!ball_on) return;
    bx = FX + ball_x - 2; by = FY + ball_y - 2;
    queue_draw_box(bx - DX[ball_dir] * 3, by - DY[ball_dir] * 3, 4, 4, COL_HOSE_D);     /* motion streak */
    queue_draw_box(bx, by, 4, 4, COL_WHITE);
    queue_draw_box(bx + 1, by + 1, 2, 1, COL_FLAME3);                                     /* seam */
}

#pragma code-name (push, "PROG2")
static void draw_mark(unsigned char i, unsigned char x, unsigned char y)
{
    /* strike marks: X1 white, X2 yellow, X3 red (Mad Scott: X1..X5 in the same colours) */
    unsigned char sn = e_infl[i], m;
    if (e_type[i] != 4) m = (sn == 1) ? 0 : (sn == 2) ? 2 : 5;
    else m = (sn == 1) ? 0 : (sn == 2) ? 1 : (sn == 3) ? 3 : (sn == 4) ? 4 : 6;
    BLIT(slot_spr, x, y - ((e_type[i] == 4) ? 12 : 8), 8, 6, mark_x[m], mark_y[m]);
}

static void draw_enemy(unsigned char i)
{
    unsigned char st = e_state[i], x = FX + e_x[i], y = FY + e_y[i], f, sz, k;
    f = ((frame_ct >> 2) & 1);
    k = e_face[i] * 2 + f;
    if (e_type[i] == 1 && (st == ES_WALK || st == ES_FLAME)) {      /* the fireball circling a Heater */
        signed int ox, oy;
        ox = (signed int)x + ORB_X[ORB_K(0)]; oy = (signed int)y + ORB_Y[ORB_K(0)];
        if (ox >= 0 && ox < 121 && oy >= 0 && oy < 121)
            BLIT(slot_spr, (unsigned char)ox, (unsigned char)oy, 8, 8, flame_x[f & 1], flame_y[f & 1]);
    }
    switch (st) {
    case ES_WALK:
        if (e_type[i] == 4) { BLIT_BOB(slot_spr2, x - 4, y - 4, 16, 16, mascot_x[k], mascot_y[k], 10); if (e_infl[i]) draw_mark(i, x, y); }
        else if (e_type[i] == 3) BLIT_BOB(slot_spr, x, y, 8, 8, gk_x[k], gk_y[k], 5);
        else if (e_type[i])      BLIT(slot_spr, x, y, 8, 8, emb_x[k], emb_y[k]);
        else                     BLIT_BOB(slot_spr, x, y, 8, 8, grub_x[k], grub_y[k], 5);
        break;
    case ES_FLAME:
        if (e_type[i] == 0) {                          /* ritual: the Vumpire glows red */
            BLIT(slot_spr, x, y, 8, 8, grub_x[k], grub_y[k]);
            if (e_timer[i] & 4) {
                queue_draw_box(x - 1, y - 1, 2, 2, COL_FLAME3); queue_draw_box(x + 7, y - 1, 2, 2, COL_FLAME3);
                queue_draw_box(x - 1, y + 7, 2, 2, COL_FLAME3); queue_draw_box(x + 7, y + 7, 2, 2, COL_FLAME3);
            }
            break;
        }
        if (e_timer[i] < WINDUP && ((e_timer[i] >> 1) & 1))
            BLIT(slot_spr, x, y, 8, 8, emb_x[e_face[i] * 2], emb_y[e_face[i] * 2]);
        else
            BLIT(slot_spr, x, y, 8, 8, emb_x[e_face[i] * 2 + 1], emb_y[e_face[i] * 2 + 1]);
        if (e_timer[i] >= WINDUP) {
            unsigned char n, fx, fr;
            fr = (frame_ct >> 1) & 1;
            for (n = 0; n < e_flen[i]; ++n) {
                fx = (e_face[i] == DIR_R) ? x + 8 + (n << 3) : x - 8 - (n << 3);
                BLIT(slot_spr, fx, y, 8, 8, flame_x[fr ^ (n & 1)], flame_y[fr ^ (n & 1)]);
            }
        }
        break;
    case ES_GHOST:
        f = (frame_ct >> 3) & 1;
        if (e_type[i] == 2) BLIT(slot_spr, x - 2, y, 12, 8, bat_x[(frame_ct >> 1) & 1], bat_y[(frame_ct >> 1) & 1]);
        else                BLIT(slot_spr, x, y, 8, 8, ghost_x[f], ghost_y[f]);
        break;
    case ES_INFL:                          /* stunned: normal body plus a "K" per strike */
        if (e_type[i] == 4)      BLIT(slot_spr2, x - 4, y - 4, 16, 16, mascot_x[k], mascot_y[k]);
        else if (e_type[i] == 3) BLIT(slot_spr, x, y, 8, 8, gk_x[k], gk_y[k]);
        else if (e_type[i] == 2) BLIT(slot_spr, x - 2, y, 12, 8, bat_x[0], bat_y[0]);
        else if (e_type[i])      BLIT(slot_spr, x, y, 8, 8, emb_x[k], emb_y[k]);
        else                     BLIT(slot_spr, x, y, 8, 8, grub_x[k], grub_y[k]);
        draw_mark(i, x, y);
        break;
    case ES_POP:                           /* out! a little firework */
        k = e_timer[i] >> 1;
        if (k > 3) k = 3;
        sz = burst_size[k];
        BLIT(slot_spr, x + 4 - (sz >> 1), y + 4 - (sz >> 1), sz, sz, burst_x[k], burst_y[k]);
        if (e_timer[i] < 6) BLIT(slot_spr, x, y - ((e_type[i] == 4) ? 12 : 8), 8, 6, mark_x[(e_type[i] == 4) ? 7 : 5], mark_y[(e_type[i] == 4) ? 7 : 5]);
        break;
    case ES_SQUASH:
        if (e_type[i] == 3)  BLIT(slot_spr, x, y + 4, 8, 4, gk_x[k], gk_y[k] + 4);
        else if (e_type[i] == 2)  BLIT(slot_spr, x - 2, y + 4, 12, 4, bat_x[0], bat_y[0] + 4);
        else if (e_type[i])  BLIT(slot_spr, x, y + 4, 8, 4, emb_x[k], emb_y[k] + 4);
        else                 BLIT(slot_spr, x, y + 4, 8, 4, grub_x[k], grub_y[k] + 4);
        break;
    }
}

static void enemies_draw_all(void)
{
    unsigned char i;
    for (i = 0; i < MAXE; ++i)
        if (e_state[i] != ES_NONE) draw_enemy(i);
}
#pragma code-name (pop)

static void draw_player(void)
{
    unsigned char x = FX + px, y = FY + py, f;
    if (state == ST_DYING || state == ST_OVER) {
        f = (state == ST_OVER) || (state_timer > 20);
        if (state == ST_DYING && state_timer < 14) f = 0;
        BLIT(slot_spr, x, y, 8, 8, doug_dead_x[f], doug_dead_y[f]);
        return;
    }
    f = pmoving ? ((panim >> 2) & 1) : 0;
    BLIT_BOB(slot_spr, x, y, 8, 8, doug_x[pdir * 2 + f], doug_y[pdir * 2 + f], 5);
}

static void draw_hud(void)
{
    unsigned char i;
    queue_draw_box(1, 7, 126, 9, COL_INK);
    queue_draw_box(1, 15, 126, 1, COL_RIM);
    if (score_dirty) {
        fmt_score(score_str, score_h, score_t);
        fmt_score(hi_str, hi_h, hi_t);
        score_dirty = 0;
    }
    text(10, 9, "RUNS", 1);
    text(30, 9, score_str, 0);
    text(62, 9, "INN", 1);
    {
        char rd[3];
        rd[0] = '0' + (level / 10) % 10; rd[1] = '0' + (level % 10); rd[2] = 0;
        text(74, 9, rd, 0);
    }
    for (i = 0; i < lives && i < 5; ++i)
        BLIT(slot_spr, 121 - (i << 3) - 8, 8, 8, 6, SP_LIFE_X, SP_LIFE_Y);
}

static void draw_popups(void)
{
    unsigned char i, n;
    char buf[8];
    unsigned int v;
    for (i = 0; i < MAXP; ++i) {
        if (!pop_t[i]) continue;
        v = pop_v[i];
        /* hundreds -> digits + "00" (bit 15: a loss, with a minus sign) */
        n = 0;
        if (v & 0x8000) { buf[n++] = '-'; v &= 0x7FFF; }
        if (v >= 100) buf[n++] = '0' + v / 100;
        if (v >= 10) buf[n++] = '0' + (v / 10) % 10;
        buf[n++] = '0' + v % 10;
        buf[n++] = '0'; buf[n++] = '0'; buf[n] = 0;
        text(FX + pop_x[i] + 4 - (n << 1), FY + pop_y[i] + 1 - (pop_t[i] >> 3), buf, 1);
        --pop_t[i];
    }
}

/* the depth gauges carry a marker that follows Doug */
static void draw_depth_marker(void)
{
    unsigned char y = FY + py + 3;
    queue_draw_box(1, y, 5, 3, COL_GOLD);
    queue_draw_box(122, y, 5, 3, COL_GOLD);
}

static void draw_world(void)
{
    unsigned char i;
    draw_field();
    draw_depth_marker();
    draw_rocks();
    for (i = 0; i < MAXC; ++i)
        if (c_on[i]) BLIT(slot_spr, FX + c_x[i], FY + c_y[i], 8, 8, SP_TOMB_X, SP_TOMB_Y);
    if (gold_on && M(gold_c, gold_r) == 0) BLIT(slot_spr, FX + (gold_c << 3), FY + (gold_r << 3), 8, 8, SP_GOLD_X, SP_GOLD_Y);
    draw_ball();
    enemies_draw_all();
    draw_player();
    draw_popups();
    draw_hud();
}

/* ------------------------------------------------------------- game flow -- */
static void new_game(void)
{
    level = 1; lives = 3; score_h = 0; score_t = 0; next_life_h = 100;
    hi_at_start = hi_h; new_best = 0;
#ifdef FIXED_SEED
    run_seed = FIXED_SEED;                        /* regression builds: same caves every run */
#else
    run_seed = ((((unsigned int)vsync_raw << 8) ^ frame_ct ^ (idle_t * 251u)) ^ lfsr) | 1u;   /* new caves every game */
#endif
    score_dirty = 1;
    build_level();
    state = ST_INTRO; state_timer = 0; icur = 0;
    SFXP(ASSET__audio__start_sfx_ID, 2);
    stop_music();
}

static void start_music(void)
{
    play_song(ASSET__audio__theme_mid, REPEAT_LOOP);
    beat_start();
}

static void kill_player(void)
{
    state = ST_DYING; state_timer = 0;
    ball_on = 0;
    stop_music();
    SFXP(ASSET__audio__die_sfx_ID, 5);
}

static void play_update(void)
{
    unsigned char i, k;

    if (player1_new_buttons & INPUT_MASK_START) {
        state = ST_PAUSE;
        return;
    }
    player_update();
    rocks_update();
    if (c_on[0] | c_on[1] | c_on[2]) {
        k = vumpires_alive();
        for (i = 0; i < MAXC; ++i) {
            if (!c_on[i]) continue;
            if (!k) { c_on[i] = 0; continue; }                 /* nobody left to raise it */
            if (absdiff(px, c_x[i]) < 6 && absdiff(py, c_y[i]) < 6) {   /* Doug stomps the headstone */
                c_on[i] = 0; add_score(1); add_popup(c_x[i], c_y[i], 1);
                SFX(ASSET__audio__dig_sfx_ID);
            }
        }
    }
    enemies_update_all();

    /* deadly contact */
    if (enemies_touch_player()) { kill_player(); return; }
    for (i = 0; i < MAXR; ++i) {
        if (r_on[i] && r_state[i] == RS_FALL &&
            absdiff(px, r_c[i] << 3) < 7 && absdiff(py, r_y[i]) < 7) {
            kill_player();
            return;
        }
    }

    if (enemies_left == 0) {
        unsigned char alive = 0;
        for (i = 0; i < MAXE; ++i) if (e_state[i] != ES_NONE) alive = 1;
        if (!alive) {
            state = ST_CLEAR; state_timer = 0;
            stop_music();
            play_song(ASSET__audio__clear_mid, REPEAT_NONE);
        }
    }
}

#define FRAME_VSYNCS 2      /* game runs at 30 fps */
static unsigned char last_flip, last_tick;

/* One music tick per vsync, spread evenly: a tick on the in-between vsync and one right after the page flip,
 * so a slow frame can't make the notes bunch up. */
static void music_poll(void)
{
    unsigned char n = (unsigned char)(vsync_raw - last_tick);
    if (n > 4) { last_tick = vsync_raw - 4; n = 4; }
    while (n) { ++last_tick; tick_music(); --n; }
}

static void frame_end(void)
{
    unsigned char v;
    queue_clear_border(COL_INK);
    await_draw_queue();
    music_poll();
    for (;;) {
        v = vsync_raw;
        while (vsync_raw == v) { }                                   /* wait for the next vsync */
        if ((unsigned char)(vsync_raw - last_flip) >= FRAME_VSYNCS) break;
        music_poll();                                                /* the in-between vsync */
    }
    flip_pages();
    last_flip = vsync_raw;
    music_poll();
}

/* The whole-screen scenes live in their own bank, PROG1. The game loop reaches them through bank_call. */
#pragma code-name (push, "PROG1")

static void plaque(unsigned char x, unsigned char y, unsigned char w, unsigned char h)
{
    queue_draw_box(x, y, w, h, COL_INK);
    queue_draw_box(x + 2, y + 1, w - 4, 1, COL_RIM);
    queue_draw_box(x + 2, y + h - 2, w - 4, 1, COL_RIM);
}

static void title_scene(void)
{
    /* Doug runs the long tunnel with a Vumpire and a Heater in pursuit. Positions wrap
     * with period 128 (= 256 frames / 2), which matches the 8-bit frame counter exactly,
     * so the chase loops seamlessly: everyone runs off the right edge and re-enters left. */
    unsigned char t = frame_ct >> 1, f = (frame_ct >> 2) & 1, p;
    draw_field();
    p = t & 127;
    if (p < 112) BLIT(slot_spr, FX + p, FY + 72, 8, 8, doug_x[f], doug_y[f]);
    p = (t - 24) & 127;
    if (p < 112) BLIT(slot_spr, FX + p, FY + 72, 8, 8, grub_x[f], grub_y[f]);
    p = (t - 44) & 127;
    if (p < 112) BLIT(slot_spr, FX + p, FY + 72, 8, 8, emb_x[f], emb_y[f]);
    plaque(14, FY + 4, 100, 50);
    BLIT(slot_spr, 64 - (SP_LOGO_W >> 1), FY + 11, SP_LOGO_W, SP_LOGO_H, SP_LOGO_X, SP_LOGO_Y);
    if ((frame_ct & 32) == 0) text_center(FY + 40, "PUSH START", 1);
    plaque(20, FY + 84, 88, 12);
    text_center(FY + 87, "Z:THROW ARROWS:DIG", 0);
}

/* ---- high score: kept in the cartridge's flash save sector ------------------------------
 * layout: 0x44 0x55 lo hi check.  A blank/never-written sector fails the magic and is ignored. */
#pragma code-name (pop)
#pragma code-name (push, "CODE")           /* the save code stays in the fixed bank */
static void load_hiscore(void)
{
    unsigned char lo, hi;
    hi_saved = 0;
    if (save_peek(0) != 0x44 || save_peek(1) != 0x55) return;
    lo = save_peek(2); hi = save_peek(3);
    if (save_peek(4) != (unsigned char)(lo ^ hi ^ 0xA5)) return;
    hi_saved = ((unsigned int)hi << 8) | lo;
    if (hi_saved > hi_h) hi_h = hi_saved;
}

static void save_hiscore_if_needed(void)
{
    new_best = (score_h > hi_at_start);
    if (score_h <= hi_saved) return;
    await_draw_queue();
    sbuf[0] = 0x44; sbuf[1] = 0x55;
    sbuf[2] = (unsigned char)(score_h & 0xFF);
    sbuf[3] = (unsigned char)(score_h >> 8);
    sbuf[4] = sbuf[2] ^ sbuf[3] ^ 0xA5;
    clear_save_sector();
    save_write(sbuf, (void*)0x8000, 5);
    hi_saved = score_h;
}

/* bottom plaque shared by the win and game over screens: score / best, then PRESS START */
#pragma code-name (pop)
#pragma code-name (push, "PROG1")
static void score_plaque(void)
{
    queue_draw_box(1, 108, 126, 12, COL_INK);
    queue_draw_box(3, 109, 122, 1, COL_RIM);
    if ((frame_ct & 64) == 0 || scene_t < 40) {
        text(10, 112, "RUNS", 1); text(30, 112, score_str, 0);
        text(72, 112, "BEST", 1); text(92, 112, hi_str, 0);
    } else {
        text_center(112, "PRESS START", 1);
    }
}

static void over_scene(void)
{
    unsigned char i, x, y, f = (frame_ct >> 1) & 1;
    BLIT(slot_over, 0, 0, 64, 64, 0, 0);
    BLIT(slot_over, 64, 0, 64, 64, 64, 0);
    BLIT(slot_over, 0, 64, 64, 64, 0, 64);
    BLIT(slot_over, 64, 64, 64, 64, 64, 64);
    for (i = 0; i < 3; ++i) {                      /* baseball bats circle the moon */
        x = (unsigned char)(((unsigned)frame_ct * (2 + i) >> 1) + i * 57) % 140;
        y = 32 + i * 5 + ((frame_ct >> 3) & 3) * (i + 1) / 2;
        if (x < 116) BLIT(slot_spr, x, y, 12, 8, bat_x[(f + i) & 1], bat_y[(f + i) & 1]);
    }
    text_center(31, "YOU'RE OUT!", 1);
    if (new_best && (frame_ct & 16)) {
        queue_draw_box(30, 63, 68, 9, COL_INK);
        text_center(65, "NEW BEST SCORE!", 1);
    }
    score_plaque();
}

static void win_scene(void)
{
    static const unsigned char bx[3] = { 22, 106, 64 }, by[3] = { 50, 46, 50 };
    static const unsigned char conf[5] = { COL_GOLD, COL_FLAME3, COL_RIM, COL_WHITE, COL_HAT };
    unsigned char i, k, f, sz, x, y, t = frame_ct;
    /* 128 has the blitter's flip bit set, so the page goes down as four 64x64 quadrants */
    BLIT(slot_end, 0, 0, 64, 64, 0, 0);
    BLIT(slot_end, 64, 0, 64, 64, 64, 0);
    BLIT(slot_end, 0, 64, 64, 64, 0, 64);
    BLIT(slot_end, 64, 64, 64, 64, 64, 64);
    for (i = 0; i < 3; ++i) {                       /* fireworks */
        k = (unsigned char)((t >> 1) + i * 21) & 63;
        if (k < 40) {
            f = k / 10; sz = burst_size[f];
            BLIT(slot_spr, bx[i] - (sz >> 1), by[i] - (sz >> 1), sz, sz, burst_x[f], burst_y[f]);
        }
    }
    for (i = 0; i < 22; ++i) {                      /* confetti */
        x = 3 + (unsigned char)((i * 53 + (t >> 3) * (1 + (i & 1))) % 120);
        y = 8 + (unsigned char)((((unsigned)t * (1 + (i & 3)) >> 1) + i * 11) % 104);
        queue_draw_box(x, y, 2, 3, conf[i % 5]);
    }
    y = new_best ? 22 : 13;                         /* solid plate so the text stays readable on a real LCD */
    queue_draw_box(14, 34, 100, y, COL_INK);
    queue_draw_box(15, 35, 98, 1, COL_RIM);
    queue_draw_box(15, 33 + y, 98, 1, COL_RIM);
    text_center(37, "NINE INNINGS COMPLETE", 1);
    if (new_best && (frame_ct & 16)) text_center(46, "NEW BEST SCORE!", 0);
    score_plaque();
}

#pragma code-name (pop)
/* Idle at the title long enough and the enemies introduce themselves, one at a time. */
#pragma code-name (push, "PROG1")
static void attract_scene(void)
{
    static const char* const names[5] = { "VUMPIRE", "HEATER", "BASEBALL BAT", "GROUNDSKEEPER", "MAD SCOTT" };
    static const char* const descs[5] = { "RAISES THE FALLEN", "BREATHES FIRE",
                                          "FLIES THROUGH DIRT", "RAKES TUNNELS SHUT",
                                          "BOSS. SIX STRIKES" };
    unsigned char i, y, f = (frame_ct >> 2) & 1, shown = (unsigned char)(scene_t / 50) + 1;
    draw_field();
    plaque(6, FY + 6, 116, 92);
    text_center(FY + 12, "MEET THE OPPOSITION", 1);
    if (shown > 5) shown = 5;
    for (i = 0; i < shown; ++i) {
        y = FY + 24 + i * 14;
        switch (i) {
        case 0: BLIT(slot_spr, 12, y, 8, 8, grub_x[f], grub_y[f]); break;
        case 1: BLIT(slot_spr, 12, y, 8, 8, emb_x[f], emb_y[f]); break;
        case 2: BLIT(slot_spr, 10, y, 12, 8, bat_x[(frame_ct >> 1) & 1], bat_y[(frame_ct >> 1) & 1]); break;
        case 3: BLIT(slot_spr, 12, y, 8, 8, gk_x[f], gk_y[f]); break;
        default:
            if (slot_spr2 == 0xFF) need_page(&slot_spr2, &ASSET__spr2__spr2_bmp_load_list);
            BLIT(slot_spr2, 8, y - 4, 16, 16, mascot_x[f], mascot_y[f]);
        }
        text(28, y, names[i], 1);
        text(28, y + 6, descs[i], 0);
    }
}
#pragma code-name (pop)

#pragma code-name (push, "PROG1")

/* Every time an inning brings a new kind of enemy, a short screen introduces it. */
static const char* const I_TITLE[5] = { "WARNING!", "NEW ARRIVAL!", "INCOMING!", "HEADS UP!", "FINAL INNING!" };
static const char* const I_NAME[5]  = { "THE VUMPIRES", "THE HEATERS", "THE BASEBALL BATS", "THE GROUNDSKEEPER", "MAD SCOTT" };
static const char* const I_WHAT[5]  = { "ARE ATTACKING!", "BREATHE FIRE!", "FLY THROUGH DIRT!", "CLOSES YOUR TUNNELS", "IS COMING FOR YOU!" };

static unsigned char intro_for_level(unsigned char lv)
{
    switch (lv) {
    case 1: return 0;
    case 2: return 1;
    case 3: return 2;
    case 5: return 3;
    case INNINGS: return 4;
    }
    return 255;
}

static void intro_scene(void)
{
    unsigned char t = state_timer, f = (frame_ct >> 2) & 1, i, p;
    draw_field();
    plaque(8, FY + 10, 112, 86);
    if (t >= 30 || (t > 6 && !((t >> 1) & 1))) text_center(FY + 19, I_TITLE[icur], 1);
    if (t > 12) text_center(FY + 32, I_NAME[icur], 1);
    if (t > 22) text_center(FY + 41, I_WHAT[icur], 1);
    /* a line of the new enemy marches across the bottom of the plaque */
    for (i = 0; i < 6; ++i) {
        p = (unsigned char)((frame_ct >> 1) - i * 18) & 127;
        if (p >= 100) continue;
        switch (icur) {
        case 0: BLIT(slot_spr, FX + p, FY + 65, 8, 8, grub_x[f], grub_y[f]); break;
        case 1: BLIT(slot_spr, FX + p, FY + 65, 8, 8, emb_x[f], emb_y[f]); break;
        case 2: BLIT(slot_spr, FX + p, FY + 65, 12, 8, bat_x[(frame_ct >> 1) & 1], bat_y[(frame_ct >> 1) & 1]); break;
        case 3: BLIT(slot_spr, FX + p, FY + 65, 8, 8, gk_x[f], gk_y[f]); break;
        default: if (!(i & 1)) BLIT(slot_spr2, FX + p, FY + 61, 16, 16, mascot_x[f], mascot_y[f]);
        }
    }
    if (t > 45 && (frame_ct & 32) == 0) text_center(FY + 80, "PRESS START", 1);
}

#pragma code-name (pop)

void game_main(void)
{
    unsigned char i;

    last_tick = last_flip = vsync_raw;
    slot_bg = allocate_sprite(&ASSET__bg__bg_bmp_load_list);
    slot_spr = allocate_sprite(&ASSET__spr__spr_bmp_load_list);

    hi_h = 100;
    load_hiscore();
    score_h = 0; score_t = 0; lives = 3; level = 1;
    score_dirty = 1;
    for (i = 0; i < MAXE; ++i) e_state[i] = ES_NONE;
    for (i = 0; i < MAXR; ++i) r_on[i] = 0;
    build_title_map();
    state = ST_TITLE; state_timer = 0;
    play_song(ASSET__audio__title_mid, REPEAT_LOOP);

    while (1) {
        update_inputs();
        ++frame_ct;
        beat_tick();
        music_poll();

        switch (state) {
        case ST_TITLE:
            title_scene();
            queue_draw_box(1, 7, 126, 9, COL_INK);
            if (score_dirty) { fmt_score(hi_str, hi_h, hi_t); }
            text(10, 9, "BEST", 1);
            text(30, 9, hi_str, 0);
            if (player1_buttons) idle_t = 0; else ++idle_t;
            if (player1_new_buttons & (INPUT_MASK_START | INPUT_MASK_A)) {
                new_game();
            } else if (idle_t > 450) {           /* ~15 s of nothing: show the cast */
                need_page(&slot_spr2, &ASSET__spr2__spr2_bmp_load_list);
                state = ST_ATTRACT; scene_t = 0;
            }
            break;

        case ST_ATTRACT:
            ++scene_t;
            attract_scene();
            queue_draw_box(1, 7, 126, 9, COL_INK);
            if (player1_new_buttons & (INPUT_MASK_START | INPUT_MASK_A)) {
                new_game();
            } else if ((player1_new_buttons & INPUT_MASK_ALL_KEYS) || scene_t > 520) {
                state = ST_TITLE; idle_t = 0;
            }
            break;

        case ST_INTRO:
            intro_scene();
            queue_draw_box(1, 7, 126, 9, COL_INK);
            if (++state_timer > 230 || (state_timer > 30 && (player1_new_buttons & (INPUT_MASK_START | INPUT_MASK_A)))) {
                state = ST_READY; state_timer = 0;
                SFXP(ASSET__audio__ready_sfx_ID, 2);
            }
            break;

        case ST_READY:
            draw_world();
            if (state_timer > 20) {
                if (level >= INNINGS) {
                    banner("FINAL INNING", "BOSS: MAD SCOTT");
                } else {
                    char rd[9] = "INNING 0";
                    rd[7] = '0' + level;
                    banner(rd, "PLAY BALL!");
                }
            }
            if (++state_timer > 90) { state = ST_PLAY; state_timer = 0; start_music(); }
            break;

        case ST_PLAY:
            play_update();
            draw_world();
            break;

        case ST_PAUSE:
            draw_world();
            banner("PAUSED", 0);
            if (player1_new_buttons & INPUT_MASK_START) state = ST_PLAY;
            break;

        case ST_DYING:
            ++state_timer;
            rocks_update();
            draw_world();
            if (state_timer > 70) {
                if (--lives == 0) {
                    save_hiscore_if_needed();
                    need_page(&slot_over, &ASSET__over__over_bmp_load_list);
                    fmt_score(score_str, score_h, score_t); fmt_score(hi_str, hi_h, hi_t);
                    state = ST_OVER; state_timer = 0; scene_t = 0;
                    play_song(ASSET__audio__over_mid, REPEAT_NONE);
                } else {
                    reset_player();
                    reset_enemies_home();
                    state = ST_READY; state_timer = 0;
                    SFXP(ASSET__audio__ready_sfx_ID, 2);
                }
            }
            break;

        case ST_CLEAR:
            draw_world();
            banner("INNING OVER!", 0);
            if (++state_timer > 130) {
                if (level >= INNINGS) {
                    add_score(10 * lives);           /* 1,000 per life left */
                    save_hiscore_if_needed();
                    need_page(&slot_end, &ASSET__end__end_bmp_load_list);
                    fmt_score(score_str, score_h, score_t); fmt_score(hi_str, hi_h, hi_t);
                    state = ST_WIN; state_timer = 0; scene_t = 0;
                    play_song(ASSET__audio__title_mid, REPEAT_LOOP);
                } else {
                    ++level;
                    build_level();
                    icur = intro_for_level(level);
                    state_timer = 0;
                    if (icur != 255) {
                        state = ST_INTRO;
                        SFXP(ASSET__audio__start_sfx_ID, 2);
                    } else {
                        state = ST_READY;
                        SFXP(ASSET__audio__ready_sfx_ID, 2);
                    }
                }
            }
            break;

        case ST_WIN:
            if (scene_t < 60000u) ++scene_t;
            win_scene();
            if (scene_t > 60 && (player1_new_buttons & INPUT_MASK_START)) {
                build_title_map();
                for (i = 0; i < MAXE; ++i) e_state[i] = ES_NONE;
                for (i = 0; i < MAXR; ++i) r_on[i] = 0;
                state = ST_TITLE; state_timer = 0;
                score_dirty = 1;
                play_song(ASSET__audio__title_mid, REPEAT_LOOP);
            }
            break;

        case ST_OVER:
            if (scene_t < 60000u) ++scene_t;
            over_scene();
            if (scene_t > 600 || (scene_t > 60 && (player1_new_buttons & INPUT_MASK_START))) {
                build_title_map();
                for (i = 0; i < MAXE; ++i) e_state[i] = ES_NONE;
                for (i = 0; i < MAXR; ++i) r_on[i] = 0;
                state = ST_TITLE; state_timer = 0;
                score_dirty = 1;
                play_song(ASSET__audio__title_mid, REPEAT_LOOP);
            }
            break;
        }

        frame_end();
    }
}

#pragma code-name (pop)

void main(void)
{
    change_rom_bank(BANK_PROG0);
    game_main();
}

/* Reads one byte of the flash save sector. Lives in fixed ROM because switching the
 * 0x8000 window to the save bank would pull the game code (in bank PROG0) out from under us. */
unsigned char save_peek(unsigned int off)
{
    unsigned char v;
    push_rom_bank();
    change_rom_bank(BANK_SAVE);
    v = *((volatile unsigned char*)(0x8000u + off));
    pop_rom_bank();
    return v;
}
