<!-- PROJECT INTRO -->

<img src='https://svgshare.com/i/__W.svg' title='Orfi_temporary' height="150">

OrpheusDL_Modded
=================

A modular music archival program with enhanced features

[Report Bug](https://github.com/OrfiTeam/OrpheusDL/issues)
·
[Request Feature](https://github.com/OrfiTeam/OrpheusDL/issues)


## Table of content

- [About OrpheusDL_Modded](#about-orpheusdl_modded4)
- [Key Enhancements](#key-enhancements)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
    - [General Settings](#general-settings)
    - [Artist Downloading Settings](#artist-downloading-settings)
    - [Formatting Settings](#formatting-settings)
    - [Codec Settings](#codec-settings)
    - [Module Defaults](#module-defaults)
    - [Lyrics Settings](#lyrics-settings)
    - [Cover Settings](#cover-settings)
    - [Playlist Settings](#playlist-settings)
    - [Advanced Settings](#advanced-settings)
        - [Enhanced Logging System](#enhanced-logging-system)
        - [Artist Downloading Behavior](#artist-downloading-behavior)
        - [Quality Enforcement Details](#quality-enforcement-details)
        - [Directory Organization](#directory-organization)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)
- [Contact](#contact)
- [Acknowledgements](#acknowledgements)
- [Changelog](#changelog)



<!-- ABOUT ORPHEUS -->
## About OrpheusDL_Modded

OrpheusDL_Modded is an enhanced version of OrpheusDL, a modular music archival tool written in Python which allows archiving from multiple different services. This modded version includes significant improvements for better organization, filtering, and logging capabilities.

## Key Enhancements

### 🎯 **Enhanced Logging System**
- **Separate log files** for different types of download failures
- **Album-specific logging** - logs are created in each album folder
- **Clear categorization** - unavailable tracks vs quality issues
- **Detailed error tracking** for troubleshooting

### 📁 **Improved Directory Organization**
- **Source subdirectories** - organize downloads by service (Qobuz, Tidal, Deezer, etc.)
- **Disc subdirectories** - automatic "Disc N" folders for multi-disc albums
- **Better folder structure** for easier navigation

### 🔍 **Advanced Filtering Options**
- **Collector edition filtering** - skip deluxe, expanded, bonus editions
- **Live recording filtering** - skip live albums, concerts, performances
- **Strict artist matching** - only download albums by exact artist
- **Track-level filtering** - skip tracks by different artists within albums

### ⚡ **Strict Quality Download**
- **Quality enforcement** - only download tracks meeting specified quality
- **Configurable quality requirements** - set minimum quality standards
- **Detailed quality logging** - track which quality requirements failed

### 🎵 **Updated Quality Hierarchy**
Quality levels are now ordered from highest to lowest:
- **Hifi** → Highest quality (FLAC >16bit OR >44.1kHz)
- **Lossless** → FLAC, ALAC, WAV (any bit depth/sample rate)
- **High** → Lossy formats ≥256kbps
- **Medium** → Lossy formats 128-255kbps
- **Low** → Lossy formats <128kbps

<!-- GETTING STARTED -->
## Getting Started

Follow these steps to get a local copy of OrpheusDL_Modded up and running:

### Prerequisites

* Python 3.7+ (due to the requirement of dataclasses), though Python 3.9 is highly recommended

### Installation

1. Clone the repo
    ```shell
    git clone https://github.com/OrfiTeam/OrpheusDL.git && cd OrpheusDL
    ```
2. Install all requirements
   ```shell
   pip install -r requirements.txt
   ```
3. Run the program at least once, or use this command to create the settings file
   ```shell
   python3 orpheus.py settings refresh
   ```
4. Enter your credentials in `config/settings.json`

<!-- USAGE EXAMPLES -->
## Usage

Just call `orpheus.py` with any link you want to archive, for example Qobuz:
```shell
python3 orpheus.py https://open.qobuz.com/album/c9wsrrjh49ftb
```

Alternatively do a search (luckysearch to automatically select the first option):
```shell
python3 orpheus.py search qobuz track darkside alan walker
```

Or if you have the ID of what you want to download, use:
```shell
python3 orpheus.py download qobuz track 52151405
```

<!-- CONFIGURATION -->
## Configuration

You can customize every module from Orpheus individually and also set general/global settings which are active in every
loaded module. You'll find the configuration file here: `config/settings.json`

### General Settings

```json5
{
    "download_path": "./downloads/",
    "download_quality": "hifi",
    "search_limit": 10,
    "strict_quality_download": false
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `download_path` | string | `"./downloads/"` | Set the absolute or relative output path with `/` as the delimiter |
| `download_quality` | string | `"hifi"` | Choose one of the following settings: `"hifi"`, `"lossless"`, `"high"`, `"medium"`, `"low"` |
| `search_limit` | integer | `10` | How many search results are shown when searching |
| `strict_quality_download` | boolean | `false` | If enabled, tracks will only be downloaded if the requested quality is available |

**Quality Options (Updated Order):**
- **"hifi"**: FLAC higher than 44.1/16 if available (highest quality)
- **"lossless"**: FLAC with 44.1/16 if available (any lossless format)
- **"high"**: lossy codecs such as MP3, AAC, ... in a higher bitrate (≥256kbps)
- **"medium"**: lossy codecs such as MP3, AAC, ... in a medium bitrate (128-255kbps)
- **"low"**: lossy codecs such as MP3, AAC, ... in a lower bitrate (<128kbps)

**NOTE: The `download_quality` really depends on the used modules, so check out the modules README.md**

### Artist Downloading Settings

```json5
{
    "return_credited_albums": true,
    "separate_tracks_skip_downloaded": true
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `return_credited_albums` | boolean | `true` | If enabled, includes albums where the artist is credited (not just main artist) |
| `separate_tracks_skip_downloaded` | boolean | `true` | If enabled, skips separate tracks that have already been downloaded as part of albums |

### Formatting Settings

```json5
{
    "album_format": "{name}{explicit}",
    "playlist_format": "{name}{explicit}",
    "track_filename_format": "{track_number}. {name}",
    "single_full_path_format": "{name}",
    "enable_zfill": true,
    "force_album_format": false,
    "source_subdirectories": true,
    "disc_subdirectories": true
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `track_filename_format` | string | `"{track_number}. {name}"` | How tracks are formatted in albums and playlists |
| `album_format` | string | `"{name}{explicit}"` | Base directory for albums - tracks and cover art are stored here |
| `playlist_format` | string | `"{name}{explicit}"` | Base directory for playlists |
| `single_full_path_format` | string | `"{name}"` | How singles are handled, separate from album/playlist formatting |
| `enable_zfill` | boolean | `true` | Enables zero padding for track numbers, disc numbers, etc. |
| `force_album_format` | boolean | `false` | Forces album format for tracks instead of single format |
| `source_subdirectories` | boolean | `true` | Creates service-specific subdirectories (e.g., "Qobuz", "Tidal", "Deezer") |
| `disc_subdirectories` | boolean | `true` | Creates "Disc N" subdirectories for multi-disc albums |

#### Format Variables

**Track filename variables:** `{name}`, `{album}`, `{album_artist}`, `{album_id}`, `{track_number}`, `{total_tracks}`, `{disc_number}`, `{total_discs}`, `{release_date}`, `{release_year}`, `{artist_id}`, `{isrc}`, `{upc}`, `{explicit}`, `{copyright}`, `{codec}`, `{sample_rate}`, `{bit_depth}`

**Album format variables:** `{name}`, `{id}`, `{artist}`, `{artist_id}`, `{release_year}`, `{upc}`, `{explicit}`, `{quality}`, `{artist_initials}`

**Playlist format variables:** `{name}`, `{creator}`, `{tracks}`, `{release_year}`, `{explicit}`, `{creator_id}`

**Special variables:**
- `{quality}` adds quality indicators like `[Dolby Atmos]`, `[96kHz 24bit]`, `[M]`
- `{explicit}` adds `[E]` for explicit content

### Codec Settings

```json5
{
    "proprietary_codecs": false,
    "spatial_codecs": true
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `proprietary_codecs` | boolean | `false` | Enable to allow `MQA`, `E-AC-3 JOC` or `AC-4 IMS` |
| `spatial_codecs` | boolean | `true` | Enable to allow `MPEG-H 3D`, `E-AC-3 JOC` or `AC-4 IMS` |

**Note: `spatial_codecs` has priority over `proprietary_codecs` when deciding if a codec is enabled**

### Module Defaults

```json5
{
    "lyrics": "default",
    "covers": "default",
    "credits": "default"
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `lyrics` | string | `"default"` | Module to use for lyrics retrieval. Change to module name under `/modules` |
| `covers` | string | `"default"` | Module to use for cover art retrieval. Change to module name under `/modules` |
| `credits` | string | `"default"` | Module to use for credits retrieval. Change to module name under `/modules` |

### Lyrics Settings

```json5
{
    "embed_lyrics": true,
    "embed_synced_lyrics": false,
    "save_synced_lyrics": true
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `embed_lyrics` | boolean | `true` | Embeds the (unsynced) lyrics inside every track |
| `embed_synced_lyrics` | boolean | `false` | Embeds the synced lyrics inside every track (requires `embed_lyrics` to be enabled) |
| `save_synced_lyrics` | boolean | `true` | Saves the synced lyrics in a `.lrc` file in the same directory as the track |

### Cover Settings

```json5
{
    "embed_cover": true,
    "main_compression": "high",
    "main_resolution": 1400,
    "save_external": false,
    "external_format": "png",
    "external_compression": "low",
    "external_resolution": 3000,
    "save_animated_cover": true
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `embed_cover` | boolean | `true` | Embeds the album cover inside every track |
| `main_compression` | string | `"high"` | Compression of the main cover (`"low"` or `"high"`) |
| `main_resolution` | integer | `1400` | Resolution (in pixels) of the main cover |
| `save_external` | boolean | `false` | Saves the cover from a third party cover module |
| `external_format` | string | `"png"` | Format of the third party cover (`"jpg"`, `"png"`, `"webp"`) |
| `external_compression` | string | `"low"` | Compression of the third party cover (`"low"` or `"high"`) |
| `external_resolution` | integer | `3000` | Resolution (in pixels) of the third party cover |
| `save_animated_cover` | boolean | `true` | Saves animated covers when supported (often in MPEG-4 format) |

### Playlist Settings

```json5
{
    "save_m3u": true,
    "paths_m3u": "absolute",
    "extended_m3u": true
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `save_m3u` | boolean | `true` | Saves an M3U playlist file with the downloaded tracks |
| `paths_m3u` | string | `"absolute"` | Type of paths in M3U file (`"absolute"` or `"relative"`) |
| `extended_m3u` | boolean | `true` | Creates extended M3U format with track duration and artist information |

### Advanced Settings

```json5
{
    "advanced_login_system": false,
    "codec_conversions": {
        "alac": "flac",
        "wav": "flac"
    },
    "conversion_flags": {
        "flac": {
            "compression_level": "5"
        }
    },
    "conversion_keep_original": false,
    "cover_variance_threshold": 8,
    "debug_mode": false,
    "disable_subscription_checks": false,
    "enable_undesirable_conversions": false,
    "ignore_existing_files": false,
    "ignore_different_artists": true,
    "remove_collectors_editions": true,
    "remove_live_recordings": true,
    "strict_artist_match": true,
    "log_unavailable_tracks": true
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `advanced_login_system` | boolean | `false` | Enables advanced login system for modules |
| `codec_conversions` | object | `{"alac": "flac", "wav": "flac"}` | Automatic codec conversion rules |
| `conversion_flags` | object | `{"flac": {"compression_level": "5"}}` | FFmpeg conversion flags for different codecs |
| `conversion_keep_original` | boolean | `false` | Keeps original files after codec conversion |
| `cover_variance_threshold` | integer | `8` | Threshold for cover art similarity matching |
| `debug_mode` | boolean | `false` | Enables debug logging |
| `disable_subscription_checks` | boolean | `false` | Disables subscription quality checks |
| `enable_undesirable_conversions` | boolean | `false` | Enables potentially undesirable codec conversions |
| `ignore_existing_files` | boolean | `false` | Skips tracks that already exist on disk |
| `ignore_different_artists` | boolean | `true` | Skips tracks by different artists during artist downloads |
| `remove_collectors_editions` | boolean | `true` | Filters out collector's editions during artist downloads |
| `remove_live_recordings` | boolean | `true` | Filters out live recordings during artist downloads |
| `strict_artist_match` | boolean | `true` | Only downloads albums where album artist matches requested artist |
| `log_unavailable_tracks` | boolean | `true` | Logs failed track downloads to separate log files in album folders |

#### Enhanced Logging System

OrpheusDL_Modded includes an enhanced logging system that creates separate log files within each album folder to help you track and troubleshoot download issues:

**Log Files Created:**

1. **`error.txt`** - Logs tracks that are unavailable (region-locked, removed, or otherwise not accessible)
   ```
   Unavailable: The Rolling Stones [11]/Honk (Deluxe) [144013822]/Beast Of Burden (Live At Arrowhead Stadium, Kansas) [939813142]
   ```

2. **`strict_quality_error.txt`** - Logs tracks that don't meet quality requirements
   ```
   Not meet quality requirements: The Rolling Stones [11]/Flashpoint (2009 Remaster) [212919]/Continental Drift (Live / 2009 Remaster) [2120676]
   ```

**Features:**
- **Separate categorization**: Unavailable tracks and quality issues are logged to different files for easier troubleshooting
- **Album-specific logging**: Log files are created in each album's download folder, not in the project root
- **Clear error messages**: Each log entry clearly indicates the reason for the failure
- **Consistent format**: All entries follow the same format: `Error Type: Artist [ID]/Album [ID]/Track [ID]`

**Location:**
Log files are created in the album folder structure:
```
downloads/
└── Deezer/
    └── The Rolling Stones [11]/
        └── Honk (Deluxe) [144013822] [E]/
            ├── error.txt
            ├── strict_quality_error.txt
            └── [music files...]
```

**Settings Required:**
- `log_unavailable_tracks: true` (in advanced settings) - enables logging of unavailable tracks
- `strict_quality_download: true` (in general settings) - enables logging of quality issues

#### Directory Organization

OrpheusDL_Modded provides enhanced directory organization features:

**Source Subdirectories:**
When `source_subdirectories: true` is enabled, downloads are organized by service:
```
downloads/
├── Qobuz/
│   └── [Qobuz albums...]
├── Tidal/
│   └── [Tidal albums...]
├── Deezer/
│   └── [Deezer albums...]
└── Spotify/
    └── [Spotify albums...]
```

**Disc Subdirectories:**
When `disc_subdirectories: true` is enabled, multi-disc albums are organized:
```
downloads/
└── Qobuz/
    └── Artist Name [123]/
        └── Album Name [456]/
            ├── Disc 1/
            │   ├── 01. Track 1.flac
            │   └── 02. Track 2.flac
            ├── Disc 2/
            │   ├── 01. Track 1.flac
            │   └── 02. Track 2.flac
            └── cover.jpg
```

#### Artist Downloading Behavior

The following settings control how artist downloads behave:

**Album Filtering:**
- `strict_artist_match`: Only processes albums where the album artist exactly matches the requested artist
- `remove_collectors_editions`: Skips albums with keywords like "collector", "deluxe", "expanded", "bonus", "special", "anniversary", "remastered", "reissue", "limited"
- `remove_live_recordings`: Skips albums with keywords like "live", "concert", "performance", "stage", "tour", "acoustic", "unplugged", "mtv", "bbc", "radio", "session"

**Track Filtering:**
- `ignore_different_artists`: Within albums, skips individual tracks by artists other than the requested artist
- `separate_tracks_skip_downloaded`: Skips separate tracks that have already been downloaded as part of albums

**Examples:**

**Conservative Download (Current Default):**
```json5
{
    "strict_artist_match": true,
    "ignore_different_artists": true,
    "remove_collectors_editions": true,
    "remove_live_recordings": true
}
```
- Only downloads albums by the exact artist
- Only downloads tracks by the exact artist within those albums
- Skips collector editions and live recordings

**Complete Album Download:**
```json5
{
    "strict_artist_match": true,
    "ignore_different_artists": false,
    "remove_collectors_editions": false,
    "remove_live_recordings": false
}
```
- Downloads albums by the exact artist
- Downloads ALL tracks within those albums (including guest features)
- Includes collector editions and live recordings

**Most Permissive:**
```json5
{
    "strict_artist_match": false,
    "ignore_different_artists": false,
    "remove_collectors_editions": false,
    "remove_live_recordings": false
}
```
- Downloads all albums where the artist appears (credited or main)
- Downloads all tracks within those albums
- Includes all types of releases

#### Quality Enforcement Details

When `strict_quality_download` is enabled, the following quality requirements are enforced:

| Quality Setting | Allowed Codecs | Additional Requirements |
|----------------|----------------|------------------------|
| **hifi** | FLAC | >16bit OR >44.1kHz sample rate |
| **lossless** | FLAC, ALAC, WAV | Any bit depth/sample rate |
| **high** | MP3, AAC, HE-AAC, Vorbis, Opus | ≥256kbps bitrate |
| **medium** | MP3, AAC, HE-AAC, Vorbis, Opus | 128-255kbps bitrate |
| **low** | MP3, AAC, HE-AAC, Vorbis, Opus | <128kbps bitrate |

**Example Error Log Entry:**
```
Strict quality download failed: Requested quality "lossless" unavailable for: Artist Name [123]/Album Name [456]/Track Name [789] (codec: MP3, bitrate: 320, bit_depth: 16, sample_rate: 44.1)
```

**Benefits:**
- Prevents downloading tracks that don't meet your quality standards
- Avoids creating empty folders when no tracks meet quality requirements
- Provides detailed logging of failed downloads for review
- Works with all download types: albums, artists, playlists, and individual tracks

## Usage Examples

### Strict Quality Download Examples

**Example 1: Download only lossless tracks**
```json5
{
    "download_quality": "lossless",
    "strict_quality_download": true
}
```
This will only download FLAC, ALAC, or WAV files. Any MP3, AAC, or other lossy formats will be skipped.

**Example 2: Download only high-quality lossy tracks**
```json5
{
    "download_quality": "high",
    "strict_quality_download": true
}
```
This will only download lossy formats (MP3, AAC, etc.) with bitrates of 256kbps or higher.

**Example 3: Download with quality fallback (default behavior)**
```json5
{
    "download_quality": "lossless",
    "strict_quality_download": false
}
```
This will attempt to download lossless quality but fall back to the best available quality if lossless is not available.

### Artist Download Examples

**Example 1: Download only studio albums by exact artist**
```json5
{
    "strict_artist_match": true,
    "ignore_different_artists": true,
    "remove_collectors_editions": true,
    "remove_live_recordings": true
}
```

**Example 2: Download complete albums (including guest features)**
```json5
{
    "strict_artist_match": true,
    "ignore_different_artists": false,
    "remove_collectors_editions": false,
    "remove_live_recordings": false
}
```

**Example 3: Download everything the artist appears on**
```json5
{
    "strict_artist_match": false,
    "ignore_different_artists": false,
    "remove_collectors_editions": false,
    "remove_live_recordings": false
}
```

### Directory Organization Examples

**Example 1: Enable source subdirectories**
```json5
{
    "source_subdirectories": true
}
```
This will create service-specific folders like "Qobuz", "Tidal", "Deezer" in your downloads directory.

**Example 2: Enable disc subdirectories**
```json5
{
    "disc_subdirectories": true
}
```
This will create "Disc 1", "Disc 2", etc. folders for multi-disc albums.

### Console Output Examples

**When tracks meet quality requirements:**
```
Track 1/10
=== Downloading track Track Name (123456) ===
        Album: Album Name (789)
        Artists: Artist Name (456)
        Codec: FLAC, bitrate: 1411kbps, bit depth: 16bit, sample rate: 44.1kHz
        Downloading track file
        === Track 123456 downloaded ===
```

**When tracks fail quality requirements:**
```
Track 1/10
        Strict quality download failed: Requested quality "lossless" unavailable for: Artist [123]/Album [456]/Track [789] (codec: MP3, bitrate: 320, bit_depth: 16, sample_rate: 44.1)
=== Track 789 failed due to strict quality requirements ===
```

**When tracks are skipped due to artist filtering:**
```
Track 1/10
        Track is not from the correct artist, skipping
```

**When albums are filtered out:**
```
Skipping collector edition: Album Name (Deluxe Edition)
Skipping live recording: Album Name (Live)
Skipping different artist: Album Name (by Different Artist)
```

## Troubleshooting

**Q: Why are all my tracks being skipped?**
A: Check your `download_quality` setting and ensure the tracks are actually available in that quality. Some older releases may only be available in lossy formats.

**Q: Where can I find details about failed downloads?**
A: Failed downloads are logged to separate files in each album folder:
- `error.txt` - for unavailable tracks (region-locked, removed, etc.)
- `strict_quality_error.txt` - for tracks that don't meet quality requirements

**Q: Can I use strict quality with any download type?**
A: Yes, strict quality download works with albums, artists, playlists, and individual tracks.

**Q: Will folders be created if no tracks meet quality requirements?**
A: No, folders and cover art are only created when at least one track will be downloaded.

**Q: Why are some tracks being skipped during artist downloads?**
A: Check your `ignore_different_artists` setting. If enabled, tracks by other artists within albums will be skipped.

**Q: How do I download complete albums with guest features?**
A: Set `ignore_different_artists` to `false` to download all tracks within albums, including guest appearances.

**Q: How do I enable logging of failed downloads?**
A: Set `log_unavailable_tracks: true` in the advanced settings to log unavailable tracks, and `strict_quality_download: true` in general settings to log quality issues.

**Q: What's the difference between unavailable tracks and quality issues?**
A: 
- **Unavailable tracks**: Cannot be downloaded due to service restrictions (region-locked, removed from service, etc.)
- **Quality issues**: Available but don't meet your specified quality requirements (e.g., only MP3 available when you requested FLAC)

**Q: How do I organize downloads by service?**
A: Enable `source_subdirectories: true` in the formatting settings to create service-specific folders.

**Q: How do I organize multi-disc albums?**
A: Enable `disc_subdirectories: true` in the formatting settings to create "Disc N" folders for multi-disc albums.

<!-- Contact -->
## Contact

OrfiDev (Project Lead) - [@OrfiDev](https://github.com/OrfiTeam)

Dniel97 (Current Lead Developer) - [@Dniel97](https://github.com/Dniel97)

Project Link: [Orpheus Public GitHub Repository](https://github.com/OrfiTeam/OrpheusDL)

## Changelog

### Version 4.0 (OrpheusDL_Modded)

#### 🆕 New Features
- **Enhanced Logging System**: Separate log files for unavailable tracks and quality issues
- **Strict Quality Download**: Enforce quality requirements and skip tracks that don't meet standards
- **Source Subdirectories**: Organize downloads by service (Qobuz, Tidal, Deezer, etc.)
- **Disc Subdirectories**: Automatic "Disc N" folders for multi-disc albums
- **Advanced Filtering**: Filter collector editions, live recordings, and strict artist matching

#### 🔧 Improvements
- **Updated Quality Hierarchy**: Hifi → Highest, Lossless, high, medium, low
- **Better Error Messages**: Clear categorization of download failures
- **Improved Directory Structure**: More organized download folders
- **Enhanced Artist Downloads**: More granular control over what gets downloaded

#### 🐛 Bug Fixes
- Fixed logging order to properly categorize unavailable vs quality issues
- Improved error handling for strict quality downloads
- Better handling of multi-disc album organization

#### 📝 Documentation
- Comprehensive README with all new features
- Detailed configuration examples
- Troubleshooting guide
- Usage examples for all new features

<!-- ACKNOWLEDGEMENTS -->
## Acknowledgements
* Chimera by Aesir - the inspiration to the project
* [Icon modified from a freepik image](https://www.freepik.com/)
* Original OrpheusDL team for the excellent foundation
