---
generated_by: "Claude Code CLI (claude-opus-5-5)"
timestamp: "2026-10-02T15:40:00-05:00"
---

# Build & Preview

```bash
source .venv/bin/activate
python3 execution/build_deep_time_data.py --dry-run   # keyframe schedule, no network
python3 execution/build_deep_time_data.py             # uses .tmp/cache/
python3 execution/build_deep_time_data.py --refresh   # re-fetch everything
python3 -m pytest tests -q
python3 -m http.server 8765                           # then http://localhost:8765/?t=17:00:00
```

- `?t=HH:MM:SS` pins the preview clock (used for headless screenshots); no param = live time
- Headless shot: `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new
  --window-size=1000,700 --virtual-time-budget=4000 --screenshot=$PWD/.tmp/shots/x.png URL`
- Cache keys must encode every request parameter; bump the `pbdb_vN_` prefix when PBDB params change
- Full run from cache ≈ 1 s; cold ≈ 20 s
