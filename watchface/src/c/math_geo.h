#pragma once
#include <pebble.h>
#include "pangaea_data.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846f
#endif

typedef struct {
  float x, y, z;
} Vec3;

typedef struct {
  float w, x, y, z;
} Quat;

Vec3 math_geo_to_vec(float lat_deg, float lon_deg);
void math_geo_to_lat_lon(Vec3 v, float *out_lat, float *out_lon);

Quat math_geo_quat_from_int16(PangaeaQuat16 q16);
bool math_geo_quat_is_zero(PangaeaQuat16 q16);
Quat math_geo_quat_slerp(Quat a, Quat b, float t);
Vec3 math_geo_quat_rotate_vec(Quat q, Vec3 v);

GPoint math_geo_coord_to_screen(float lat, float lon, GRect map_rect);

float math_geo_calc_age_at_minute(float minute);
void math_geo_find_bracket(float minute, int *out_idx, float *out_t);

const char *math_geo_climate_band(float lat_deg);
