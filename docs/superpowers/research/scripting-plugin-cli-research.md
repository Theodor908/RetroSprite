# Scripting/Plugin API & CLI Batch Export Research

Research date: 2026-03-11

---

## 1. Aseprite Lua Scripting API

### Object Model
Aseprite exposes a rich hierarchy of Lua objects:
- **app** — Global entry point. Properties: `app.sprite`, `app.layer`, `app.cel`, `app.frame`, `app.image`, `app.palette`, `app.range`, `app.site`, `app.tool`, `app.editor`
- **Sprite** — The document. Has layers, frames, cels, palette, tags, slices, tilesets
- **Layer** — Layer in the layer stack. Properties: name, opacity, blendMode, isVisible, isEditable, parent (for groups)
- **Frame** — A specific point in time. Has frameNumber, duration
- **Cel** — The intersection of a layer and frame. Has image, position, opacity
- **Image** — Pixel data. Has width, height, colorMode. Methods: `getPixel()`, `putPixel()`, `drawSprite()`, `drawImage()`
- **Palette** — Color palette. Has `getColor(index)`, `setColor(index, color)`, `resize()`
- **Selection** — Selection mask
- **Dialog** — UI dialog builder with widgets (label, button, slider, color, entry, combobox, check, radio, file, canvas)

### Plugin Registration
Plugins are folders with `package.json`:
```json
{
  "name": "my-plugin",
  "displayName": "My Plugin",
  "description": "...",
  "version": "1.0",
  "scripts": ["main.lua"]
}
```

Register commands via:
```lua
function init(plugin)
  plugin:newMenuGroup{
    id = "my_menu",
    title = "My Menu",
    group = "edit_menu"
  }
  plugin:newCommand{
    id = "my_command",
    title = "Do Something",
    group = "my_menu",
    onclick = function() ... end
  }
end
```

### Events/Hooks
- `app.events:on('sitechange', fn)` — active sprite/layer/frame changed
- `app.events:on('beforecommand', fn)` — before any command executes (can inspect command name + params)
- `app.events:on('aftercommand', fn)` — after command executes
- `sprite.events:on('change', fn)` — sprite modified

### Plugin Preferences
`plugin.preferences` is a table auto-persisted between sessions. Plugins can store settings there.

### Key Takeaways
- **Simple object hierarchy** mirroring the document model
- **Command registration** with menu placement via group IDs
- **Event system** for reactive plugins
- **Dialog builder** for plugin UI
- **Persistent preferences** per plugin

---

## 2. GIMP Plugin System (Script-Fu / Python-Fu)

### Plugin Registration (GIMP 3 / Python)
Plugins subclass `Gimp.PlugIn`:
```python
class MyPlugin(Gimp.PlugIn):
    def do_query_procedures(self):
        return ["my-procedure-name"]

    def do_create_procedure(self, name):
        procedure = Gimp.ImageProcedure.new(self, name, ...)
        procedure.set_menu_label("My Filter")
        procedure.set_menu_path("<Image>/Filters/MyMenu")
        procedure.add_argument_from_property(self, "radius")
        return procedure

    def run(self, procedure, run_mode, image, drawables, config, data):
        # actual work here
        ...

Gimp.main(MyPlugin.__gtype__, sys.argv)
```

### Key Concepts
- **PDB (Procedural DataBase):** Every registered procedure gets a name and becomes callable by any other plugin or script. This is the universal interface.
- **Menu paths:** Plugins specify where they appear via path strings like `"<Image>/Filters/Blur"`
- **Run modes:** `INTERACTIVE` (show dialog), `NONINTERACTIVE` (scripted), `WITH_LAST_VALS` (repeat)
- **Arguments:** Declared as typed parameters during registration
- **File layout:** Plugin must be in `~/.config/GIMP/3.0/plug-ins/myplugin/myplugin.py`

### Key Takeaways
- **PDB is brilliant:** Every operation is a named procedure with typed args, callable from any language
- **Menu path strings** for placement
- **Run modes** distinguish interactive vs scripted usage
- **Heavy introspection** — you can enumerate all procedures and their args

---

## 3. Pixelorama Extension System

### Extension Structure
Extensions are `.pck` files (Godot packed scenes) with:
```json
// extension.json
{
  "name": "my_extension",
  "display_name": "My Extension",
  "description": "...",
  "author": "...",
  "version": "1.0",
  "supported_api_versions": [4],
  "license": "MIT",
  "nodes": ["Main.tscn"]
}
```

### API Access
```gdscript
# Main.gd
var api = get_node_or_null("/root/ExtensionsApi")
```

### Available Sub-APIs (proposed/evolving)
- **GeneralAPI** — app-level operations
- **ThemeAPI** — UI theme/color access
- **DialogAPI** — show dialogs
- **MenuAPI** — add menu bar options
- **ExportAPI** — custom export formats
- **ToolAPI** — custom drawing tools
- **SelectionAPI** — selection operations

### Key Takeaways
- **Godot scene-based** — extensions are Godot scenes/scripts
- **Single entry point** via `ExtensionsApi` node
- **Namespaced sub-APIs** for different concerns
- **Still evolving** — API surface expanding based on community needs
- **Lesson:** Start with a small, well-defined API and expand based on demand

---

## 4. ImageMagick CLI Patterns

### Command Structure (v7)
```
magick [input] [settings] [operators] [output]
```

### Key Operations
```bash
# Format conversion
magick input.png output.jpg

# Resize
magick input.png -resize 50% output.png
magick input.png -resize 128x128 output.png
magick input.png -resize 128x128! output.png   # force exact (ignore aspect)

# Multiple operations chained
magick input.png -resize 200% -flip -rotate 90 output.png

# Batch processing with mogrify (modifies in-place)
magick mogrify -resize 50% -format png *.jpg

# Color operations
magick input.png -colorspace Gray output.png
magick input.png -colors 16 output.png

# Sprite sheet (montage)
magick montage frame*.png -tile 4x4 -geometry 32x32+0+0 spritesheet.png
```

### CLI Flag Patterns
- **Settings** persist until overridden: `-quality 90`, `-background transparent`
- **Operators** apply immediately: `-resize`, `-flip`, `-rotate`, `-crop`, `-blur`
- **Input/Output** are positional: first file is input, last is output
- **Geometry strings:** `WxH`, `WxH!` (force), `WxH>` (only shrink), `WxH^` (minimum), `%`
- **Globbing:** `*.png` for batch input

### Key Takeaways
- **Pipeline pattern:** input -> chain of operations -> output
- **Verb-based flags** for operations (`-resize`, `-rotate`, `-flip`, `-crop`)
- **Geometry mini-language** for sizes
- **`mogrify` vs `convert`** — in-place vs new file
- **Format auto-detection** from file extension

---

## 5. Krita Python Scripting

### Entry Points
```python
from krita import *

# Global instance
app = Krita.instance()

# Get active document
doc = app.activeDocument()

# Get active node (layer)
node = doc.activeNode()
```

### Object Model
- **Krita** (singleton) — `activeDocument()`, `documents()`, `createDocument()`, `openDocument()`, `action(name)`
- **Document** — `rootNode()`, `activeNode()`, `nodeByName()`, `createNode(name, type)`, `width()`, `height()`, `setWidth()`, `exportImage()`, `save()`, `setBatchmode(True)`
- **Node** (= Layer) — `name()`, `type()`, `setVisible()`, `opacity()`, `blendingMode()`, `pixelData()`, `setPixelData()`, `childNodes()`, `parentNode()`
- **Selection** — `width()`, `height()`, `pixelData()`, `select()`, `clear()`
- **InfoObject** — key-value config for export options

### Plugin Types
1. **Extensions** — appear in Tools > Scripts menu
2. **Dockers** — panel widgets docked in the UI

### Extension Registration
```python
class MyExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self):
        action = self.createAction("myAction", "My Action", "tools/scripts")
        action.triggered.connect(self.do_something)

    def do_something(self):
        doc = Krita.instance().activeDocument()
        # ... manipulate document ...

Krita.instance().addExtension(MyExtension(Krita.instance()))
```

### Desktop File (Registration Metadata)
```ini
[Desktop Entry]
Type=Service
ServiceTypes=Krita/PythonPlugin
X-KDE-Library=myplugin
X-Python-2-Compatible=false
Name=My Plugin
Comment=Description here
```

### Batch Mode
```python
doc.setBatchmode(True)  # suppress dialogs
doc.exportImage("output.png", InfoObject())
doc.close()
```

### Key Takeaways
- **Python-native** — uses actual Python classes, not a DSL
- **Extension + Docker** pattern for different UI integration
- **Desktop file** for metadata (like package.json)
- **Batch mode flag** to suppress UI for scripted operations
- **Node = Layer** abstraction (everything in the layer tree is a Node)

---

## Summary: Design Patterns for RetroSprite

### Recommended API Design

#### 1. Object Model (consensus across all editors)
All editors expose a hierarchy mirroring the document model:
```
app
  +-- sprite/document
        +-- layers[] / nodes[]
        |     +-- image/pixel_data
        +-- frames[]
        +-- palette
        +-- selection
        +-- tags[]
```

**For RetroSprite:** Expose `app`, `sprite` (wrapping current state), `layer`, `frame`, `image` (wrapping PixelGrid), `palette`, `selection`.

#### 2. Plugin Registration (best patterns)
Three strong conventions emerged:

| Pattern | Used By | Mechanism |
|---------|---------|-----------|
| Manifest file + entry script | Aseprite, Pixelorama, Krita | `package.json` / `extension.json` / `.desktop` file |
| Class subclassing | GIMP, Krita | Subclass `PlugIn` / `Extension` |
| Command registration | Aseprite | `plugin:newCommand{id, title, group, onclick}` |

**For RetroSprite (Python):** Use a manifest (`plugin.json`) + a Python module with a conventional `register(app)` function. The register function receives the app API object and can:
- Register menu commands: `app.add_command(id, title, menu_path, callback)`
- Register tools: `app.add_tool(id, title, icon, callbacks)`
- Listen to events: `app.on('sprite_changed', callback)`

#### 3. Event System (from Aseprite + GIMP)
Key events to support:
- `before_tool_use` / `after_tool_use`
- `sprite_changed` (any modification)
- `layer_changed` (active layer switched)
- `frame_changed` (active frame switched)
- `color_changed` (palette selection changed)
- `selection_changed`

#### 4. CLI Batch Export (from ImageMagick + Krita)
Recommended CLI pattern:
```bash
# Basic export
retrosprite export input.rsp -o output.png

# Resize
retrosprite export input.rsp -o output.png --scale 2x
retrosprite export input.rsp -o output.png --resize 128x128

# Sprite sheet
retrosprite export input.rsp -o sheet.png --spritesheet --columns 4

# Format conversion
retrosprite export input.rsp -o output.gif --fps 12

# Batch processing (multiple files)
retrosprite batch *.rsp --export png --scale 2x --output-dir ./exports/

# Apply operations
retrosprite export input.rsp -o output.png --flip-h --rotate 90

# Specific frames/layers
retrosprite export input.rsp -o output.png --frame 5
retrosprite export input.rsp -o output.png --layer "Background"
retrosprite export input.rsp -o output.png --frames 1-10

# Pipeline-style (ImageMagick-inspired)
retrosprite process input.rsp --resize 64x64 --palette "gameboy" --export output.png
```

#### 5. Plugin Discovery & Loading
```
~/.retrosprite/plugins/
  my-plugin/
    plugin.json        # manifest
    __init__.py        # entry point with register(app)
    helpers.py         # additional modules
```

#### 6. Security Considerations
- Run plugins in a restricted namespace (no shell execution, no subprocess spawning)
- Provide safe file I/O through the API only
- Allow users to enable/disable plugins via preferences

### Priority Recommendation
1. **CLI batch export first** — lowest complexity, highest standalone value, no UI needed
2. **Scripting API second** — expose read-only document model, then read-write
3. **Plugin system third** — manifest + registration + menu integration
4. **Event hooks last** — most complex, least urgent

Sources:
- [Aseprite API](https://www.aseprite.org/api/)
- [Aseprite Plugin API](https://www.aseprite.org/api/plugin)
- [Aseprite API GitHub](https://github.com/aseprite/api)
- [GIMP Python Plug-Ins](https://developer.gimp.org/resource/writing-a-plug-in/tutorial-python/)
- [GIMP Script-Fu](https://developer.gimp.org/resource/writing-a-plug-in/tutorial-script-fu/)
- [GIMP Python-Fu Samples](https://github.com/jfmdev/PythonFuSamples)
- [GIMP 3 Python Migration](https://gist.github.com/hnbdr/d4aa13f830b104b23694a5ac275958f8)
- [Pixelorama Extension Basics](https://pixelorama.org/extension_system/extension_basics/)
- [Pixelorama Plugin Discussion](https://github.com/Orama-Interactive/Pixelorama/discussions/544)
- [ImageMagick CLI Processing](https://imagemagick.org/script/command-line-processing.php)
- [ImageMagick Convert](https://imagemagick.org/script/convert.php)
- [ImageMagick Mogrify](https://imagemagick.org/script/mogrify.php)
- [Krita Python Scripting Intro](https://docs.krita.org/en/user_manual/python_scripting/introduction_to_python_scripting.html)
- [Krita Python Plugin HowTo](https://docs.krita.org/en/user_manual/python_scripting/krita_python_plugin_howto.html)
- [Krita Scripting School](https://scripting.krita.org/lessons/plugins-create)
