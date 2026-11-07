# Samsung TV for Home Assistant – H/J-series enhancements

> ⚠️ **Use at your own risk. Everyone has to know what they are doing.**
> This is an **unofficial** modified copy of Home Assistant's built-in
> `samsungtv` integration. It is **not** supported by the Home Assistant
> project or its maintainers — please do **not** report problems with this
> copy to home-assistant/core. It replaces the built-in integration while it is
> installed. It was written with the help of an AI assistant (Claude) and tested
> on exactly **one** TV (see below). Read the code before you install it.

## What it adds

For 2014/2015 Samsung **H/J-series** TVs that are paired with the
**encrypted** method (port 8000, PIN pairing), the built-in integration can
only send remote keys. On these TVs:

- the source list is a fixed `["TV", "HDMI"]`; `HDMI` just presses `KEY_HDMI`
  (cycles through inputs), `KEY_HDMI1..4` are ignored by the TV
  (see home-assistant/core#147250, #98646, #84912);
- the current source is never shown;
- volume / mute only update when the TV sends UPnP events, which H/J TVs often
  stop doing (e.g. while an HDMI input is active), so `volume_level` goes stale
  (compare home-assistant/core#190774, #134401).

This copy fixes that **only for models on an allow-list** (`HJ_ENHANCED_MODELS`
in `custom_components/samsungtv/const.py`, currently just `UE55H8000`):

| Feature | How |
|---|---|
| Real input list (`HDMI1`…`HDMI4`, `HDMI2/DVI`, `SCART`, `AV`, `COMPONENT`, `TV`) | `GetSourceList` of the Samsung UPnP service `urn:samsung.com:service:MainTVAgent2:1` |
| Current source (`source` attribute) | `GetCurrentExternalSource`, polled every 10 s with the existing coordinator |
| Direct input switching (`media_player.select_source`) | `SetMainTVSource(Source, ID, UiID=-1)`; on any error it falls back to the stock key behaviour |
| Fresh volume / mute | `GetVolume` / `GetMute` of the DLNA RenderingControl, polled every 10 s even while subscribed |

The `TV` and `HDMI` entries of the stock list are kept, so existing automations
keep working. Every model **not** on the allow-list behaves exactly like the
stock integration of Home Assistant 2026.11.0.

The MainTVAgent2 location (`ssdp_main_tv_agent_location`) has been discovered
and stored in the config entry by the stock integration since 2022
(home-assistant/core#68763, "so it can be used in a followup PR") but was never
used. Note that the TV answers these calls with UPnP error 501 until it has been
paired with the encrypted method.

## Tested on

| Model | Firmware | HA version | Result |
|---|---|---|---|
| UE55H8000 (`14_GOLFP`) | unknown | 2026.11.0 | input list, current source, `select_source` TV ↔ HDMI4, volume polling: all OK |

Power-on is still not possible over the network on these models (no
Wake-on-LAN in standby); use HDMI-CEC (Anynet+) from a connected device or an
IR blaster for that.

## Install

1. Copy `custom_components/samsungtv` into your Home Assistant `config/custom_components/`
   (or add this repository as a custom repository in HACS, type *Integration*).
2. Add your exact model to `HJ_ENHANCED_MODELS` in `const.py` if it is not
   `UE55H8000` — only after you understand the change. Your model string is
   shown in *Settings → Devices → your TV* or in the integration's diagnostics.
3. Restart Home Assistant. You get a log warning that a custom integration
   overrides `samsungtv` — that is expected. Your existing config entry is reused.

**Uninstall:** delete `config/custom_components/samsungtv` and restart. The
built-in integration takes over again with the same config entry.

**Version pinning:** this copy is based on the `samsungtv` code of Home
Assistant **2026.11.0** (`manifest.json` version `2026.11.0.hjN`). When you
update Home Assistant, the built-in integration may change; this copy does not
follow automatically. If something breaks after an HA update, uninstall it.

## What exactly was changed (vs. HA 2026.11.0)

- `main_tv_agent.py` (new): small async wrapper around the MainTVAgent2 UPnP
  service using `async_upnp_client` (already a dependency); parses the
  `SourceList` XML with `defusedxml`.
- `media_player.py`:
  - `__init__`: enables the enhancements only if `method == "encrypted"` **and**
    the model is in `HJ_ENHANCED_MODELS`.
  - `_async_extra_update` → `_async_hj_update`: polls DLNA volume/mute and the
    current input; fetches the input list once (retries while the TV answers
    501, gives up for good if the service does not exist).
  - `_update_sources`: stock `TV`/`HDMI` + real inputs + apps.
  - `async_select_source`: tries `SetMainTVSource` first, falls back to the
    stock key presses on error.
- `const.py`: `HJ_ENHANCED_MODELS`.
- `manifest.json`: `version`, `documentation`, `issue_tracker` (required for
  custom integrations), `quality_scale` removed.
- `translations/en.json`: generated from `strings.json` (custom integrations
  do not get Home Assistant's build-time string resolution).

All other files are unchanged copies from Home Assistant 2026.11.0.

## License

Home Assistant is licensed under the Apache License 2.0; this modified copy is
distributed under the same license (`LICENSE.md`). Modifications © 2026 the
repository owner, marked above. Not affiliated with Samsung, Nabu Casa or the
Open Home Foundation.
