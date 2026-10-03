#include <pebble.h>
#include "pangaea_data.h"
#include "math_geo.h"
#include "pangaea_map.h"
#include <math.h>

#define STORAGE_KEY_HOME 101
#define STORAGE_KEY_CONFIG 102

static Window *s_main_window;
static Layer *s_canvas_layer;
static PangaeaState s_state;
static TimeUnits s_current_tick_unit = MINUTE_UNIT;

typedef struct {
  int32_t plate_id;
  int16_t lat_x100;
  int16_t lon_x100;
  uint16_t birth_ma_x10;
  char label[20];
} PersistedHome;

static void save_config_state(void) {
  persist_write_data(STORAGE_KEY_CONFIG, &s_state.config, sizeof(s_state.config));
}

static void load_config_state(void) {
  if (persist_exists(STORAGE_KEY_CONFIG) &&
      persist_read_data(STORAGE_KEY_CONFIG, &s_state.config, sizeof(s_state.config)) == sizeof(s_state.config)) {
    return;
  }
  // Defaults:
  s_state.config.hour_mode = 0; // Follow watch
  s_state.config.color_time = 0xFFAA00;   // Chrome Yellow
  s_state.config.color_taxon = 0xFFAA00;  // Chrome Yellow
  s_state.config.color_coords = 0xFFFFFF; // White
  s_state.config.color_age = 0x55FFFF;    // Electric Blue
  s_state.config.color_ticker = 0xAAFFAA; // Mint Green
  s_state.config.color_header = 0xFFFFFF; // White
  s_state.config.color_footer = 0xAAAAAA; // Light Gray
}

static void save_home_state(void) {
  if (!s_state.has_home) return;
  PersistedHome saved = {
    .plate_id = s_state.home_plate_id,
    .lat_x100 = s_state.home_lat_x100,
    .lon_x100 = s_state.home_lon_x100,
    .birth_ma_x10 = s_state.home_birth_ma_x10,
  };
  strncpy(saved.label, s_state.home_label, sizeof(saved.label));
  persist_write_data(STORAGE_KEY_HOME, &saved, sizeof(saved));
}

static void load_home_state(void) {
  PersistedHome saved;
  if (persist_exists(STORAGE_KEY_HOME) &&
      persist_read_data(STORAGE_KEY_HOME, &saved, sizeof(saved)) == sizeof(saved)) {
    s_state.has_home = true;
    s_state.home_plate_id = saved.plate_id;
    s_state.home_lat_x100 = saved.lat_x100;
    s_state.home_lon_x100 = saved.lon_x100;
    s_state.home_birth_ma_x10 = saved.birth_ma_x10;
    strncpy(s_state.home_label, saved.label, sizeof(s_state.home_label));
  } else {
    // Default reference location: Spring, TX (Plate 101, exists at 252 Ma)
    s_state.has_home = true;
    s_state.home_plate_id = 101;
    s_state.home_lat_x100 = 3003;
    s_state.home_lon_x100 = -9553;
    s_state.home_birth_ma_x10 = 2520;
    strncpy(s_state.home_label, "SPRING, TX", sizeof(s_state.home_label));
  }
}

static void update_paleo_position(float minute, float age_ma) {
  if (!s_state.has_home) {
    s_state.home_alive = false;
    return;
  }

  uint16_t curr_age_x10 = (uint16_t)roundf(age_ma * 10.0f);
  if (curr_age_x10 > s_state.home_birth_ma_x10) {
    s_state.home_alive = false;
    return;
  }

  int pidx = pangaea_find_plate_idx(s_state.home_plate_id);
  if (pidx < 0) {
    s_state.home_alive = false;
    return;
  }

  int k_idx = 0;
  float t_frac = 0.0f;
  math_geo_find_bracket(minute, &k_idx, &t_frac);

  PangaeaQuat16 q0 = s_pangaea_rotations[k_idx][pidx];
  PangaeaQuat16 q1 = s_pangaea_rotations[k_idx + 1][pidx];
  bool has_q0 = !math_geo_quat_is_zero(q0);
  bool has_q1 = !math_geo_quat_is_zero(q1);

  Quat q;
  if (has_q0 && has_q1) {
    q = math_geo_quat_slerp(math_geo_quat_from_int16(q0),
                            math_geo_quat_from_int16(q1), t_frac);
  } else if (has_q0) {
    q = math_geo_quat_from_int16(q0);
  } else if (has_q1) {
    q = math_geo_quat_from_int16(q1);
  } else {
    s_state.home_alive = false;
    return;
  }

  float h_lat = (float)s_state.home_lat_x100 / 100.0f;
  float h_lon = (float)s_state.home_lon_x100 / 100.0f;
  Vec3 rotated_home = math_geo_quat_rotate_vec(q, math_geo_to_vec(h_lat, h_lon));
  math_geo_to_lat_lon(rotated_home, &s_state.paleo_lat, &s_state.paleo_lon);
  s_state.home_alive = true;

  // Approximate drift distance and rate from 252 Ma
  float frac_elapsed = minute / 1440.0f;
  s_state.drift_km = 4500.0f * frac_elapsed;
  s_state.drift_cmyr = 3.2f;
}

static void update_active_event(float minute, float age_ma) {
  s_state.active_event[0] = '\0';
  uint16_t age_x10 = (uint16_t)roundf(age_ma * 10.0f);

  for (int e = 0; e < PANGAEA_NUM_EVENTS; e++) {
    const PangaeaEvent *ev = &s_pangaea_events[e];
    // Check if within window
    if (ev->age_ma_x10 > PANGAEA_EXTINCTION_MA) {
      // Mesozoic events: window ~ 25 Ma (2.5 clock minutes)
      if (age_x10 <= ev->age_ma_x10 && age_x10 >= ev->age_ma_x10 - 25 && minute < (float)PANGAEA_LAST_MINUTE) {
        strncpy(s_state.active_event, ev->label, sizeof(s_state.active_event));
        return;
      }
    } else {
      // Cenozoic fast-forward events: window ~ 6 Ma (4 seconds)
      if (age_x10 <= ev->age_ma_x10 + 30 && age_x10 >= ev->age_ma_x10 - 30) {
        strncpy(s_state.active_event, ev->label, sizeof(s_state.active_event));
        return;
      }
    }
  }
}

static void handle_tick(struct tm *tick_time, TimeUnits units_changed);

static void check_tick_rate(struct tm *tick_time) {
  TimeUnits desired_unit = (tick_time->tm_hour == 23 && tick_time->tm_min == 59)
                           ? SECOND_UNIT : MINUTE_UNIT;
  if (desired_unit != s_current_tick_unit) {
    s_current_tick_unit = desired_unit;
    tick_timer_service_subscribe(s_current_tick_unit, handle_tick);
  }
}

static void update_state(struct tm *t) {
  s_state.hour = t->tm_hour;
  s_state.minute = t->tm_min;
  s_state.second = t->tm_sec;
  s_state.clock_time = time(NULL);

  float minute = (float)s_state.hour * 60.0f + (float)s_state.minute + (float)s_state.second / 60.0f;
  s_state.age_ma = math_geo_calc_age_at_minute(minute);

  int k_idx = 0;
  float t_frac = 0.0f;
  math_geo_find_bracket(minute, &k_idx, &t_frac);
  int nearest_k = t_frac < 0.5f ? k_idx : k_idx + 1;
  strncpy(s_state.period, s_pangaea_keyframes[nearest_k].period, sizeof(s_state.period));

  update_paleo_position(minute, s_state.age_ma);
  update_active_event(minute, s_state.age_ma);
}

static void handle_tick(struct tm *tick_time, TimeUnits units_changed) {
  check_tick_rate(tick_time);
  update_state(tick_time);
  layer_mark_dirty(s_canvas_layer);
}

static void canvas_update_proc(Layer *layer, GContext *ctx) {
  GRect bounds = layer_get_bounds(layer);
  pangaea_map_render(ctx, bounds, &s_state);
}

// ── AppMessage Handlers ──────────────────────────────────────────────────────

static void inbox_received_callback(DictionaryIterator *iterator, void *context) {
  Tuple *status_tuple = dict_find(iterator, MESSAGE_KEY_STATUS_MSG);
  if (status_tuple) {
    strncpy(s_state.status_msg, status_tuple->value->cstring, sizeof(s_state.status_msg));
  }

  Tuple *lat_tuple = dict_find(iterator, MESSAGE_KEY_HOME_LAT);
  Tuple *lon_tuple = dict_find(iterator, MESSAGE_KEY_HOME_LON);
  Tuple *label_tuple = dict_find(iterator, MESSAGE_KEY_HOME_LABEL);
  Tuple *plate_tuple = dict_find(iterator, MESSAGE_KEY_HOME_PLATE_ID);
  Tuple *birth_tuple = dict_find(iterator, MESSAGE_KEY_HOME_BIRTH_AGE);

  if (lat_tuple && lon_tuple && plate_tuple) {
    s_state.has_home = true;
    s_state.home_lat_x100 = (int16_t)lat_tuple->value->int32;
    s_state.home_lon_x100 = (int16_t)lon_tuple->value->int32;
    s_state.home_plate_id = plate_tuple->value->int32;
    if (birth_tuple) s_state.home_birth_ma_x10 = (uint16_t)birth_tuple->value->uint32;
    if (label_tuple) strncpy(s_state.home_label, label_tuple->value->cstring, sizeof(s_state.home_label));
    save_home_state();
  }

  Tuple *genus_tuple = dict_find(iterator, MESSAGE_KEY_FOSSIL_GENUS);
  if (genus_tuple) {
    s_state.fossil_found = true;
    strncpy(s_state.fossil_genus, genus_tuple->value->cstring, sizeof(s_state.fossil_genus));

    Tuple *group_tuple = dict_find(iterator, MESSAGE_KEY_FOSSIL_GROUP);
    if (group_tuple) strncpy(s_state.fossil_group, group_tuple->value->cstring, sizeof(s_state.fossil_group));

    Tuple *dist_tuple = dict_find(iterator, MESSAGE_KEY_FOSSIL_DIST_KM);
    if (dist_tuple) s_state.fossil_dist_km = (int16_t)dist_tuple->value->int32;

    Tuple *marine_tuple = dict_find(iterator, MESSAGE_KEY_FOSSIL_MARINE);
    if (marine_tuple) s_state.fossil_marine = (marine_tuple->value->uint8 != 0);
  }

  // Configuration options (12/24h and font colors)
  bool config_changed = false;
  Tuple *hour_mode_tuple = dict_find(iterator, MESSAGE_KEY_HOUR_MODE);
  if (hour_mode_tuple) {
    s_state.config.hour_mode = hour_mode_tuple->value->uint8;
    config_changed = true;
  }
  Tuple *col_time_tuple = dict_find(iterator, MESSAGE_KEY_COLOR_TIME);
  if (col_time_tuple) {
    s_state.config.color_time = col_time_tuple->value->int32;
    config_changed = true;
  }
  Tuple *col_taxon_tuple = dict_find(iterator, MESSAGE_KEY_COLOR_TAXON);
  if (col_taxon_tuple) {
    s_state.config.color_taxon = col_taxon_tuple->value->int32;
    config_changed = true;
  }
  Tuple *col_coords_tuple = dict_find(iterator, MESSAGE_KEY_COLOR_COORDS);
  if (col_coords_tuple) {
    s_state.config.color_coords = col_coords_tuple->value->int32;
    config_changed = true;
  }
  Tuple *col_age_tuple = dict_find(iterator, MESSAGE_KEY_COLOR_AGE);
  if (col_age_tuple) {
    s_state.config.color_age = col_age_tuple->value->int32;
    config_changed = true;
  }
  Tuple *col_ticker_tuple = dict_find(iterator, MESSAGE_KEY_COLOR_TICKER);
  if (col_ticker_tuple) {
    s_state.config.color_ticker = col_ticker_tuple->value->int32;
    config_changed = true;
  }
  Tuple *col_hdr_tuple = dict_find(iterator, MESSAGE_KEY_COLOR_HEADER);
  if (col_hdr_tuple) {
    s_state.config.color_header = col_hdr_tuple->value->int32;
    config_changed = true;
  }
  Tuple *col_foot_tuple = dict_find(iterator, MESSAGE_KEY_COLOR_FOOTER);
  if (col_foot_tuple) {
    s_state.config.color_footer = col_foot_tuple->value->int32;
    config_changed = true;
  }
  if (config_changed) {
    save_config_state();
  }

  time_t now = time(NULL);
  struct tm *t = localtime(&now);
  update_state(t);
  layer_mark_dirty(s_canvas_layer);
}

static void request_phone_update(void) {
  DictionaryIterator *iter;
  if (app_message_outbox_begin(&iter) == APP_MSG_OK) {
    dict_write_uint8(iter, MESSAGE_KEY_CMD, 1);
    app_message_outbox_send();
  }
}

// ── Window Lifecycle ────────────────────────────────────────────────────────

static void prv_window_load(Window *window) {
  Layer *window_layer = window_get_root_layer(window);
  GRect bounds = layer_get_bounds(window_layer);

  s_canvas_layer = layer_create(bounds);
  layer_set_update_proc(s_canvas_layer, canvas_update_proc);
  layer_add_child(window_layer, s_canvas_layer);

  pangaea_map_init();
  load_config_state();
  load_home_state();

  time_t now = time(NULL);
  struct tm *t = localtime(&now);
  check_tick_rate(t);
  update_state(t);
}

static void prv_window_unload(Window *window) {
  pangaea_map_deinit();
  layer_destroy(s_canvas_layer);
}

static void prv_init(void) {
  s_main_window = window_create();
  window_set_background_color(s_main_window, GColorBlack);
  window_set_window_handlers(s_main_window, (WindowHandlers){
    .load = prv_window_load,
    .unload = prv_window_unload,
  });
  window_stack_push(s_main_window, true);

  app_message_register_inbox_received(inbox_received_callback);
  app_message_open(256, 64);

  tick_timer_service_subscribe(s_current_tick_unit, handle_tick);
  request_phone_update();
}

static void prv_deinit(void) {
  tick_timer_service_unsubscribe();
  app_message_deregister_callbacks();
  window_destroy(s_main_window);
}

int main(void) {
  prv_init();
  app_event_loop();
  prv_deinit();
}
