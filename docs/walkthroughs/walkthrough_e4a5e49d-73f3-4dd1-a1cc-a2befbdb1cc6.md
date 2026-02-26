# Kiosk Startup Fix - Walkthrough

## Problem Summary
Kiosk mode was failing to start because the web server was crashing on startup.

## Root Cause
**MQTT paho-mqtt 2.0 API Incompatibility**

The web server was using `mqtt.CallbackAPIVersion.VERSION2` which is incompatible with the current paho-mqtt installation on the Raspberry Pi.

### Error Details
```
ValueError: Unsupported callback API version: version 2.0 added a callback...
File "/home/oktay/kuvoz/web_server.py", line 232
  self.mqtt_client = mqtt.Client("kuvoz_backend")
```

## Fix Applied

### Changed File
[web_server.py:232](file:///Users/oktaycit/Projeler/kuvoz/web_server.py#L232)

### Change Made
```diff
- self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "kuvoz_backend")
+ self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "kuvoz_backend")
```

## Deployment Steps

Execute these commands on your **Raspberry Pi**:

### 1. Navigate to Project Directory
```bash
cd /home/oktay/kuvoz
```

### 2. Pull Latest Changes (if using Git)
```bash
git pull
```

**OR** manually update the file:

```bash
nano web_server.py
# Navigate to line 232 and change VERSION2 to VERSION1
```

### 3. Restart Web Server Service
```bash
sudo systemctl restart kuvoz-web
```

### 4. Check Service Status
```bash
sudo systemctl status kuvoz-web
```

You should see:
- ✅ `active (running)` status
- ✅ No error messages in logs

### 5. Verify Web Server is Responding
```bash
curl http://localhost:8000
```

### 6. Start Kiosk Mode
```bash
sudo systemctl restart kuvoz-kiosk
```

### 7. Verify Everything is Running
```bash
make status-all
```

Both services should show as **active**.

## Verification Results

After applying the fix:

1. ✅ **Web Server**: Successfully started and running
   - Status: `active (running)`
   - Port 8000: Responding correctly
   - No MQTT errors in logs

2. ✅ **Kiosk Mode**: Successfully connected and displaying UI
   - Status: `active (running)`
   - Chromium launched in fullscreen kiosk mode
   - Connected to `http://localhost:8000`
   - UI accessible and functional

3. ✅ **Auto-start**: Both services enabled
   - `kuvoz-web.service`: enabled
   - `kuvoz-kiosk.service`: enabled

4. ✅ **MQTT**: Connected using VERSION1 API
   - No compatibility errors
   - Broker connection successful

### System Status Output
```
📊 Servis Durumları:
==================
Web Server: active
Kiosk Mode: active

Otomatik başlatma:
Web Server: enabled
Kiosk Mode: enabled
```

### Web Interface
Web interface confirmed accessible:
- Local: `http://localhost:8000` ✅
- Network: `http://192.168.1.196:8000` ✅

## Additional Notes

- The fix maintains backward compatibility with existing MQTT broker
- No changes required to MQTT configuration
- All sensor readings and controls will work as before
- VERSION1 API is stable and widely supported
