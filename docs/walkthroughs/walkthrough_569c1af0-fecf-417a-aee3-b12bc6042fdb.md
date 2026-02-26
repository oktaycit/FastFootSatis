# Walkthrough: Caller ID Integration & Customer Tracking

I have successfully integrated the "Signal 7" Caller ID system and expanded customer tracking capabilities.

## Changes Made

### 🗄️ Database Updates
- Added `telefon` and `adres` fields to the `cari_hesaplar` table.
- Implemented `get_cari_by_phone` and `get_customer_order_history` functions in `database.py`.
- Updated `init_database` with migration logic to ensure existing databases are updated.

### ⚙️ Backend Enhancements
- **Multi-Protocol Support**: Implemented a `CallerIDListener` that supports both TCP (Port 101) and Serial (USB/Arduino) connections.
- **PTTAVM Modem Compatibility**: Specifically tuned to handle the `01 N {phone}` format used by popular 2-line modems.
- **Auto-Reconnection**: The serial listener automatically attempts to reconnect if the device is unplugged.
- **New API Endpoints**:
    - `/api/settings`: Now includes Caller ID configuration.
    - `/api/serial/ports`: Returns a list of available COM ports for easy configuration.

### 💻 Frontend (Web Interface)
- **Settings UI**: A new "Caller ID Ayarları" card in the settings page allows you to:
    - Enable/Disable the service.
    - Choose between Ethernet (TCP) or USB (Serial).
    - Select from a list of detected COM ports.
- **Incoming Call Popup**: Premium UI with customer name, phone, address, and balance.
- **Order History**: Shows last 5 orders of the caller.

## Visual Demonstrations

### Caller ID Configuration (Settings)
You can now configure your device directly from the interface:
1. Go to **Ayarlar**.
2. Scroll to **Caller ID Ayarları**.
3. Select **USB / Seri Port** and pick your device (e.g., `COM3`).

> [!TIP]
> Use the 🔄 button next to the port selection to refresh the list of connected USB devices.

## Verification Results
- [x] TCP Signal 7 simulation successful.
- [x] Serial port discovery API verified.
- [x] PTTAVM "01 N" format parser tested with mock data.
- [x] Settings persistence verified.

## How to Test
1. Connect your PTTAVM Modem to a USB port.
2. Open the **Ayarlar** page in FastFoot.
3. Enable Caller ID and select the correct COM port.
4. Call your line; the "Gelen Çağrı" alert will appear instantly.
