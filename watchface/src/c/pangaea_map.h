#pragma once
#include <pebble.h>
#include "pangaea_data.h"

typedef struct {
  uint8_t hour_mode;     // 0 = Watch system default, 1 = 12-hour, 2 = 24-hour
  int32_t color_time;    // Default: 0xFFAA00 (Chrome Yellow)
  int32_t color_taxon;   // Default: 0xFFAA00 (Chrome Yellow)
  int32_t color_coords;  // Default: 0xFFFFFF (White)
  int32_t color_age;     // Default: 0x55FFFF (Electric Blue)
  int32_t color_ticker;  // Default: 0xAAFFAA (Mint Green)
  int32_t color_header;  // Default: 0xFFFFFF (White)
  int32_t color_footer;  // Default: 0xAAAAAA (Light Gray)
} PangaeaConfig;

typedef struct {
  time_t clock_time;
  uint8_t hour;
  uint8_t minute;
  uint8_t second;
  float age_ma;
  char period[20];

  PangaeaConfig config;

  bool has_home;
  int32_t home_plate_id;
  int16_t home_lat_x100;
  int16_t home_lon_x100;
  uint16_t home_birth_ma_x10;
  char home_label[20];

  bool home_alive;
  float paleo_lat;
  float paleo_lon;
  float drift_km;
  float drift_cmyr;

  char active_event[28];
  char fossil_genus[24];
  char fossil_group[16];
  int16_t fossil_dist_km;
  bool fossil_marine;
  bool fossil_found;

  char status_msg[32];
} PangaeaState;

void pangaea_map_init(void);
void pangaea_map_deinit(void);
void pangaea_map_render(GContext *ctx, GRect bounds, PangaeaState *state);
