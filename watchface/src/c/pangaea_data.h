#pragma once
#include <pebble.h>

#define PANGAEA_NUM_VERTICES 1465
#define PANGAEA_NUM_PLATES 71
#define PANGAEA_NUM_KEYFRAMES 45
#define PANGAEA_NUM_EVENTS 21

#define PANGAEA_MAP_X 4
#define PANGAEA_MAP_Y 32
#define PANGAEA_MAP_W 192
#define PANGAEA_MAP_H 96

#define PANGAEA_START_MA 2520      // 252.0 * 10
#define PANGAEA_EXTINCTION_MA 660  // 66.0 * 10
#define PANGAEA_LAST_MINUTE 1439   // 23:59:00

typedef struct {
  int16_t lat_x100;
  int16_t lon_x100;
  uint8_t plate_idx;
  uint8_t pen_down;
  uint16_t birth_ma_x10;
} PangaeaVertex;

typedef struct {
  int16_t w, x, y, z;
} PangaeaQuat16;

typedef struct {
  uint16_t minute_x10; // e.g. 15.0 -> 150
  uint16_t age_ma_x10; // e.g. 252.0 -> 2520
  char period[20];
} PangaeaKeyframe;

typedef struct {
  uint16_t age_ma_x10;
  char label[28];
} PangaeaEvent;

extern const int32_t s_pangaea_plate_ids[PANGAEA_NUM_PLATES];
extern const PangaeaVertex s_pangaea_vertices[PANGAEA_NUM_VERTICES];
extern const PangaeaKeyframe s_pangaea_keyframes[PANGAEA_NUM_KEYFRAMES];
extern const PangaeaQuat16 s_pangaea_rotations[PANGAEA_NUM_KEYFRAMES][PANGAEA_NUM_PLATES];
extern const PangaeaEvent s_pangaea_events[PANGAEA_NUM_EVENTS];

// Find plate index from plate ID, returns -1 if not found
int pangaea_find_plate_idx(int32_t plate_id);
