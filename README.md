[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

# Sensor fetcher and IR contoroler for RS-WFIREX4

A custom componet of Home Assistant to use RS-WFIREX4. This component is still under development. Do not use it in a production environment.

## Installation & configuration
You can install this component in two ways: via HACS or manually.

### Option A: Installing via HACS
If you have HACS, you must add this repository ("https://github.com/nao-pon/hass_rs_wfirex4") to your Custom Repository 
selecting the Configuration Tab in the HACS page.
After this you can go in the Integration Tab and search the "RS-WFIREX4" component to configure it.

### Option B: Manually installation (custom_component)
1. Clone the git master branch.
2. Unzip/copy the tuya_custom direcotry within the `custom_components` directory of your homeassistant installation.
The `custom_components` directory resides within your homeassistant configuration directory.
Usually, the configuration directory is within your home (`~/.homeassistant/`).
In other words, the configuration directory of homeassistant is where the configuration.yaml file is located.

### Entity parameters (configuration.yaml)

```
rs_wfirex4:
  - host: "xxx.xxx.xxx.xxx"   # IP address of your first RS-WFIREX4
    mac : "xx:xx:xx:xx:xx:xx" # Optional MAC Address of this device (Recommend to set for device identification)
    name: "Living Wfirex4"    # Optional entity name
    scan_interval: 30         # Optional seconds of scan interval (Default 60)

  - host: "xxx.xxx.xxx.xxx"   # IP address of your second RS-WFIREX4
    mac : "xx:xx:xx:xx:xx:xx" # Optional MAC Address of this device (Recommend to set for device identification)
    name: "Living Wfirex4"    # Optional entity name
    scan_interval: 30         # Optional seconds of scan interval (Default 60)
```
You can find entities that four sensors and one remote.

This remote entity can be used in much the same way as [Broadlink's remote](https://www.home-assistant.io/integrations/broadlink/#remote) entity.