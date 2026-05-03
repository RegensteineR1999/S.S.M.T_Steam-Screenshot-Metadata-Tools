# Steam Screenshot Metadata Tool

A small tool for viewing and editing Steam screenshot metadata in `screenshots.vdf`

This started as a niche weekend project to make it easier to add or restore metadata for non-Steam or external screenshots inside Steam's screenshot library.

## Why it exists

**First and foremost:
Especially wanted to test before Half-Life 3 drops how well you can get by in 2026 just by chatting with these 'smart and badass AIs'... I'm really curious (Spoilers, It was a very strange experience)**

Steam's screenshot system supports extra metadata such as location names, tagged users, and tagged workshop files. Valve documents this here:

- [ISteamScreenshots Interface](https://partner.steamgames.com/doc/api/isteamscreenshots)
- [Steam Screenshots API](https://partner.steamgames.com/doc/features/screenshots)


This tool gives that metadata a simple GUI, mainly for people who want to work with Images/Screenshots outside the usual Steam workflow.

## Features

- Open and parse `screenshots.vdf`
- Auto-detect the active `screenshots.vdf` path
- Browse screenshots by AppID / game
~~- Choose a startup view for the list~~
- Preview the selected screenshot
- Filter entries with `Published only` & `Unpublished only`
- Show raw VDF states such as `Published`, `imported=1`, or `no import flag`
- Edit metadata fields directly in the VDF
- Create manual backups when needed
- Reveal the selected file in Explorer

## Notes

- Install Pillow (Python Imaging Library) if you want the built-in screenshot preview to work. Without it, the tool can still read and edit metadata, but image preview is disabled.
- `imported=1` is shown as a raw VDF state and should not automatically be read as "externally added"
  
~~- `Published` is treated separately when a screenshot has a published file id~~
  

## Usage

1. Start the script with Python.
2. Use Auto-detect or load a `screenshots.vdf` file manually.
3. Select an AppID
5. Optionally change the startup view or use the published filters.
6. Select a screenshot entry.
7. Edit the metadata field.
8. Click **Apply** to save the change.
9. Use **Backup** only when you want a manual safety copy.

## Status

This project is still in alpha. ~~More metadata fields may be added (maybe) later, including workshop-related fields and tagged Steam users.~~

## Transparency

AI was used as a development aid for parts of the coding, UI iteration, wording, and troubleshooting.  
Direction, testing, and project goals were still set by me.

No enterprise-grade setup here – just regular language models like ChatGPT, Perplexity or Copilot.  
Worked in a single chat window with interruptions, copy-paste style.
