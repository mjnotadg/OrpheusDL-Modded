---
name: Proxy Support Implementation
overview: Add built-in proxy support as a first-class extension (extension_type = "proxy"), with extension-defined CLI arguments, auto-detection of HTTP/SOCKS5 protocol from port number, and formal pre/post download hooks wired into the download pipeline.
todos:
  - id: models
    content: Add cli_args field to ExtensionInformation in utils/models.py
    status: completed
  - id: orpheus-cli
    content: Modify orpheus.py to dynamically build CLI parser from installed extensions
    status: completed
  - id: core-hooks
    content: Modify orpheus/core.py to call on_startup/on_shutdown and pass parsed CLI args to extensions
    status: completed
  - id: hook-system
    content: Wire before_download/after_download/on_download_error hooks into music_downloader.py
    status: completed
  - id: proxy-extension
    content: Create extensions/proxy_rotator/interface.py with ProxyManager, CLI args, auto-detect protocol
    status: completed
  - id: gitignore
    content: Add proxy-list.txt to .gitignore
    status: completed
  - id: readme
    content: Add Proxy Extension section to README.md and EXTENSIONS.md docs
    status: completed
isProject: false
---

## Approach

Proxy support is implemented as a first-class extension (`extension_type = "proxy"`). CLI arguments are **extension-defined, not hardcoded** in `orpheus.py` — extensions declare their args in `ExtensionInformation`, and `orpheus.py` dynamically builds the parser at startup from all installed extensions. The extension hook system is formalized with system hooks (`on_startup`, `on_shutdown`) and download pipeline hooks (`before_download`, `after_download`, `on_download_error`).

---

## Extension CLI Argument System

Each extension declares CLI args in `ExtensionInformation.cli_args` as a list of dicts matching `argparse.add_argument()` signature:

```python
extension_settings = ExtensionInformation(
    extension_type = "proxy",
    settings = {
        "enabled": True,
        "proxy_list_file": "proxy-list.txt",
        "rotation_strategy": "session",
    },
    cli_args = [
        {"flags": ["-px", "--proxy-list"], "kwargs": {"help": "Path to proxy list file"}},
    ]
)
```

At startup, `orpheus.py` scans all installed extensions, collects their `cli_args`, and adds them to the parser. Parsed values are forwarded to `Orpheus.__init__` as `{extension_name: {arg_dest: value}}` — e.g. `{"proxy_rotator": {"proxy_list": "/path/to/file"}}`. `core.py` injects these into extension settings before instantiation.

---

## Hook System

Extensions implement optional methods. The pipeline checks `hasattr` before calling.

### System Hooks (`orpheus/core.py`)

| Method | When | Purpose |
|--------|------|---------|
| `on_startup(orpheus_session)` | After extensions instantiated, before modules load | **Proxy setup point.** |
| `on_shutdown()` | On `Orpheus.shutdown()` call | Cleanup. |

### Download Pipeline Hooks (`orpheus/music_downloader.py`)

| Method | When | Purpose |
|--------|------|---------|
| `before_download(track_info, module_name)` | Before track download begins | Logging, proxy rotation, track filtering |
| `after_download(track_info, file_path)` | After track downloaded and tagged | Notifications, cleanup |
| `on_download_error(track_info, error)` | When track download fails | Error logging, retry logic |

---

## Execution Timing

```
1. orpheus.py main()
   → scans extensions/, imports each interface.py
   → collects cli_args from ExtensionInformation
   → argparse builds parser with extension args
   → parses args

2. Orpheus.__init__(extension_cli_args)
   → loads settings
   → injects parsed CLI args into extension settings
   → instantiates extensions

3. on_startup() on all extensions ← PROXY ACTIVATED HERE
   → proxy_rotator loads file, detects protocols, sets env vars

4. Module startup loading (HTTP requests use proxies)

5. For each track:
   → before_download() ← proxy rotated for request strategy
   → download + tag
   → after_download() or on_download_error()

6. orpheus.shutdown() on exit → on_shutdown() on all extensions
```

---

## Task 1: `utils/models.py` — Add `cli_args` to `ExtensionInformation`

Add `cli_args: list[dict] = field(default_factory=list)` to the `ExtensionInformation` dataclass. Update the dataclass import to include `field` from dataclasses if not already present.

---

## Task 2: `orpheus.py` — Dynamic CLI Parser

In `main()`, before building the argument parser:

```python
# Collect CLI args from all installed extensions
extension_cli_info = {}  # {ext_name: {"flags": [...], "kwargs": {...}}}

for ext_name in os.listdir('extensions'):
    ext_path = f'extensions/{ext_name}'
    if os.path.isdir(ext_path) and os.path.exists(f'{ext_path}/interface.py'):
        mod = importlib.import_module(f'extensions.{ext_name}.interface')
        es = getattr(mod, 'extension_settings', None)
        if es and hasattr(es, 'cli_args') and es.cli_args:
            extension_cli_info[ext_name] = es.cli_args
```

After the base parser is created (before `args = parser.parse_args()`), dynamically add extension args:

```python
for ext_name, cli_args_list in extension_cli_info.items():
    for arg_def in cli_args_list:
        flags = arg_def.get("flags", [])
        kwargs = arg_def.get("kwargs", {})
        parser.add_argument(*flags, **kwargs)
```

After parsing, build a nested dict of extension CLI values and pass to `Orpheus`:

```python
extension_cli_args = {}
for ext_name in extension_cli_info:
    ext_kwargs = extension_cli_info[ext_name]
    for arg_def in ext_kwargs:
        for flag in arg_def.get("flags", []):
            if flag.startswith("--"):
                dest = flag[2:].replace("-", "_")
            else:
                dest = flag[1:].replace("-", "_")
            if hasattr(args, dest):
                extension_cli_args.setdefault(ext_name, {})[dest] = getattr(args, dest)

# At the end of main(), call shutdown
orpheus.shutdown()
```

---

## Task 3: `orpheus/core.py` — Accept CLI Args, Call System Hooks

**A.** Accept `extension_cli_args: dict | None = None` in `Orpheus.__init__`. After loading settings but before creating extension instances, merge CLI args into extension settings:

```python
if extension_cli_args:
    for ext_type, exts in self.settings.get('extensions', {}).items():
        for ext_name, ext_settings in exts.items():
            if ext_name in extension_cli_args:
                ext_settings.update(extension_cli_args[ext_name])
```

**B.** After extension instantiation (before module startup loading), call `on_startup()` on all extensions:

```python
for ext_type in self.extensions:
    for ext_name, ext in self.extensions[ext_type].items():
        if hasattr(ext, 'on_startup'):
            ext.on_startup(self)
```

**C.** Add `shutdown()` method to `Orpheus`:

```python
def shutdown(self):
    for ext_type in self.extensions:
        for ext_name, ext in self.extensions[ext_type].items():
            if hasattr(ext, 'on_shutdown'):
                ext.on_shutdown()
```

---

## Task 4: `orpheus/music_downloader.py` — Wire Download Hooks

In `Downloader.__init__`, store extensions:

```python
self.extensions = module_controls.get('extensions', {})
```

Add helper:

```python
def _call_hooks(self, method_name, *args, **kwargs):
    for ext_type in self.extensions:
        for ext_name, ext in self.extensions[ext_type].items():
            if hasattr(ext, method_name):
                getattr(ext, method_name)(*args, **kwargs)
```

**Hook call sites in `download_track()`:**
1. **Start of method** (before any download logic) — `before_download(track_info, self.service_name)`
2. **After successful tagging** (before `return True`) — `after_download(track_info, track_location)`
3. **In exception handler** (before `return False`) — `on_download_error(track_info, str(e))`

---

## Task 5: `extensions/proxy_rotator/interface.py` — Create the Extension

Full extension with:
- `extension_type = "proxy"`
- `cli_args` declaring `-px`/`--proxy-list`
- `ProxyManager` inner class: reads proxy list file, parses `user:pass@host:port`, auto-detects protocol from port, rotates
- `on_startup()`: loads proxies, sets env vars (session) or patches adapters (request)
- `on_shutdown()`: restores original state
- `before_download()`: rotates proxy for `request` strategy

**Protocol auto-detection:**
- Port `1080`, `10800` → `socks5://`
- Port `3128`, `8000`, `8080`, `8443`, `8888` → `http://`
- All others → `http://` (default)

**Rotation strategies:**
- `session` — one random proxy at `on_startup()`, set via `os.environ["HTTP_PROXY"]`/`os.environ["HTTPS_PROXY"]`. `requests.Session` respects these automatically.
- `request` — custom `ProxyAdapter` that round-robins through the proxy list on each `r_session.get()` call.

---

## Task 6: `.gitignore`

Add `proxy-list.txt`.

---

## Task 7: Documentation

**`README.md`** — Proxy Extension section:
- Installation (create `extensions/proxy_rotator/interface.py`)
- Settings: `enabled`, `proxy_list_file`, `rotation_strategy`
- `proxy-list.txt` format (`user:pass@host:port` per line, `#` comments supported)
- CLI: `-px /path/to/proxy-list.txt` (only visible when extension is installed)
- Example JSON config

**`docs/EXTENSIONS.md`** — Add:
- `proxy_rotator` to extension types table
- `cli_args` field in ExtensionInformation schema
- Full hook method reference table
- `proxy_rotator` example showing all methods and CLI args

---

## Acceptance Criteria

1. `utils/models.py` — `ExtensionInformation` has a `cli_args: list[dict]` field.
2. `orpheus.py` — CLI args are dynamically collected from installed extensions and added to the parser. Running without the proxy extension installed, `-px` is not recognized.
3. `extensions/proxy_rotator/interface.py` — exists with `extension_type = "proxy"`, declares `-px`/`--proxy-list` in `cli_args`, implements `ProxyManager`, auto-detects protocol from port.
4. `on_startup()` is called from `core.py` **before** any module loading or HTTP requests.
5. `before_download()` / `after_download()` / `on_download_error()` are called from `music_downloader.py` around every track download.
6. `on_shutdown()` is called on `orpheus.shutdown()`.
7. `proxy-list.txt` is listed in `.gitignore`.
8. README and EXTENSIONS.md are updated with proxy extension docs.
9. `modules/` directory is not modified.
