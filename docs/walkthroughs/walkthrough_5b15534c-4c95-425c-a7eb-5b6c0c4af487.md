# Walkthrough: Cloud MQTT Bridge Implementation

I have implemented a secure way to access your Kuvoz device from an external network (Mobile App) without modifying your router settings, using a **Cloud MQTT Bridge**.

## Changes

1.  **New Script**: [`scripts/setup_cloud_bridge.sh`](file:///Users/oktaycit/Projeler/kuvoz/scripts/setup_cloud_bridge.sh)
    -   This interactive script helps you configure the connection to a cloud provider.
2.  **Configuration Template**: [`config/cloud_bridge.conf.template`](file:///Users/oktaycit/Projeler/kuvoz/config/cloud_bridge.conf.template)
    -   Mosquitto bridge configuration pattern.
3.  **Documentation**: [`CLOUD_BRIDGE_README.md`](file:///Users/oktaycit/Projeler/kuvoz/CLOUD_BRIDGE_README.md)
    -   Step-by-step guide to signing up for a broker and setting this up.
4.  **Plan Update**: Updated `MOBILE_APP_PLAN.md` to reference this new method.

## How to Verify and Use

1.  **Sign Up**: Get a free account at [HiveMQ Cloud](https://www.hivemq.com/mqtt-cloud-broker/) (or AWS IoT, etc.).
2.  **Run Setup**:
    ```bash
    cd ~/kuvoz
    sudo ./scripts/setup_cloud_bridge.sh
    ```
3.  **Enter Details**: Provide the URL, Username, and Password when prompted.
4.  **Connect App**: Point your Mobile App to the same Cloud Broker URL.

## Technical Details

-   **Security**: The bridge uses an outbound connection (port 8883 usually), so no incoming ports need to be opened on your router.
## Mobile App (React)

I have also created a simple **Mobile Dashboard** for you.

### Features
-   **Direct Cloud Connection**: Connects to HiveMQ Cloud.
-   **Real-time Dashboard**: Shows Temperature, Humidity, Oxygen.
-   **Controls**: Toggle buttons for all device functions.

### How to Use
1.  **Access the Public Link**:
    -   Open: [https://oktaycit.github.io/Kuvoz/](https://oktaycit.github.io/Kuvoz/)
    -   You can open this on any phone, anywhere.
2.  **Connect**:
    -   Enter your **HiveMQ Cloud** credentials.
    -   Click "Connect".

### Connection Loops
If looking at logs (`tail -f /var/log/mosquitto/mosquitto.log`) shows the bridge connecting and immediately disconnecting:
-   This is often due to `try_private true` (default). Cloud brokers usually require `try_private false`.
-   We have set this correctly in the default template now.

### Protocol Version Error
If logs show `Invalid bridge_protocol_version`:
-   Ensure the config uses `mqttv311` (with the 'v') and not `mqtt311`. This has been fixed in the template.
