<!-- PROJECT INTRO -->

<img src='https://svgshare.com/i/__W.svg' title='Orfi_temporary' height="150">

OrpheusDL
=========

A modular music archival program

[Report Bug](https://github.com/OrfiTeam/OrpheusDL/issues)
·
[Request Feature](https://github.com/OrfiTeam/OrpheusDL/issues)


## Table of content

- [About OrpheusDL](#about-orpheusdl)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
    - [Global/Formatting](#globalformatting)
        - [Format variables](#format-variables)
- [Contact](#contact)
- [Acknowledgements](#acknowledgements)



<!-- ABOUT ORPHEUS -->
## About OrpheusDL

OrpheusDL is a modular music archival tool written in Python which allows archiving from multiple different services.


<!-- GETTING STARTED -->
## Getting Started

Follow these steps to get a local copy of Orpheus up and running:

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

### Global/General
```json5
{
    "download_path": "./downloads/",
    "download_quality": "hifi",
    "search_limit": 10,
    "strict_quality_download": false
}
```

`download_path`: Set the absolute or relative output path with `/` as the delimiter

`download_quality`: Choose one of the following settings:
* "hifi": FLAC higher than 44.1/16 if available
* "lossless": FLAC with 44.1/16 if available
* "high": lossy codecs such as MP3, AAC, ... in a higher bitrate
* "medium": lossy codecs such as MP3, AAC, ... in a medium bitrate
* "low": lossy codecs such as MP3, AAC, ... in a lower bitrate

**NOTE: The `download_quality` really depends on the used modules, so check out the modules README.md**

`search_limit`: How many search results are shown

`strict_quality_download`: If enabled, tracks will only be downloaded if the requested quality is available. If the quality is unavailable, the track will be skipped and an error will be logged to `strict_quality_errors.log` with details about the failed download.

#### Quality Enforcement Details

When `strict_quality_download` is enabled, the following quality requirements are enforced:

| Quality Setting | Allowed Codecs | Additional Requirements |
|----------------|----------------|------------------------|
| **lossless** | FLAC, ALAC, WAV | Any bit depth/sample rate |
| **hifi** | FLAC | >16bit OR >44.1kHz sample rate |
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

### Global/Formatting:

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

`track_filename_format`: How tracks are formatted in albums and playlists. The relevant extension is appended to the end.

`album_format`, `playlist_format`, `artist_format`: Base directories for their respective formats - tracks and cover
art are stored here. May have slashes in it, for instance {artist}/{album}.

`single_full_path_format`: How singles are handled, which is separate to how the above work.
Instead, this has both the folder's name and the track's name.

`enable_zfill`: Enables zero padding for `track_number`, `total_tracks`, `disc_number`, `total_discs` if the
corresponding number has more than 2 digits

`force_album_format`: Forces the `album_format` for tracks instead of the `single_full_path_format` and also
uses `album_format` in the `playlist_format` folder 

`source_subdirectories`: If enabled, creates service-specific subdirectories (e.g., "Qobuz", "Tidal", "Deezer") 
within the download path. This helps organize downloads by their source service.

`disc_subdirectories`: If enabled, creates "Disc N" subdirectories for multi-disc albums. If disabled, no disc subdirectories are created and all tracks are placed directly in the album folder.

#### Format variables

`track_filename_format` variables are `{name}`, `{album}`, `{album_artist}`, `{album_id}`, `{track_number}`,
`{total_tracks}`, `{disc_number}`, `{total_discs}`, `{release_date}`, `{release_year}`, `{artist_id}`, `{isrc}`,
`{upc}`, `{explicit}`, `{copyright}`, `{codec}`, `{sample_rate}`, `{bit_depth}`.

`album_format` variables are `{name}`, `{id}`, `{artist}`, `{artist_id}`, `{release_year}`, `{upc}`, `{explicit}`,
`{quality}`, `{artist_initials}`.

`playlist_format` variables are `{name}`, `{creator}`, `{tracks}`, `{release_year}`, `{explicit}`, `{creator_id}`

* `{quality}` will add
    ```
     [Dolby Atmos]
     [96kHz 24bit]
     [M]
    ```
 to the corresponding path (depending on the module)
* `{explicit}` will add
    ```
     [E]
    ```
  to the corresponding path

### Global/Covers

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

| Option               | Info                                                                                     |
|----------------------|------------------------------------------------------------------------------------------|
| embed_cover          | Enable it to embed the album cover inside every track                                    |
| main_compression     | Compression of the main cover                                                            |
| main_resolution      | Resolution (in pixels) of the cover of the module used                                   |
| save_external        | Enable it to save the cover from a third party cover module                              |
| external_format      | Format of the third party cover, supported values: `jpg`, `png`, `webp`                  |
| external_compression | Compression of the third party cover, supported values: `low`, `high`                    |
| external_resolution  | Resolution (in pixels) of the third party cover                                          |
| save_animated_cover  | Enable saving the animated cover when supported from the module (often in MPEG-4 format) |

### Global/Codecs

```json5
{
    "proprietary_codecs": false,
    "spatial_codecs": true
}
```

`proprietary_codecs`: Enable it to allow `MQA`, `E-AC-3 JOC` or `AC-4 IMS`

`spatial_codecs`: Enable it to allow `MPEG-H 3D`, `E-AC-3 JOC` or `AC-4 IMS`

**Note: `spatial_codecs` has priority over `proprietary_codecs` when deciding if a codec is enabled**

### Global/Module_defaults

```json5
{
    "lyrics": "default",
    "covers": "default",
    "credits": "default"
}
```

Change `default` to the module name under `/modules` in order to retrieve `lyrics`, `covers` or `credits` from the
selected module

### Global/Lyrics
```json5
{
    "embed_lyrics": true,
    "embed_synced_lyrics": false,
    "save_synced_lyrics": true
}
```

| Option              | Info                                                                                                                                                                |
|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| embed_lyrics        | Embeds the (unsynced) lyrics inside every track                                                                                                                     |
| embed_synced_lyrics | Embeds the synced lyrics inside every track (needs `embed_lyrics` to be enabled) (required for [Roon](https://community.roonlabs.com/t/1-7-lyrics-tag-guide/85182)) |
| save_synced_lyrics  | Saves the synced lyrics inside a  `.lrc` file in the same directory as the track with the same `track_format` variables                                             |

### Global/Advanced

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

| Option                        | Info                                                                                     |
|-------------------------------|------------------------------------------------------------------------------------------|
| remove_collectors_editions    | If enabled, filters out collector's editions when downloading artists. Detected by keywords: collector, deluxe, expanded, bonus, special, anniversary, remastered, reissue, limited |
| remove_live_recordings        | If enabled, filters out live recordings when downloading artists. Detected by keywords: live, concert, performance, stage, tour, acoustic, unplugged, mtv, bbc, radio, session |
| strict_artist_match           | If enabled, only downloads albums where the album artist exactly matches the requested artist name (case-insensitive) |
| log_unavailable_tracks        | If enabled, logs failed track downloads to `unavailable_tracks.log` with track ID, name, album, and artists |

**Note:** The filtering options (`remove_collectors_editions`, `remove_live_recordings`, and `strict_artist_match`) only apply when downloading artists, not individual albums or tracks.

### Usage Examples

#### Strict Quality Download Examples

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

#### Console Output Examples

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

**When no tracks meet requirements:**
```
=== Album Album Name skipped - no tracks meet quality requirements ===
```

#### Troubleshooting

**Q: Why are all my tracks being skipped?**
A: Check your `download_quality` setting and ensure the tracks are actually available in that quality. Some older releases may only be available in lossy formats.

**Q: Where can I find details about failed downloads?**
A: Failed downloads are logged to `strict_quality_errors.log` in the same directory where you run OrpheusDL.

**Q: Can I use strict quality with any download type?**
A: Yes, strict quality download works with albums, artists, playlists, and individual tracks.

**Q: Will folders be created if no tracks meet quality requirements?**
A: No, folders and cover art are only created when at least one track will be downloaded.

<!-- Contact -->
## Contact

OrfiDev (Project Lead) - [@OrfiDev](https://github.com/OrfiTeam)

Dniel97 (Current Lead Developer) - [@Dniel97](https://github.com/Dniel97)

Project Link: [Orpheus Public GitHub Repository](https://github.com/OrfiTeam/OrpheusDL)



<!-- ACKNOWLEDGEMENTS -->
## Acknowledgements
* Chimera by Aesir - the inspiration to the project
* [Icon modified from a freepik image](https://www.freepik.com/)
