#include "math_geo.h"
#include <math.h>

#define DEG_TO_RAD (M_PI / 180.0f)
#define RAD_TO_DEG (180.0f / M_PI)

Vec3 math_geo_to_vec(float lat_deg, float lon_deg) {
  float la = lat_deg * DEG_TO_RAD;
  float lo = lon_deg * DEG_TO_RAD;
  return (Vec3){
    cosf(la) * cosf(lo),
    cosf(la) * sinf(lo),
    sinf(la)
  };
}

void math_geo_to_lat_lon(Vec3 v, float *out_lat, float *out_lon) {
  float z = v.z;
  if (z < -1.0f) z = -1.0f;
  if (z > 1.0f) z = 1.0f;
  *out_lat = asinf(z) * RAD_TO_DEG;
  *out_lon = atan2f(v.y, v.x) * RAD_TO_DEG;
}

Quat math_geo_quat_from_int16(PangaeaQuat16 q16) {
  return (Quat){
    (float)q16.w / 32767.0f,
    (float)q16.x / 32767.0f,
    (float)q16.y / 32767.0f,
    (float)q16.z / 32767.0f
  };
}

bool math_geo_quat_is_zero(PangaeaQuat16 q16) {
  return (q16.w == 0 && q16.x == 0 && q16.y == 0 && q16.z == 0);
}

Quat math_geo_quat_slerp(Quat a, Quat b, float t) {
  float dot = a.w * b.w + a.x * b.x + a.y * b.y + a.z * b.z;
  Quat bb = b;
  if (dot < 0.0f) {
    dot = -dot;
    bb.w = -b.w;
    bb.x = -b.x;
    bb.y = -b.y;
    bb.z = -b.z;
  }
  if (dot > 0.9995f) {
    Quat q = {
      a.w + t * (bb.w - a.w),
      a.x + t * (bb.x - a.x),
      a.y + t * (bb.y - a.y),
      a.z + t * (bb.z - a.z)
    };
    float n = sqrtf(q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z);
    if (n > 0.0f) {
      q.w /= n; q.x /= n; q.y /= n; q.z /= n;
    }
    return q;
  }
  float th = acosf(dot);
  float sa = sinf((1.0f - t) * th) / sinf(th);
  float sb = sinf(t * th) / sinf(th);
  return (Quat){
    sa * a.w + sb * bb.w,
    sa * a.x + sb * bb.x,
    sa * a.y + sb * bb.y,
    sa * a.z + sb * bb.z
  };
}

Vec3 math_geo_quat_rotate_vec(Quat q, Vec3 v) {
  float cx = q.y * v.z - q.z * v.y;
  float cy = q.z * v.x - q.x * v.z;
  float cz = q.x * v.y - q.y * v.x;
  float ccx = q.y * cz - q.z * cy;
  float ccy = q.z * cx - q.x * cz;
  float ccz = q.x * cy - q.y * cx;
  return (Vec3){
    v.x + 2.0f * (q.w * cx + ccx),
    v.y + 2.0f * (q.w * cy + ccy),
    v.z + 2.0f * (q.w * cz + ccz)
  };
}

GPoint math_geo_coord_to_screen(float lat, float lon, GRect map_rect) {
  int16_t lo = (int16_t)roundf(lon);
  int16_t la = (int16_t)roundf(lat);
  if (lo < -180) lo += 360;
  if (lo > 180) lo -= 360;
  if (la < -90) la = -90;
  if (la > 90) la = 90;
  int16_t sx = map_rect.origin.x + (int16_t)(((int32_t)(lo + 180) * map_rect.size.w) / 360);
  int16_t sy = map_rect.origin.y + (int16_t)(((int32_t)(90 - la) * map_rect.size.h) / 180);
  return GPoint(sx, sy);
}

float math_geo_calc_age_at_minute(float minute) {
  if (minute <= (float)PANGAEA_LAST_MINUTE) {
    return 252.0f - (minute * (252.0f - 66.0f)) / (float)PANGAEA_LAST_MINUTE;
  }
  float end_min = (float)PANGAEA_LAST_MINUTE + 59.0f / 60.0f;
  float frac = (minute - (float)PANGAEA_LAST_MINUTE) / (end_min - (float)PANGAEA_LAST_MINUTE);
  if (frac > 1.0f) frac = 1.0f;
  if (frac < 0.0f) frac = 0.0f;
  return 66.0f * (1.0f - frac);
}

void math_geo_find_bracket(float minute, int *out_idx, float *out_t) {
  int i = 0;
  while (i < PANGAEA_NUM_KEYFRAMES - 2 && (s_pangaea_keyframes[i + 1].minute_x10 / 10.0f) <= minute) {
    i++;
  }
  float m0 = s_pangaea_keyframes[i].minute_x10 / 10.0f;
  float m1 = s_pangaea_keyframes[i + 1].minute_x10 / 10.0f;
  float span = m1 - m0;
  float t = span > 0.0f ? (minute - m0) / span : 0.0f;
  if (t < 0.0f) t = 0.0f;
  if (t > 1.0f) t = 1.0f;
  *out_idx = i;
  *out_t = t;
}

const char *math_geo_climate_band(float lat_deg) {
  float a = fabsf(lat_deg);
  if (a < 23.5f) return "TROPICS";
  if (a < 35.0f) return "SUBTROPICS";
  if (a < 60.0f) return "MID-LAT";
  return "HIGH-LAT";
}
