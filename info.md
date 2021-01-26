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

- For sensors entity:
```
sensor:
  - platform: rs_wfirex4
    host: "xxx.xxx.xxx.xxx" # IP address of your RS-WFIREX4
    name: "Living sensors"  # Optional
```

- For remote entity:
```
remote:
  - platform: rs_wfirex4
    host: "xxx.xxx.xxx.xxx"         # IP address of your RS-WFIREX4
    name: "Living remote commander" # Optional
```
This remote entity can be used in much the same way as [Broadlink's remote](https://www.home-assistant.io/integrations/broadlink/#remote) entity.