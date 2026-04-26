# resources folder

This directory contains all files that are in resources.gpak, but extracted so they can be searched easily. Original `resources.gpak` included just in case - avoid opening or searching it when you can use the extracted content instead. They were extracted using: https://mewgpaks.netlify.app/

All content from `resources.gpak` is divided between 5 categories:

- **Audio** - extracted to `gpak-audio/audio/`. Music and sound files (compressed audio assets).
- **Image** - extracted to `gpak-image/textures/`. Sprite sheets and image assets used by the game's renderer.
- **Other** - extracted to `gpak-other/` with multiple subdirectories:
  - `gpak-other/audio/music/` - MIDI files; appear to enable cats to sing along to the main music tracks in-game.
  - `gpak-other/data/` - binary data files (e.g. `furniture_info.data`).
  - `gpak-other/levels/` - level layout files (`.lvl`), one per map/encounter area.
  - `gpak-other/shaders/` - GLSL/shader source files used by the game's rendering pipeline.
- **Text** - extracted to `gpak-text/` with multiple subdirectories. The most useful category for reverse engineering:
  - `gpak-text/data/` - GON and TXT game data files: abilities, mutations, classes, catnames, difficulty settings, room/furniture definitions, etc. **Primary lookup source for parser work.**
  - `gpak-text/audio/` - GON files describing SFX and music cues (`combat_sfx.gon`, `house_sfx.gon`, `ui_sfx.gon`), plus voice/NPC audio manifests.
  - `gpak-text/swfs/` - `swflist.gon`, a manifest of SWF assets.
  - `gpak-text/textures/cursor/` - cursor texture definitions.
- **Video** - extracted to `gpak-video/swfs/`. SWF animation files for cat parts, ability icons, backgrounds, bosses, UI elements, etc.


