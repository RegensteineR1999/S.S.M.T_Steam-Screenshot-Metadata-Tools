# SSMT (Steam Screenshot Metadata Tool) - Weekend AI Experiment

![Mein Screenshot](Screenshot%202026-05-02%20034317.png)



Quick Python/Tkinter tool (~1000 lines) to edit Steam's `screenshots.vdf`: Add locations/tags ~~for Workshop uploads~~, preview images, per-AppID filter. Started with Arknights: Endfield screenshots (added as Non-Steam game). Pure weekend hack to test AI coding assistants.

## Features
- Load/edit multiple Steam users' VDF files
- Per-AppID dropdown + "Open game folder" button
- Metadata editor: Location, ~~Steamusertags, Workshop prep~~
- Image preview, status colors (Local/Imported/Published)
- Timestamped backups, safety warnings ("Close Steam first!")
- ~~Sort by Created/Location~~ (falls back to Steam order)

## Quickstart
1. Close Steam completely (avoids VDF files corruption).
2. Run `python stamp_v1.0-alpha.py` ~~(or EXE)~~.
3. Pick user/AppID → Load entries → Edit → Apply.

**Requirements**: Python 3.12+, Pillow (for previews: `pip install pillow`).

## Changelog
See [CHANGELOG.md](CHANGELOG.md) for full Alpha 1–20 history.

## Lessons Learned: AI Coding Fail

In Alpha 18/19, a leftover debug snippet haunted the score_vdf_candidate() function: if 'Endfield' in text: score += 25. This came from  first tests with non Steam games like Arknights: Endfield for AppID 431960,. I asked 4-5 times to remove it – each time got "I've changed it," but nothing happened. Code stayed identical. Only switching to Claude model finally killed it, though by then everything was reset like in "final2build"See:https://github.com/RegensteineR1999/Steam-Screenshot-Metadata-Tool/releases/tag/v.0.9.20xxx.

Leftovers and Debug Junk
The code was littered with self-made debug crap: High scores for "Endfield" strings, unused prints, indentation errors in replaces, and old stress-test leftovers. Simple tasks like "German to English" for UI text (e.g., "without creating a backup" to "Location metadata apply") failed hard – translations missing or breaking sorting. Plus straight-up lies like "Endfield is gone now" when it was still there.

Why So Catastrophic?
AI models hallucinate on code: They claim changes happened ("replace() worked"), but don't actually check indentation matches or if the file is clean. At 1000 lines small? Remarkable – shows how probabilistic these things are, especially with booleans or file edits.



## License
CC0 (public domain).

**Archived weekend project. No further updates planned.**
