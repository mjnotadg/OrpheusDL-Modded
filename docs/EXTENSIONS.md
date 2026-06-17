# Extensions Guide

Extensions let you hook into OrpheusDL's download pipeline to run custom logic before or after each track download. This guide covers the architecture, how extensions are loaded, and how to create one.

---

## Architecture Overview

### How Extensions Are Loaded

Extensions live in the `extensions/` directory at the project root. During Orpheus initialization (`orpheus/core.py`), the loader:

1. Creates `extensions/` if it doesn't exist
2. Scans for subdirectories containing an `interface.py`
3. Imports the `OrpheusExtension` class from each
4. Instantiates them using settings from `config/settings.json`
5. Stores them in a nested dict: `self.extensions[extension_type][extension_name]`

```python
# orpheus/core.py, lines 122-179
os.makedirs('extensions', exist_ok=True)
for extension in os.listdir('extensions'):
    if os.path.isdir(f'extensions/{extension}') and os.path.exists(f'extensions/{extension}/interface.py'):
        class_ = getattr(importlib.import_module(f'extensions.{extension}.interface'), 'OrpheusExtension', None)
        if class_:
            self.extension_list.add(extension)

# Later: instances are created and stored
for extension in self.extension_list:
    extension_settings = getattr(importlib.import_module(f'extensions.{extension}.interface'), 'extension_settings', None)
    settings = self.settings['extensions'][extension_settings.extension_type][extension] \
        if extension_settings.extension_type in self.settings['extensions'] \
        and extension in self.settings['extensions'][extension_settings.extension_type] else extension_settings.settings
    extension_type = extension_settings.extension_type
    self.extensions[extension_type] = self.extensions.get(extension_type, {})
    self.extensions[extension_type][extension] = class_(settings)
```

### Extension Data Model

Extensions define their metadata via `ExtensionInformation` (from `utils/models.py`):

```python
@dataclass
class ExtensionInformation:
    extension_type: str   # groups extensions (e.g. "hooks", "proxy", "notification")
    settings: dict       # default settings for this extension
```

The `ModuleController` passes extensions to modules:

```python
@dataclass
class ModuleController:
    module_settings: dict
    data_folder: str
    extensions: dict          # { extension_type: { extension_name: instance } }
    temporary_settings_controller: TemporarySettingsController
    orpheus_options: OrpheusOptions
    get_current_timestamp: FunctionType
    printer_controller: Oprinter
    module_error: ClassMethodDescriptorType
```

---

## Directory Structure

```
orpheus.py
config/
  settings.json          # extension settings go here
extensions/
  my_extension/
    interface.py        # required
    (other files)       # optional
```

---

## Creating an Extension

### Step 1: Create the Extension Directory

Create a new folder under `extensions/`:

```
extensions/
  before_after_hook/
    interface.py
```

### Step 2: Write `interface.py`

Every extension must define two things:

1. `extension_settings` — an `ExtensionInformation` instance
2. `OrpheusExtension` — a class with an `__init__` accepting settings

```python
from utils.models import *

extension_settings = ExtensionInformation(
    extension_type = "hooks",
    settings = {
        "enabled": True,
        "log_actions": True,
    }
)

class OrpheusExtension:
    def __init__(self, settings: dict):
        self.settings = settings
```

### Step 3: Define Hook Methods

Add methods to `OrpheusExtension` that will be called by the download pipeline. There is no enforced method signature — you define what you need. For example:

```python
class OrpheusExtension:
    def __init__(self, settings: dict):
        self.settings = settings

    def before_download(self, track_info: TrackInfo, module_name: str) -> None:
        """Called before a track is downloaded."""
        if self.settings.get("log_actions"):
            print(f"[before_download] {track_info.name} via {module_name}")

    def after_download(self, track_info: TrackInfo, file_path: str) -> None:
        """Called after a track has been downloaded and tagged."""
        if self.settings.get("log_actions"):
            print(f"[after_download] {track_info.name} -> {file_path}")

    def on_download_error(self, track_info: TrackInfo, error: str) -> None:
        """Called when a track download fails."""
        if self.settings.get("log_actions"):
            print(f"[error] {track_info.name} failed: {error}")
```

The `TrackInfo` dataclass (from `utils/models.py`) provides full track metadata:

```python
@dataclass
class TrackInfo:
    name: str
    album: str
    album_id: str
    artists: list
    tags: Tags
    codec: CodecEnum
    cover_url: str
    release_year: int
    duration: Optional[int] = None
    explicit: Optional[bool] = None
    artist_id: Optional[str] = None
    animated_cover_url: Optional[str] = None
    description: Optional[str] = None
    bit_depth: Optional[int] = 16
    sample_rate: Optional[float] = 44.1
    bitrate: Optional[int] = None
    download_extra_kwargs: Optional[dict] = field(default_factory=dict)
    cover_extra_kwargs: Optional[dict] = field(default_factory=dict)
    credits_extra_kwargs: Optional[dict] = field(default_factory=dict)
    lyrics_extra_kwargs: Optional[dict] = field(default_factory=dict)
    error: Optional[str] = None
```

### Step 4: Add Settings to `config/settings.json`

Add your extension's configuration under the `extensions` key:

```json
{
  "extensions": {
    "hooks": {
      "before_after_hook": {
        "enabled": true,
        "log_actions": true
      }
    }
  }
}
```

If no `extensions` section exists yet, add it to `config/settings.json`.

---

## Wiring Hooks into the Download Pipeline

The extension skeleton above defines the hook methods, but they won't be called until you add the call sites in `orpheus/music_downloader.py`. The main entry point is `download_track()` (line 628).

Here is where to insert the calls:

### Before Download

In `orpheus/music_downloader.py`, find the start of `download_track()` and call `before_download` on all loaded extensions:

```python
def download_track(self, track_id, album_location='', ...):
    # Before downloading, call all extensions
    for extension_type in self.module_controls.get('extensions', {}):
        for extension_name, extension in self.module_controls['extensions'][extension_type].items():
            if hasattr(extension, 'before_download'):
                extension.before_download(track_info, module_name)
```

### After Download

At the end of `download_track()`, after the file is downloaded and tagged, call `after_download`:

```python
    # After downloading, call all extensions
    for extension_type in self.module_controls.get('extensions', {}):
        for extension_name, extension in self.module_controls['extensions'][extension_type].items():
            if hasattr(extension, 'after_download'):
                extension.after_download(track_info, final_file_path)
```

### On Error

Wrap the download logic in a try/except and call `on_download_error` in the exception handler:

```python
try:
    # ... download and tagging logic ...
except Exception as e:
    for extension_type in self.module_controls.get('extensions', {}):
        for extension_name, extension in self.module_controls['extensions'][extension_type].items():
            if hasattr(extension, 'on_download_error'):
                extension.on_download_error(track_info, str(e))
    raise
```

---

## Complete Example: `before_after_hook` Extension

```python
# extensions/before_after_hook/interface.py
import logging
from utils.models import *

extension_settings = ExtensionInformation(
    extension_type = "hooks",
    settings = {
        "enabled": True,
        "log_actions": True,
    }
)

class OrpheusExtension:
    def __init__(self, settings: dict):
        self.settings = settings
        self.logger = logging.getLogger("before_after_hook")

    def before_download(self, track_info: TrackInfo, module_name: str) -> None:
        if not self.settings.get("enabled"):
            return
        self.logger.debug(f"Downloading: {track_info.name} ({track_info.album})")

    def after_download(self, track_info: TrackInfo, file_path: str) -> None:
        if not self.settings.get("enabled"):
            return
        self.logger.debug(f"Completed: {track_info.name} -> {file_path}")

    def on_download_error(self, track_info: TrackInfo, error: str) -> None:
        if not self.settings.get("enabled"):
            return
        self.logger.error(f"Failed: {track_info.name} - {error}")
```

Then add to `config/settings.json`:

```json
{
  "extensions": {
    "hooks": {
      "before_after_hook": {
        "enabled": true,
        "log_actions": true
      }
    }
  }
}
```

And add the hook calls to `orpheus/music_downloader.py` at the desired pipeline points.

---

## `proxy_rotator` Extension

The `proxy_rotator` extension routes requests through a rotating proxy list. It supports two rotation strategies:

- **session**: Sets the proxy once at startup via environment variables
- **request**: Rotates the proxy before each download request

### Hook Methods

| Method | Description |
|--------|-------------|
| `on_startup(orpheus_session)` | Called when Orpheus starts. Loads proxy list and applies initial strategy. |
| `on_shutdown()` | Called when Orpheus exits. Restores original environment variables. |
| `before_download(track_info, module_name)` | Called before each track download. Rotates proxy if using request strategy. |

### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `true` | Enable or disable the extension |
| `proxy_list_file` | `"proxy-list.txt"` | Path to file containing proxy list (one per line, `#` for comments) |
| `rotation_strategy` | `"session"` | Strategy: `"session"` or `"request"` |

### CLI Arguments

| Flag | Description |
|------|-------------|
| `-px`, `--proxy-list` | Path to proxy list file (overrides `proxy_list_file` setting) |

### Proxy List Format

Each line in the proxy file should contain a proxy in `host:port` format:

```
# My proxy list
proxy1.example.com:8080
proxy2.example.com:3128
192.168.1.1:1080
```

The extension auto-detects common SOCKS5 ports (1080, 10800) and HTTP ports (3128, 8000, 8080, 8443, 8888).

### Example Configuration

```json
{
  "extensions": {
    "proxy": {
      "proxy_rotator": {
        "enabled": true,
        "proxy_list_file": "proxy-list.txt",
        "rotation_strategy": "request"
      }
    }
  }
}
```

---

## Extension Types

Extensions are grouped by `extension_type`. Multiple extensions of the same type can coexist. The type is arbitrary — choose a name that makes sense for your use case:

| extension_type | Example use |
|---|---|
| `hooks` | Before/after download callbacks |
| `proxy` | Route requests through a rotating proxy list |
| `notification` | Send alerts on download events |
| `filter` | Skip or modify tracks based on rules |

Extensions of different types are independent and do not interfere with each other.
