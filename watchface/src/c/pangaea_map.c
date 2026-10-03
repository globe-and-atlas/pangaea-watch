#include "pangaea_map.h"
#include "math_geo.h"
#include <math.h>

static GFont s_font_norm;
static GFont s_font_bold;
static GFont s_font_time;
static GFont s_font_taxon;

void pangaea_map_init(void) {
  s_font_norm = fonts_get_system_font(FONT_KEY_GOTHIC_14);
  s_font_bold = fonts_get_system_font(FONT_KEY_GOTHIC_14_BOLD);
  s_font_time = fonts_get_system_font(FONT_KEY_GOTHIC_24_BOLD);
  s_font_taxon = fonts_get_system_font(FONT_KEY_GOTHIC_18_BOLD);
}

void pangaea_map_deinit(void) {
  // System fonts do not need to be destroyed
}

void pangaea_map_render(GContext *ctx, GRect bounds, PangaeaState *state) {
  // 1. Overall Background (Black)
  graphics_context_set_fill_color(ctx, GColorBlack);
  graphics_fill_rect(ctx, bounds, 0, GCornerNone);

  // 2. Top Header Bar (y: 0..26, divider at y: 27)
  // Left: Hero Digital Time (24px Bold, 12h or 24h configurable)
  char time_buf[16];
  if (state->config.hour_mode == 0) {
    clock_copy_time_string(time_buf, sizeof(time_buf));
  } else {
    time_t now = state->clock_time ? state->clock_time : time(NULL);
    strftime(time_buf, sizeof(time_buf), state->config.hour_mode == 2 ? "%H:%M" : "%I:%M", localtime(&now));
    if (state->config.hour_mode == 1 && time_buf[0] == '0') {
      memmove(time_buf, time_buf + 1, sizeof(time_buf) - 1);
    }
  }
  GColor col_time = state->config.color_time ? GColorFromHEX(state->config.color_time) : GColorChromeYellow;
  graphics_context_set_text_color(ctx, col_time);
  graphics_draw_text(ctx, time_buf, s_font_time, GRect(4, -3, 85, 28),
                     GTextOverflowModeTrailingEllipsis, GTextAlignmentLeft, NULL);

  // Right: Stacked Period Name + Age
  GColor col_header = state->config.color_header ? GColorFromHEX(state->config.color_header) : GColorWhite;
  graphics_context_set_text_color(ctx, col_header);
  graphics_draw_text(ctx, state->period, s_font_bold, GRect(90, 0, bounds.size.w - 94, 14),
                     GTextOverflowModeTrailingEllipsis, GTextAlignmentRight, NULL);

  char age_buf[24];
  if (state->age_ma < 0.05f) {
    snprintf(age_buf, sizeof(age_buf), "TODAY");
  } else {
    snprintf(age_buf, sizeof(age_buf), "%.1f MA", state->age_ma);
  }
  GColor col_age = state->config.color_age ? GColorFromHEX(state->config.color_age) : GColorElectricBlue;
  graphics_context_set_text_color(ctx, col_age);
  graphics_draw_text(ctx, age_buf, s_font_bold, GRect(90, 13, bounds.size.w - 94, 14),
                     GTextOverflowModeTrailingEllipsis, GTextAlignmentRight, NULL);

  graphics_context_set_stroke_color(ctx, GColorDarkGray);
  graphics_draw_line(ctx, GPoint(0, 28), GPoint(bounds.size.w - 1, 28));

  // 3. Map Frame (x: 4, y: 32, w: 192, h: 96)
  GRect map_rect = GRect(PANGAEA_MAP_X, PANGAEA_MAP_Y, PANGAEA_MAP_W, PANGAEA_MAP_H);

  // Background Ocean
  graphics_context_set_fill_color(ctx, GColorOxfordBlue);
  graphics_fill_rect(ctx, map_rect, 0, GCornerNone);

  // Equator & Prime Meridian Grid
  graphics_context_set_stroke_color(ctx, GColorDarkGray);
  int16_t eq_y = map_rect.origin.y + (map_rect.size.h / 2);
  int16_t pm_x = map_rect.origin.x + (map_rect.size.w / 2);
  graphics_draw_line(ctx, GPoint(map_rect.origin.x, eq_y), GPoint(map_rect.origin.x + map_rect.size.w - 1, eq_y));
  graphics_draw_line(ctx, GPoint(pm_x, map_rect.origin.y), GPoint(pm_x, map_rect.origin.y + map_rect.size.h - 1));

  // Map Border (White)
  graphics_context_set_stroke_color(ctx, GColorWhite);
  graphics_draw_rect(ctx, map_rect);

  // 4. Compute active rotations for each plate at current time
  float minute = (float)state->hour * 60.0f + (float)state->minute + (float)state->second / 60.0f;
  int k_idx = 0;
  float t_frac = 0.0f;
  math_geo_find_bracket(minute, &k_idx, &t_frac);

  Quat active_quats[PANGAEA_NUM_PLATES];
  bool plate_active[PANGAEA_NUM_PLATES];
  uint16_t curr_age_x10 = (uint16_t)roundf(state->age_ma * 10.0f);

  for (int p = 0; p < PANGAEA_NUM_PLATES; p++) {
    PangaeaQuat16 q0 = s_pangaea_rotations[k_idx][p];
    PangaeaQuat16 q1 = s_pangaea_rotations[k_idx + 1][p];
    bool has_q0 = !math_geo_quat_is_zero(q0);
    bool has_q1 = !math_geo_quat_is_zero(q1);

    if (has_q0 && has_q1) {
      active_quats[p] = math_geo_quat_slerp(math_geo_quat_from_int16(q0),
                                            math_geo_quat_from_int16(q1), t_frac);
      plate_active[p] = true;
    } else if (has_q0) {
      active_quats[p] = math_geo_quat_from_int16(q0);
      plate_active[p] = true;
    } else if (has_q1) {
      active_quats[p] = math_geo_quat_from_int16(q1);
      plate_active[p] = true;
    } else {
      plate_active[p] = false;
    }
  }

  // 5. Draw Continental Coastlines (Mint Green)
  graphics_context_set_stroke_color(ctx, GColorMintGreen);
  GPoint prev_pt = GPoint(0, 0);
  float prev_lon = 0.0f;
  bool has_prev = false;

  for (int i = 0; i < PANGAEA_NUM_VERTICES; i++) {
    const PangaeaVertex *v = &s_pangaea_vertices[i];
    // A vertex is hidden until its crust exists (current age <= birth age)
    if (curr_age_x10 > v->birth_ma_x10) {
      has_prev = false;
      continue;
    }
    if (!plate_active[v->plate_idx]) {
      has_prev = false;
      continue;
    }

    float v_lat = (float)v->lat_x100 / 100.0f;
    float v_lon = (float)v->lon_x100 / 100.0f;
    Vec3 rotated_v = math_geo_quat_rotate_vec(active_quats[v->plate_idx],
                                              math_geo_to_vec(v_lat, v_lon));
    float plat = 0.0f, plon = 0.0f;
    math_geo_to_lat_lon(rotated_v, &plat, &plon);
    GPoint pt = math_geo_coord_to_screen(plat, plon, map_rect);

    bool wrap = has_prev && (fabsf(plon - prev_lon) > 180.0f);
    if (v->pen_down && has_prev && !wrap) {
      graphics_draw_line(ctx, prev_pt, pt);
    }
    prev_pt = pt;
    prev_lon = plon;
    has_prev = true;
  }

  // 6. Draw Home Crosshair (Chrome Yellow)
  if (state->has_home && state->home_alive) {
    GPoint u_pt = math_geo_coord_to_screen(state->paleo_lat, state->paleo_lon, map_rect);
    graphics_context_set_stroke_color(ctx, GColorChromeYellow);
    graphics_draw_line(ctx, GPoint(u_pt.x - 3, u_pt.y), GPoint(u_pt.x + 3, u_pt.y));
    graphics_draw_line(ctx, GPoint(u_pt.x, u_pt.y - 3), GPoint(u_pt.x, u_pt.y + 3));
  }

  // 7. Deep-Time "Day Arc" Ribbon (y: 130..133, height 4px, width 192px)
  // Triassic (00:00 - 06:35): x: 4..56 (Amber/Orange)
  // Jurassic (06:35 - 13:48): x: 57..113 (Cadet/Cyan)
  // Cretaceous (13:48 - 23:59): x: 114..194 (Mint)
  // Asteroid impact boundary at 66 Ma: x: 195 (Red)
  graphics_context_set_fill_color(ctx, GColorOrange);
  graphics_fill_rect(ctx, GRect(4, 130, 53, 4), 0, GCornerNone);
  graphics_context_set_fill_color(ctx, GColorCadetBlue);
  graphics_fill_rect(ctx, GRect(57, 130, 57, 4), 0, GCornerNone);
  graphics_context_set_fill_color(ctx, GColorMintGreen);
  graphics_fill_rect(ctx, GRect(114, 130, 81, 4), 0, GCornerNone);
  graphics_context_set_fill_color(ctx, GColorRed);
  graphics_fill_rect(ctx, GRect(195, 130, 1, 4), 0, GCornerNone);

  // Day Arc Cursor Needle (White, 2px wide, y: 129..134)
  int16_t cur_x = 4 + (int16_t)((minute * 191.0f) / 1440.0f);
  if (cur_x > 195) cur_x = 195;
  graphics_context_set_fill_color(ctx, GColorWhite);
  graphics_fill_rect(ctx, GRect(cur_x - 1, 129, 2, 6), 0, GCornerNone);

  // 8. Telemetry Text Stack (y: 136..206)
  int16_t text_w = bounds.size.w - 8;

  // Line 1: Hero Taxon / Status (18px Chrome Yellow Bold)
  char line1[48] = {0};
  if (!state->has_home) {
    snprintf(line1, sizeof(line1), "%s", state->status_msg[0] ? state->status_msg : "LOCATING GROUND…");
  } else if (!state->home_alive) {
    snprintf(line1, sizeof(line1), "GROUND NOT FORMED YET");
  } else if (state->age_ma < 66.0f) {
    snprintf(line1, sizeof(line1), "AFTER THE DINOSAURS");
  } else if (state->fossil_found) {
    if (state->fossil_group[0]) {
      snprintf(line1, sizeof(line1), "%s · %s", state->fossil_genus, state->fossil_group);
    } else {
      snprintf(line1, sizeof(line1), "%s", state->fossil_genus);
    }
  } else {
    snprintf(line1, sizeof(line1), "NOTHING FOUND NEARBY");
  }
  GColor col_taxon = state->config.color_taxon ? GColorFromHEX(state->config.color_taxon) : GColorChromeYellow;
  graphics_context_set_text_color(ctx, col_taxon);
  graphics_draw_text(ctx, line1, s_font_taxon, GRect(PANGAEA_MAP_X, 136, text_w, 20),
                     GTextOverflowModeTrailingEllipsis, GTextAlignmentLeft, NULL);

  // Line 2: Context Subline (14px Gothic)
  char line2[48] = {0};
  if (!state->has_home) {
    snprintf(line2, sizeof(line2), "MERDITH 2021 PLATE MODEL");
  } else if (!state->home_alive) {
    snprintf(line2, sizeof(line2), "APPEARS AT %.1f MA", (float)state->home_birth_ma_x10 / 10.0f);
  } else if (state->age_ma < 66.0f) {
    snprintf(line2, sizeof(line2), "CENOZOIC FAST-FORWARD");
  } else if (state->fossil_found) {
    snprintf(line2, sizeof(line2), "%s FIND • %d KM",
             state->fossil_marine ? "MARINE" : "TERRESTRIAL", state->fossil_dist_km);
  } else {
    snprintf(line2, sizeof(line2), "NO FOSSILS WITHIN 1000 KM");
  }
  graphics_context_set_text_color(ctx, GColorWhite);
  graphics_draw_text(ctx, line2, s_font_norm, GRect(PANGAEA_MAP_X, 155, text_w, 15),
                     GTextOverflowModeTrailingEllipsis, GTextAlignmentLeft, NULL);

  // Line 3: Event Ticker or Drift Odometer (14px Gothic)
  char line3[48] = {0};
  GColor line3_color = state->config.color_ticker ? GColorFromHEX(state->config.color_ticker) : GColorMintGreen;
  if (state->active_event[0]) {
    snprintf(line3, sizeof(line3), "%s", state->active_event);
    line3_color = GColorWhite;
  } else if (state->has_home && state->home_alive) {
    snprintf(line3, sizeof(line3), "DRIFT %d KM • %.1f CM/YR",
             (int)roundf(state->drift_km), state->drift_cmyr);
  }
  if (line3[0]) {
    graphics_context_set_text_color(ctx, line3_color);
    graphics_draw_text(ctx, line3, s_font_norm, GRect(PANGAEA_MAP_X, 171, text_w, 15),
                       GTextOverflowModeTrailingEllipsis, GTextAlignmentLeft, NULL);
  }

  // Line 4: Paleo Coordinates (14px Gothic)
  char line4[48] = {0};
  if (state->has_home && state->home_alive) {
    char s_lat = state->paleo_lat < 0 ? '-' : '+';
    char s_lon = state->paleo_lon < 0 ? '-' : '+';
    snprintf(line4, sizeof(line4), "PALEO: %c%.1f°, %c%.1f° (YOU)",
             s_lat, fabsf(state->paleo_lat), s_lon, fabsf(state->paleo_lon));
  } else {
    snprintf(line4, sizeof(line4), "GLOBAL RECONSTRUCTION");
  }
  GColor col_coords = state->config.color_coords ? GColorFromHEX(state->config.color_coords) : GColorWhite;
  graphics_context_set_text_color(ctx, col_coords);
  graphics_draw_text(ctx, line4, s_font_norm, GRect(PANGAEA_MAP_X, 187, text_w, 15),
                     GTextOverflowModeTrailingEllipsis, GTextAlignmentLeft, NULL);

  // 9. Bottom Bar (y: 207..227)
  graphics_context_set_stroke_color(ctx, GColorDarkGray);
  graphics_draw_line(ctx, GPoint(0, bounds.size.h - 21), GPoint(bounds.size.w - 1, bounds.size.h - 21));

  // Left: Home Location label
  const char *lbl = state->has_home && state->home_label[0] ? state->home_label : "PANGAEA";
  GColor col_footer = state->config.color_footer ? GColorFromHEX(state->config.color_footer) : GColorLightGray;
  graphics_context_set_text_color(ctx, col_footer);
  graphics_draw_text(ctx, lbl, s_font_bold, GRect(PANGAEA_MAP_X, bounds.size.h - 18, 120, 16),
                     GTextOverflowModeTrailingEllipsis, GTextAlignmentLeft, NULL);

  // Right: Climate Band
  const char *band = state->has_home && state->home_alive ? math_geo_climate_band(state->paleo_lat) : "GLOBAL";
  graphics_draw_text(ctx, band, s_font_norm, GRect(bounds.size.w - 74, bounds.size.h - 18, 70, 16),
                     GTextOverflowModeTrailingEllipsis, GTextAlignmentRight, NULL);
}
