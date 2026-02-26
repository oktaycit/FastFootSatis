# Walkthrough: Fixing Dashboard Kasa Status

## The Issue
The user reported that the dashboard in `vet@kuvoz.local` showed "Kasa Kapalı" (Register Closed) even though an active cash register shift was currently open.

## Investigation & Root Cause
After inspecting the frontend `script.js` and checking the SocketIO communication patterns, I determined that when the dashboard connects, it issues a `set_kasa` event to the `web_server.py`. 

The server processes this event and calls `get_sid_active_shift` to send a `vardiya_update` back to the frontend to ensure its state is correct. However, `db.get_active_shift_by_kasa(kasa_id)` returned dictionary keys with `datetime` objects.

Since Python's `datetime` objects are not natively JSON-serializable, `flask_socketio` was encountering an unhandled exception when attempting to emit the payload `emit('vardiya_update', ...)`. The process would crash silently for that specific event, preventing the dashboard from ever getting the actual status.

## Resolution
1. Modified `web_server.py` `get_sid_active_shift` function.
2. Formatted `acilis_zamani` and `kapanis_zamani` utilizing the `.isoformat()` method when retrieving the active shift.
3. Restarted the background `web_server.py` and validated that the startup sequence succeeds and socket connections establish normally, confirming that the JSON serialization crash is fixed.

```python
        shift = db.get_active_shift_by_kasa(kasa_id)
        if shift:
            shift_dict = dict(shift)
            if 'acilis_zamani' in shift_dict and hasattr(shift_dict['acilis_zamani'], 'isoformat'):
                shift_dict['acilis_zamani'] = shift_dict['acilis_zamani'].isoformat()
            if 'kapanis_zamani' in shift_dict and hasattr(shift_dict['kapanis_zamani'], 'isoformat'):
                shift_dict['kapanis_zamani'] = shift_dict['kapanis_zamani'].isoformat()
            return shift_dict
```

## Additional Issue & Resolution
When deploying the `datetime` fix to `vet@kuvoz.local`, the dashboard still did not update because the active shift had financial metadata attached. The database columns `acilis_bakiyesi`, `kapanis_nakit`, and `kapanis_kart` are of type `Decimal`. Like `datetime`, `Decimal` is also not natively JSON-serializable in Python.

Consequently, `get_sid_active_shift` was modified again to also explicitly convert any `Decimal` fields to standard floating-point numbers (`float`). 

```python
            # Decimal değerleri float'a çevir
            for key in ['acilis_bakiyesi', 'kapanis_nakit', 'kapanis_kart']:
                if key in shift_dict and isinstance(shift_dict[key], Decimal):
                    shift_dict[key] = float(shift_dict[key])
```

## Final Verification
After deploying this additional serialization fix to the remote server and correctly restarting the background Python process without permission denials or port conflicts, the dashboard successfully received the SocketIO payloads.

The header now properly dynamically updates with the cashier's name and the Open status `Hasan (Açık)` upon navigating to the site.

![Dashboard Verification](/Users/oktaycit/.gemini/antigravity/brain/1cb9d0ad-116a-47f1-bb23-a466b352a91a/kasa_acik.png)
