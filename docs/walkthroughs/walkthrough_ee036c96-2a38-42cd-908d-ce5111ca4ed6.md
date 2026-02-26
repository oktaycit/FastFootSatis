# Sensor Data Logging - Walkthrough

## Summary

Change-based sensor data logging implemented on branch `feature/sensor-data-logging`.

## Changes Made

### New Files
- [`lib/data/sensor_logger.py`](file:///Users/oktaycit/Projeler/kuvoz/lib/data/sensor_logger.py) - SQLite-based logger
- [`lib/data/__init__.py`](file:///Users/oktaycit/Projeler/kuvoz/lib/data/__init__.py) - Module init

### Modified Files
- [`web_server.py`](file:///Users/oktaycit/Projeler/kuvoz/web_server.py) - SensorLogger integration

render_diffs(file:///Users/oktaycit/Projeler/kuvoz/web_server.py)

## How It Works

```
Sensor Reading (every 15s)
        ↓
    Value Changed?  ──No──→ Skip
        ↓ Yes
    Log to SQLite
```

**Thresholds:**
| Sensor | Threshold |
|--------|-----------|
| Temperature | ±0.5°C |
| Humidity | ±2% |
| Oxygen | ±0.5% |
| CO2 | ±50 ppm |

## Test Results

```
✅ SensorLogger import OK
First log: True         ← Initial values logged
Same data log: False    ← Unchanged, skipped
Changed data log: True  ← Temperature changed 0.6°C, logged
Record count: 2
```

## Database Location

```
data/sensor_logs.db
```

## Next Steps

```bash
# Merge to main branch
git checkout main
git merge feature/sensor-data-logging

# Or push to remote
git push -u origin feature/sensor-data-logging
```
