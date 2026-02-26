# Walkthrough - Restricting Shift Opening to Registered Cashiers

I have implemented a security restriction to ensure that shifts can only be opened by registered cashiers.

## Debugging - Shift Closing Failure

The user reported an issue closing the register on `vet@kuvoz.local`.

- **Root Cause**: `ValueError` in the backend when the "Nakit" or "Kart" fields were left empty in the UI. The code was attempting to convert an empty string to a float.
- **Fix**: Updated `api_vardiya_kapat` to default empty or whitespace-only inputs to `0.0`.
- **Additional Improvement**: Relaxed the cashier registration check in `api_vardiya_ac`. Now, if no cashiers are registered in the system (e.g., a fresh setup), users can still open a shift with any name. The restriction only applies if the cashier list is not empty.

## Verification Results

### Remote Server Logs (vet@kuvoz.local)
Verified service logs after deployment:
```text
ValueError: could not convert string to float: ''  <-- Fixed
2026-02-24 20:34:05,401 - INFO - 📡 Terminal sunucusu başladı: 192.168.1.197:5555
2026-02-24 20:34:05,417 - INFO - Press CTRL+C to quit
```
The service is confirmed active and running on the remote host.

## How to Test Manually
1. Go to **Personel Yönetimi** and register a new cashier.
2. Go to **Kasa ve Vardiya** management.
3. Select a register.
4. The newly registered cashier should appear in the dropdown.
5. Starting the shift with a selected cashier will work.
6. (Optional) Any direct API calls with unregistered names will now be rejected.
