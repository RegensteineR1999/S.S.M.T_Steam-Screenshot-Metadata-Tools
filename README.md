# Steam Screenshot Metadata Tool

A small tool for viewing and editing Steam screenshot metadata in `screenshots.vdf`.

This started as a niche weekend project to make it easier to add or restore metadata for non-Steam or external screenshots inside Steam's screenshot library.

## Why it exists

Steam's screenshot system supports extra metadata such as location names, tagged users, and tagged workshop files. Valve documents this here:

- [ISteamScreenshots Interface](https://partner.steamgames.com/doc/api/isteamscreenshots)
- [Steam Screenshots API](https://partner.steamgames.com/doc/features/screenshots)


This tool gives that metadata a simple GUI, mainly for people who want to work with Images/Screenshots outside the usual Steam workflow.

## Features

- Open and parse `screenshots.vdf`
- Browse screenshots by AppID / game
- Preview the selected screenshot
- Show raw VDF states such as `Published`, `imported=1`, or `no import flag`
- Edit metadata fields directly in the VDF
- Create manual backups when needed
- Reveal the selected file in Explorer

## Notes

- `imported=1` is shown as a raw VDF state and should not automatically be read as "externally added"
- `Published` is treated separately when a screenshot has a published file id
- Pillow (`PIL`) is required for image preview support

## Usage

1. Start the script with Python.
2. Load your `screenshots.vdf` file.
3. Select an AppID
4. Select a screenshot entry.
5. Edit the metadata field.
6. Click **Apply** to save the change.
7. Use **Backup** only when you want a manual safety copy.

## Status

This project is still in alpha. More metadata fields may be added (maybe) later, including workshop-related fields and tagged Steam users.

## Transparency

AI was used as a development aid for parts of the coding, UI iteration, wording, and troubleshooting.

Direction, testing, and project goals were still set by me.