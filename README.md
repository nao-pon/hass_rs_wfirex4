# RS-WFIREX4 Integration for Home Assistant

RS-WFIREX4 is a custom Home Assistant integration for controlling **RS-WFIREX4 devices**.

This integration now supports configuration via the **Home Assistant UI**, eliminating the need to edit `configuration.yaml`.

## Features

* Control RS-WFIREX4 infrared learning remote devices
* Monitor temperature, humidity, and illuminance sensors
* UI-based configuration for easy setup
* Automatic state updates
* Configurable scan interval

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant.
2. Go to **Integrations → Explore & Download Repositories**.
3. Search for `RS-WFIREX4` and install it.
4. Restart Home Assistant.

### Manual Installation

1. Download the repository.
2. Copy the contents of the `custom_components/rs_wfirex4` folder into your Home Assistant `custom_components/rs_wfirex4` directory.
3. **Restart Home Assistant** to load the new integration.

> **Note:** Restarting Home Assistant is required after manually adding files to `custom_components`.

## Configuration

### UI Setup

1. Go to **Settings → Devices & Services → Add Integration**.

2. Search for `RS-WFIREX4` and click **Configure**.

3. Fill in the following fields:

   * **Host**: IP address of your RS-WFIREX4 device
   * **MAC Address**: MAC address of the device
   * **Name**: Friendly name for this device
   * **Scan Interval**: Polling interval in seconds (optional)

4. Click **Submit** to complete the setup.

> **Note:** Previously, configuration required editing `configuration.yaml`. This is no longer necessary.

### Options

Once the integration is added, you can adjust options such as scan interval via the **Integration Options** in Home Assistant UI.

## Troubleshooting

* Make sure your RS-WFIREX4 device is reachable on your network.
* If devices do not appear, try restarting Home Assistant.
* For network issues, check your firewall and router settings.

## Contributing

Feel free to open issues or pull requests in this repository.

