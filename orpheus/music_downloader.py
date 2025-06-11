import logging, os, ffmpeg, sys
import shutil
import unicodedata
from dataclasses import asdict
from time import strftime, gmtime

from ffmpeg import Error

from orpheus.tagging import tag_file
from utils.models import *
from utils.utils import *
from utils.exceptions import *


def beauty_format_seconds(seconds: int) -> str:
    time_data = gmtime(seconds)

    time_format = "%Mm:%Ss"
    # if seconds are higher than 3600s also add the hour format
    if time_data.tm_hour > 0:
        time_format = "%Hh:" + time_format
    # TODO: also add days to time_format if hours > 24?

    # return the formatted time string
    return strftime(time_format, time_data)


class Downloader:
    def __init__(self, settings, module_controls, oprinter, path):
        self.path = path if path.endswith('/') else path + '/' 
        self.third_party_modules = None
        self.download_mode = None
        self.service = None
        self.service_name = None
        self.module_list = module_controls['module_list']
        self.module_settings = module_controls['module_settings']
        self.loaded_modules = module_controls['loaded_modules']
        self.load_module = module_controls['module_loader']
        self.global_settings = settings

        self.oprinter = oprinter
        self.print = self.oprinter.oprint
        self.set_indent_number = self.oprinter.set_indent_number

    def search_by_tags(self, module_name, track_info: TrackInfo):
        return self.loaded_modules[module_name].search(DownloadTypeEnum.track, f'{track_info.name} {" ".join(track_info.artists)}', track_info=track_info)

    def _add_track_m3u_playlist(self, m3u_playlist: str, track_info: TrackInfo, track_location: str):
        if self.global_settings['playlist']['extended_m3u']:
            with open(m3u_playlist, 'a', encoding='utf-8') as f:
                # if no duration exists default to -1
                duration = track_info.duration if track_info.duration else -1
                # write the extended track header
                f.write(f'#EXTINF:{duration}, {track_info.artists[0]} - {track_info.name}\n')

        with open(m3u_playlist, 'a', encoding='utf-8') as f:
            if self.global_settings['playlist']['paths_m3u'] == "absolute":
                # add the absolute paths to the playlist
                f.write(f'{os.path.abspath(track_location)}\n')
            else:
                # add the relative paths to the playlist by subtracting the track_location with the m3u_path
                f.write(f'{os.path.relpath(track_location, os.path.dirname(m3u_playlist))}\n')

            # add an extra new line to the extended format
            f.write('\n') if self.global_settings['playlist']['extended_m3u'] else None

    def _log_unavailable_track(self, track_id, track_info, album_path):
        """Log unavailable tracks to error.txt in the album folder"""
        if not self.global_settings['advanced'].get('log_unavailable_tracks', False):
            return
        
        error_msg = f'Unavailable: {track_info.artists[0] if track_info.artists else "Unknown"} [{track_info.artist_id}]/{track_info.album} [{track_info.album_id}]/{track_info.name} [{track_id}]'
        
        # Create error.txt in the album folder
        error_file = os.path.join(album_path, 'error.txt') if album_path else 'unavailable_tracks.log'
        with open(error_file, 'a', encoding='utf-8') as logf:
            logf.write(f'{error_msg}\n')

    def _log_strict_quality_error(self, track_id, track_info, album_path, requested_quality, codec, bitrate, bit_depth, sample_rate):
        """Log strict quality errors to strict_quality_error.txt in the album folder"""
        if not self.global_settings['general'].get('strict_quality_download', False):
            return
        
        error_msg = f'Not meet quality requirements: {track_info.artists[0] if track_info.artists else "Unknown"} [{track_info.artist_id}]/{track_info.album} [{track_info.album_id}]/{track_info.name} [{track_id}]'
        
        # Create strict_quality_error.txt in the album folder
        error_file = os.path.join(album_path, 'strict_quality_error.txt') if album_path else 'strict_quality_errors.log'
        with open(error_file, 'a', encoding='utf-8') as logf:
            logf.write(f'{error_msg}\n')

    def _check_strict_quality_requirement(self, track_id, track_info, album_path=None, extra_kwargs={}):
        """Check if strict quality download is enabled and if the requested quality is available"""
        if not self.global_settings['general'].get('strict_quality_download', False):
            return True  # Strict quality not enabled, allow download

        requested_quality = self.global_settings['general']['download_quality'].lower()
        codec = track_info.codec
        bitrate = getattr(track_info, 'bitrate', None)
        bit_depth = getattr(track_info, 'bit_depth', None)
        sample_rate = getattr(track_info, 'sample_rate', None)

        # Define allowed codecs for each quality
        allowed = False
        if requested_quality == 'lossless':
            allowed = codec.name in ['FLAC', 'ALAC', 'WAV']
        elif requested_quality == 'hifi':
            allowed = codec.name == 'FLAC' and (bit_depth is None or bit_depth > 16 or (bit_depth == 16 and sample_rate and sample_rate > 44.1))
        elif requested_quality == 'high':
            allowed = codec.name in ['MP3', 'AAC', 'HEAAC', 'VORBIS', 'OPUS'] and bitrate and bitrate >= 256
        elif requested_quality == 'medium':
            allowed = codec.name in ['MP3', 'AAC', 'HEAAC', 'VORBIS', 'OPUS'] and bitrate and 128 <= bitrate < 256
        elif requested_quality == 'low':
            allowed = codec.name in ['MP3', 'AAC', 'HEAAC', 'VORBIS', 'OPUS'] and bitrate and bitrate < 128
        else:
            allowed = True  # fallback: allow

        if track_info.error or track_info.codec == CodecEnum.NONE or not allowed:
            error_msg = f'Strict quality download failed: Requested quality "{requested_quality}" unavailable for: {track_info.artists[0] if track_info.artists else "Unknown"} [{track_info.artist_id}]/{track_info.album} [{track_info.album_id}]/{track_info.name} [{track_id}] (codec: {codec.name}, bitrate: {bitrate}, bit_depth: {bit_depth}, sample_rate: {sample_rate})'
            self.print(error_msg)
            self._log_strict_quality_error(track_id, track_info, album_path, requested_quality, codec, bitrate, bit_depth, sample_rate)
            self.print(f'=== Track {track_id} failed due to strict quality requirements ===', drop_level=1)
            return False
        return True

    def download_playlist(self, playlist_id, custom_module=None, extra_kwargs={}):
        self.set_indent_number(1)

        playlist_info: PlaylistInfo = self.service.get_playlist_info(playlist_id, **extra_kwargs)
        if not playlist_info:
            return

        number_of_tracks = len(playlist_info.tracks)
        self.print(f'=== Downloading playlist {playlist_info.name} ({playlist_id}) ===', drop_level=1)
        self.print(f'Creator: {playlist_info.creator} ({playlist_info.creator_id})')
        if playlist_info.release_year: self.print(f'Year: {playlist_info.release_year}')
        if playlist_info.duration: self.print(f'Duration: {beauty_format_seconds(playlist_info.duration)}')
        self.print(f'Number of tracks: {number_of_tracks!s}')
        self.print(f'Service: {self.module_settings[self.service_name].service_name}')
        
        # --- SOURCE SUBDIRECTORIES AT ROOT LEVEL ---
        playlist_path = self.path
        if self.global_settings['formatting'].get('source_subdirectories', False):
            service_folder = self.module_settings[self.service_name].service_name
            playlist_path += f'{service_folder}/'

        # Create playlist folder
        playlist_tags = {k: sanitise_name(v) for k, v in asdict(playlist_info).items()}
        playlist_tags['explicit'] = ' [E]' if playlist_info.explicit else ''
        playlist_path += self.global_settings['formatting']['playlist_format'].format(**playlist_tags)
        playlist_path = fix_byte_limit(playlist_path) + '/'

        tracks_errored = set()
        m3u_playlist_path = None

        if custom_module:
            supported_modes = self.module_settings[custom_module].module_supported_modes 
            if ModuleModes.download not in supported_modes and ModuleModes.playlist not in supported_modes:
                raise Exception(f'Module "{custom_module}" cannot be used to download a playlist') # TODO: replace with ModuleDoesNotSupportAbility
            self.print(f'Service used for downloading: {self.module_settings[custom_module].service_name}')
            original_service = str(self.service_name)
            self.load_module(custom_module)
            
            # Check each track and download if quality requirements are met
            successful_tracks = []
            for index, track_id in enumerate(playlist_info.tracks, start=1):
                self.set_indent_number(2)
                print()
                self.print(f'Track {index}/{number_of_tracks}', drop_level=1)
                quality_tier = QualityEnum[self.global_settings['general']['download_quality'].upper()]
                codec_options = CodecOptions(
                    spatial_codecs = self.global_settings['codecs']['spatial_codecs'],
                    proprietary_codecs = self.global_settings['codecs']['proprietary_codecs'],
                )
                track_info: TrackInfo = self.loaded_modules[original_service].get_track_info(track_id, quality_tier, codec_options, **playlist_info.track_extra_kwargs)
                
                # Check if track is unavailable first
                if track_info.error:
                    self._log_unavailable_track(track_id, track_info, playlist_path)
                    self.print(track_info.error)
                    self.print(f'=== Track {track_id} failed ===', drop_level=1)
                    tracks_errored.add(f'{track_info.name} - {track_info.artists[0]}')
                    continue
                
                # Check quality requirements
                if not self._check_strict_quality_requirement(track_id, track_info, playlist_path):
                    tracks_errored.add(f'{track_info.name} - {track_info.artists[0]}')
                    continue
                
                self.service = self.loaded_modules[custom_module]
                self.service_name = custom_module
                results = self.search_by_tags(custom_module, track_info)
                track_id_new = results[0].result_id if len(results) else None
                
                if track_id_new:
                    # Create folder and download covers on first successful track
                    if not successful_tracks:
                        os.makedirs(playlist_path, exist_ok=True)

                        # Download playlist cover if present
                        if playlist_info.cover_url:
                            self.print('Downloading playlist cover')
                            download_file(playlist_info.cover_url, f'{playlist_path}cover.{playlist_info.cover_type.name}', artwork_settings=self._get_artwork_settings())

                        if playlist_info.animated_cover_url and self.global_settings['covers']['save_animated_cover']:
                            self.print('Downloading animated playlist cover')
                            download_file(playlist_info.animated_cover_url, playlist_path + 'cover.mp4', enable_progress_bar=True)

                        if playlist_info.description:
                            with open(playlist_path + 'description.txt', 'w', encoding='utf-8') as f:
                                f.write(playlist_info.description)

                        if self.global_settings['playlist']['save_m3u']:
                            m3u_playlist_path = playlist_path + playlist_info.name + '.m3u'
                            with open(m3u_playlist_path, 'w', encoding='utf-8') as m3u_playlist:
                                m3u_playlist.write('#EXTM3U\n')
                                m3u_playlist.write(f'#EXTINF:-1,{playlist_info.name}\n')
                                m3u_playlist.write(f'{playlist_path}\n')
                                m3u_playlist.write('\n') if self.global_settings['playlist']['extended_m3u'] else None
                        else:
                            m3u_playlist_path = None
                    else:
                        m3u_playlist_path = playlist_path + playlist_info.name + '.m3u' if self.global_settings['playlist']['save_m3u'] else None
                    
                    # Download the track
                    if self.download_track(track_id_new, album_location=playlist_path, track_index=len(successful_tracks)+1, number_of_tracks=number_of_tracks, indent_level=2, m3u_playlist=m3u_playlist_path, extra_kwargs=results[0].extra_kwargs):
                        successful_tracks.append((track_id_new, results[0].extra_kwargs))
                else:
                    tracks_errored.add(f'{track_info.name} - {track_info.artists[0]}')
                    if ModuleModes.download in self.module_settings[original_service].module_supported_modes:
                        self.service = self.loaded_modules[original_service]
                        self.service_name = original_service
                        self.print(f'Track {track_info.name} not found, using the original service as a fallback', drop_level=1)
                        
                        # Create folder and download covers on first successful track
                        if not successful_tracks:
                            os.makedirs(playlist_path, exist_ok=True)

                            # Download playlist cover if present
                            if playlist_info.cover_url:
                                self.print('Downloading playlist cover')
                                download_file(playlist_info.cover_url, f'{playlist_path}cover.{playlist_info.cover_type.name}', artwork_settings=self._get_artwork_settings())

                            if playlist_info.animated_cover_url and self.global_settings['covers']['save_animated_cover']:
                                self.print('Downloading animated playlist cover')
                                download_file(playlist_info.animated_cover_url, playlist_path + 'cover.mp4', enable_progress_bar=True)

                            if playlist_info.description:
                                with open(playlist_path + 'description.txt', 'w', encoding='utf-8') as f:
                                    f.write(playlist_info.description)

                            if self.global_settings['playlist']['save_m3u']:
                                m3u_playlist_path = playlist_path + playlist_info.name + '.m3u'
                                with open(m3u_playlist_path, 'w', encoding='utf-8') as m3u_playlist:
                                    m3u_playlist.write('#EXTM3U\n')
                                    m3u_playlist.write(f'#EXTINF:-1,{playlist_info.name}\n')
                                    m3u_playlist.write(f'{playlist_path}\n')
                                    m3u_playlist.write('\n') if self.global_settings['playlist']['extended_m3u'] else None
                            else:
                                m3u_playlist_path = None
                        else:
                            m3u_playlist_path = playlist_path + playlist_info.name + '.m3u' if self.global_settings['playlist']['save_m3u'] else None
                        
                        if self.download_track(track_id, album_location=playlist_path, track_index=len(successful_tracks)+1, number_of_tracks=number_of_tracks, indent_level=2, m3u_playlist=m3u_playlist_path, extra_kwargs=playlist_info.track_extra_kwargs):
                            successful_tracks.append((track_id, playlist_info.track_extra_kwargs))
                    else:
                        self.print(f'Track {track_info.name} not found, skipping')
        else:
            # Check each track and download if quality requirements are met
            successful_tracks = []
            for index, track_id in enumerate(playlist_info.tracks, start=1):
                self.set_indent_number(2)
                print()
                self.print(f'Track {index}/{number_of_tracks}', drop_level=1)
                quality_tier = QualityEnum[self.global_settings['general']['download_quality'].upper()]
                codec_options = CodecOptions(
                    spatial_codecs = self.global_settings['codecs']['spatial_codecs'],
                    proprietary_codecs = self.global_settings['codecs']['proprietary_codecs'],
                )
                track_info: TrackInfo = self.service.get_track_info(track_id, quality_tier, codec_options, **playlist_info.track_extra_kwargs)
                
                # Check if track is unavailable first
                if track_info.error:
                    self._log_unavailable_track(track_id, track_info, playlist_path)
                    self.print(track_info.error)
                    self.print(f'=== Track {track_id} failed ===', drop_level=1)
                    tracks_errored.add(f'{track_info.name} - {track_info.artists[0]}')
                    continue
                
                # Check quality requirements
                if not self._check_strict_quality_requirement(track_id, track_info, playlist_path):
                    tracks_errored.add(f'{track_info.name} - {track_info.artists[0]}')
                    continue
                
                # Create folder and download covers on first successful track
                if not successful_tracks:
                    os.makedirs(playlist_path, exist_ok=True)

                    # Download playlist cover if present
                    if playlist_info.cover_url:
                        self.print('Downloading playlist cover')
                        download_file(playlist_info.cover_url, f'{playlist_path}cover.{playlist_info.cover_type.name}', artwork_settings=self._get_artwork_settings())

                    if playlist_info.animated_cover_url and self.global_settings['covers']['save_animated_cover']:
                        self.print('Downloading animated playlist cover')
                        download_file(playlist_info.animated_cover_url, playlist_path + 'cover.mp4', enable_progress_bar=True)

                    if playlist_info.description:
                        with open(playlist_path + 'description.txt', 'w', encoding='utf-8') as f:
                            f.write(playlist_info.description)

                    if self.global_settings['playlist']['save_m3u']:
                        m3u_playlist_path = playlist_path + playlist_info.name + '.m3u'
                        with open(m3u_playlist_path, 'w', encoding='utf-8') as m3u_playlist:
                            m3u_playlist.write('#EXTM3U\n')
                            m3u_playlist.write(f'#EXTINF:-1,{playlist_info.name}\n')
                            m3u_playlist.write(f'{playlist_path}\n')
                            m3u_playlist.write('\n') if self.global_settings['playlist']['extended_m3u'] else None
                    else:
                        m3u_playlist_path = None
                else:
                    m3u_playlist_path = playlist_path + playlist_info.name + '.m3u' if self.global_settings['playlist']['save_m3u'] else None
                
                # Download the track
                if self.download_track(track_id, album_location=playlist_path, track_index=len(successful_tracks)+1, number_of_tracks=number_of_tracks, indent_level=2, m3u_playlist=m3u_playlist_path, extra_kwargs=playlist_info.track_extra_kwargs):
                    successful_tracks.append(track_id)

        self.set_indent_number(1)
        if successful_tracks:
            self.print(f'=== Playlist {playlist_info.name} downloaded ({len(successful_tracks)}/{number_of_tracks} tracks) ===', drop_level=1)
        else:
            self.print(f'=== Playlist {playlist_info.name} skipped - no tracks meet quality requirements ===', drop_level=1)

        if tracks_errored: logging.debug('Failed tracks: ' + ', '.join(tracks_errored))

    @staticmethod
    def _get_artist_initials_from_name(album_info: AlbumInfo) -> str:
        # Remove "the" from the inital string
        initial = album_info.artist.lower()
        if album_info.artist.lower().startswith('the'):
            initial = initial.replace('the ', '')[0].upper()

        # Unicode fix
        initial = unicodedata.normalize('NFKD', initial[0]).encode('ascii', 'ignore').decode('utf-8')

        # Make the initial upper if it's alpha
        initial = initial.upper() if initial.isalpha() else '#'

        return initial

    def _create_album_location(self, path: str, album_id: str, album_info: AlbumInfo) -> str:
        # Clean up album tags and add special explicit and additional formats
        album_tags = {k: sanitise_name(v) for k, v in asdict(album_info).items()}
        album_tags['id'] = str(album_id)
        album_tags['quality'] = f' [{album_info.quality}]' if album_info.quality else ''
        album_tags['explicit'] = ' [E]' if album_info.explicit else ''
        album_tags['artist_initials'] = self._get_artist_initials_from_name(album_info)

        # Source subdirectories are now handled at the root level, not here
        album_path = path + self.global_settings['formatting']['album_format'].format(**album_tags)
        # fix path byte limit
        album_path = fix_byte_limit(album_path) + '/'
        os.makedirs(album_path, exist_ok=True)

        return album_path

    def _download_album_files(self, album_path: str, album_info: AlbumInfo):
        if album_info.cover_url:
            self.print('Downloading album cover')
            download_file(album_info.cover_url, f'{album_path}cover.{album_info.cover_type.name}', artwork_settings=self._get_artwork_settings())

        if album_info.animated_cover_url and self.global_settings['covers']['save_animated_cover']:
            self.print('Downloading animated album cover')
            download_file(album_info.animated_cover_url, album_path + 'cover.mp4', enable_progress_bar=True)

        if album_info.description:
            with open(album_path + 'description.txt', 'w', encoding='utf-8') as f:
                f.write(album_info.description)  # Also add support for this with singles maybe?

    def download_album(self, album_id, artist_name='', path=None, indent_level=1, extra_kwargs={}):
        self.set_indent_number(indent_level)

        album_info: AlbumInfo = self.service.get_album_info(album_id, **extra_kwargs)
        if not album_info:
            return []
        number_of_tracks = len(album_info.tracks)
        
        # --- SOURCE SUBDIRECTORIES AT ROOT LEVEL ---
        if path is None:
            path = self.path
            if self.global_settings['formatting'].get('source_subdirectories', False):
                service_folder = self.module_settings[self.service_name].service_name
                path += f'{service_folder}/'
        else:
            # If path is provided (e.g., from artist download), source subdirectories are already applied
            pass

        if number_of_tracks > 1 or self.global_settings['formatting']['force_album_format']:
            # Don't create album folder yet - wait until we know at least one track will be downloaded
            album_path = None
            successful_tracks = []
            
            if self.download_mode is DownloadTypeEnum.album:
                self.set_indent_number(1)
            elif self.download_mode is DownloadTypeEnum.artist:
                self.set_indent_number(2)

            self.print(f'=== Downloading album {album_info.name} ({album_id}) ===', drop_level=1)
            self.print(f'Artist: {album_info.artist} ({album_info.artist_id})')
            if album_info.release_year: self.print(f'Year: {album_info.release_year}')
            if album_info.duration: self.print(f'Duration: {beauty_format_seconds(album_info.duration)}')
            self.print(f'Number of tracks: {number_of_tracks!s}')
            self.print(f'Service: {self.module_settings[self.service_name].service_name}')

            # Check each track and download if quality requirements are met
            for index, track_id in enumerate(album_info.tracks, start=1):
                self.set_indent_number(indent_level + 1)
                print()
                self.print(f'Track {index}/{number_of_tracks}', drop_level=1)
                
                # Check if track meets quality requirements before creating folder
                quality_tier = QualityEnum[self.global_settings['general']['download_quality'].upper()]
                codec_options = CodecOptions(
                    spatial_codecs = self.global_settings['codecs']['spatial_codecs'],
                    proprietary_codecs = self.global_settings['codecs']['proprietary_codecs'],
                )
                track_info: TrackInfo = self.service.get_track_info(track_id, quality_tier, codec_options, **album_info.track_extra_kwargs)
                
                # Create album path first for logging purposes
                if album_path is None:
                    album_path = self._create_album_location(path, album_id, album_info)
                
                # Check if track is unavailable first
                if track_info.error:
                    self._log_unavailable_track(track_id, track_info, album_path)
                    self.print(track_info.error)
                    self.print(f'=== Track {track_id} failed ===', drop_level=1)
                    continue
                
                # Check quality requirements
                if not self._check_strict_quality_requirement(track_id, track_info, album_path):
                    continue  # Skip this track
                
                # Create folder and download covers on first successful track
                if not successful_tracks:
                    if album_info.booklet_url and not os.path.exists(album_path + 'Booklet.pdf'):
                        self.print('Downloading booklet')
                        download_file(album_info.booklet_url, album_path + 'Booklet.pdf')
                    
                    cover_temp_location = download_to_temp(album_info.all_track_cover_jpg_url) if album_info.all_track_cover_jpg_url else ''

                    # Download booklet, animated album cover and album cover if present
                    self._download_album_files(album_path, album_info)
                else:
                    cover_temp_location = ''

                # Download the track
                if self.download_track(track_id, album_location=album_path, track_index=len(successful_tracks)+1, number_of_tracks=number_of_tracks, main_artist=artist_name, cover_temp_location=cover_temp_location, indent_level=indent_level+1, extra_kwargs=album_info.track_extra_kwargs):
                    successful_tracks.append(track_id)
                    if cover_temp_location: silentremove(cover_temp_location)

            self.set_indent_number(indent_level)
            if successful_tracks:
                self.print(f'=== Album {album_info.name} downloaded ({len(successful_tracks)}/{number_of_tracks} tracks) ===', drop_level=1)
            else:
                self.print(f'=== Album {album_info.name} skipped - no tracks meet quality requirements ===', drop_level=1)
        elif number_of_tracks == 1:
            # For single tracks, check quality first
            quality_tier = QualityEnum[self.global_settings['general']['download_quality'].upper()]
            codec_options = CodecOptions(
                spatial_codecs = self.global_settings['codecs']['spatial_codecs'],
                proprietary_codecs = self.global_settings['codecs']['proprietary_codecs'],
            )
            track_info: TrackInfo = self.service.get_track_info(album_info.tracks[0], quality_tier, codec_options, **album_info.track_extra_kwargs)
            
            # Create album path for logging purposes
            album_path = self._create_album_location(path, album_id, album_info)
            
            # Check if track is unavailable first
            if track_info.error:
                self._log_unavailable_track(album_info.tracks[0], track_info, album_path)
                self.print(track_info.error)
                self.print(f'=== Track {album_info.tracks[0]} failed ===', drop_level=1)
                return []
            
            if self._check_strict_quality_requirement(album_info.tracks[0], track_info, album_path):
                return self.download_track(album_info.tracks[0], album_location=album_path, number_of_tracks=1, main_artist=artist_name, indent_level=indent_level, extra_kwargs=album_info.track_extra_kwargs)
            else:
                self.print(f'=== Single track album {album_info.name} skipped - does not meet quality requirements ===', drop_level=1)
                return []

        return successful_tracks if 'successful_tracks' in locals() else []

    def download_artist(self, artist_id, extra_kwargs={}):
        # Get basic artist info first (just the name)
        artist_name = self.service.session.get_artist_name(artist_id) if hasattr(self.service, 'session') else None
        if not artist_name:
            # Fallback to the original method if session is not available
            artist_info: ArtistInfo = self.service.get_artist_info(artist_id, self.global_settings['artist_downloading']['return_credited_albums'], **extra_kwargs)
            artist_name = artist_info.name
        else:
            # Create a minimal artist_info for compatibility
            artist_info = ArtistInfo(name=artist_name, albums=[], tracks=[])

        self.set_indent_number(1)
        self.print(f'=== Downloading artist {artist_name} ({artist_id}) ===', drop_level=1)
        self.print(f'Service: {self.module_settings[self.service_name].service_name}')
        
        # --- SOURCE SUBDIRECTORIES AT ROOT LEVEL ---
        base_path = self.path
        if self.global_settings['formatting'].get('source_subdirectories', False):
            service_folder = self.module_settings[self.service_name].service_name
            base_path += f'{service_folder}/'

        # --- PROCESS ALBUMS IN BATCHES ---
        batch_size = 50  # Process 50 albums at a time
        start = 0
        album_count = 0
        filtered_album_count = 0
        tracks_downloaded = []
        
        self.print('Processing albums in batches...', drop_level=1)
        
        while True:
            # Get a batch of album IDs
            if hasattr(self.service, 'session'):
                # Use direct API call for pagination
                album_ids = self.service.session.get_artist_album_ids(
                    artist_id, 
                    start, 
                    batch_size, 
                    self.global_settings['artist_downloading']['return_credited_albums']
                )
            else:
                # Fallback: get all albums and slice them
                all_albums = self.service.session.get_artist_album_ids(
                    artist_id, 
                    0, 
                    -1, 
                    self.global_settings['artist_downloading']['return_credited_albums']
                )
                album_ids = all_albums[start:start + batch_size]
            
            # If no more albums, break
            if not album_ids:
                break
                
            album_count += len(album_ids)
            self.print(f'Processing batch: albums {start + 1}-{start + len(album_ids)} (total found so far: {album_count})', drop_level=1)
            
            # Process each album in the batch
            for album_id in album_ids:
                try:
                    # Get album info
                    album_info = self.service.get_album_info(album_id)
                    
                    # Apply filters
                    should_skip = False
                    
                    # Remove collector's editions
                    if self.global_settings['advanced'].get('remove_collectors_editions', False):
                        collectors_keywords = ['collector', 'deluxe', 'expanded', 'bonus', 'special', 'anniversary', 'remastered', 'reissue', 'limited']
                        if any(keyword in album_info.name.lower() for keyword in collectors_keywords):
                            self.print(f'Skipping collector edition: {album_info.name}', drop_level=2)
                            should_skip = True
                    
                    # Remove live recordings
                    if not should_skip and self.global_settings['advanced'].get('remove_live_recordings', False):
                        live_keywords = ['live', 'concert', 'performance', 'stage', 'tour', 'acoustic', 'unplugged', 'mtv', 'bbc', 'radio', 'session']
                        if any(keyword in album_info.name.lower() for keyword in live_keywords):
                            self.print(f'Skipping live recording: {album_info.name}', drop_level=2)
                            should_skip = True
                    
                    # Strict artist match
                    if not should_skip and self.global_settings['advanced'].get('strict_artist_match', False):
                        if album_info.artist.strip().lower() != artist_name.strip().lower():
                            self.print(f'Skipping different artist: {album_info.name} (by {album_info.artist})', drop_level=2)
                            should_skip = True
                    
                    if should_skip:
                        continue
                    
                    # Album passed all filters, download it
                    filtered_album_count += 1
                    print()
                    self.print(f'Album {filtered_album_count}: {album_info.name}', drop_level=1)
                    
                    # Download the album and collect track IDs
                    album_tracks = self.download_album(album_id, artist_name=artist_name, path=base_path, indent_level=2, extra_kwargs=artist_info.album_extra_kwargs)
                    tracks_downloaded.extend(album_tracks)
                    
                except Exception as e:
                    self.print(f'Error processing album {album_id}: {str(e)}', drop_level=2)
                    continue
            
            # Move to next batch
            start += batch_size
            
            # If we got fewer albums than requested, we've reached the end
            if len(album_ids) < batch_size:
                break

        # --- PROCESS SEPARATE TRACKS ---
        self.set_indent_number(2)
        skip_tracks = self.global_settings['artist_downloading']['separate_tracks_skip_downloaded']
        
        # Only process separate tracks if we have them and the setting allows
        if hasattr(artist_info, 'tracks') and artist_info.tracks:
            tracks_to_download = [i for i in artist_info.tracks if (i not in tracks_downloaded and skip_tracks) or not skip_tracks]
            number_of_tracks_new = len(tracks_to_download)
            
            if number_of_tracks_new > 0:
                self.print(f'Processing {number_of_tracks_new} separate tracks...', drop_level=1)
                for index, track_id in enumerate(tracks_to_download, start=1):
                    print()
                    self.print(f'Track {index}/{number_of_tracks_new}', drop_level=1)
                    self.download_track(track_id, album_location=base_path, main_artist=artist_name, number_of_tracks=1, indent_level=2, extra_kwargs=artist_info.track_extra_kwargs)

        # --- FINAL SUMMARY ---
        self.set_indent_number(1)
        self.print(f'=== Artist {artist_name} download completed ===', drop_level=1)
        self.print(f'Total albums found: {album_count}', drop_level=1)
        self.print(f'Albums downloaded: {filtered_album_count}', drop_level=1)
        if hasattr(artist_info, 'tracks') and artist_info.tracks:
            tracks_skipped = len(artist_info.tracks) - len(tracks_to_download) if 'tracks_to_download' in locals() else 0
            if tracks_skipped > 0:
                self.print(f'Tracks skipped: {tracks_skipped}', drop_level=1)

    def download_track(self, track_id, album_location='', main_artist='', track_index=0, number_of_tracks=0, cover_temp_location='', indent_level=1, m3u_playlist=None, extra_kwargs={}):
        quality_tier = QualityEnum[self.global_settings['general']['download_quality'].upper()]
        codec_options = CodecOptions(
            spatial_codecs = self.global_settings['codecs']['spatial_codecs'],
            proprietary_codecs = self.global_settings['codecs']['proprietary_codecs'],
        )
        track_info: TrackInfo = self.service.get_track_info(track_id, quality_tier, codec_options, **extra_kwargs)
        
        if track_info.error:
            self._log_unavailable_track(track_id, track_info, album_location)
            self.print(track_info.error)
            self.print(f'=== Track {track_id} failed ===', drop_level=1)
            return False

        if not self._check_strict_quality_requirement(track_id, track_info, album_location):
            return False
        
        if main_artist.lower() not in [i.lower() for i in track_info.artists] and self.global_settings['advanced']['ignore_different_artists'] and self.download_mode is DownloadTypeEnum.artist:
           self.print('Track is not from the correct artist, skipping', drop_level=1)
           return False

        if not self.global_settings['formatting']['force_album_format']:
            if track_index:
                track_info.tags.track_number = track_index
            if number_of_tracks:
                track_info.tags.total_tracks = number_of_tracks
        zfill_number = len(str(track_info.tags.total_tracks)) if self.download_mode is not DownloadTypeEnum.track else 1
        zfill_lambda = lambda input : sanitise_name(str(input)).zfill(zfill_number) if input is not None else None

        # Separate copy of tags for formatting purposes
        zfill_enabled, zfill_list = self.global_settings['formatting']['enable_zfill'], ['track_number', 'total_tracks', 'disc_number', 'total_discs']
        track_tags = {k: (zfill_lambda(v) if zfill_enabled and k in zfill_list else sanitise_name(v)) for k, v in {**asdict(track_info.tags), **asdict(track_info)}.items()}
        track_tags['explicit'] = ' [E]' if track_info.explicit else ''
        track_tags['artist'] = sanitise_name(track_info.artists[0])  # if len(track_info.artists) == 1 else 'Various Artists'
        codec = track_info.codec

        self.set_indent_number(indent_level)
        self.print(f'=== Downloading track {track_info.name} ({track_id}) ===', drop_level=1)

        if self.download_mode is not DownloadTypeEnum.album and track_info.album: self.print(f'Album: {track_info.album} ({track_info.album_id})')
        if self.download_mode is not DownloadTypeEnum.artist: self.print(f'Artists: {", ".join(track_info.artists)} ({track_info.artist_id})')
        if track_info.release_year: self.print(f'Release year: {track_info.release_year!s}')
        if track_info.duration: self.print(f'Duration: {beauty_format_seconds(track_info.duration)}')
        if self.download_mode is DownloadTypeEnum.track: self.print(f'Service: {self.module_settings[self.service_name].service_name}')

        to_print = 'Codec: ' + codec_data[codec].pretty_name
        if track_info.bitrate: to_print += f', bitrate: {track_info.bitrate!s}kbps'
        if track_info.bit_depth: to_print += f', bit depth: {track_info.bit_depth!s}bit'
        if track_info.sample_rate: to_print += f', sample rate: {track_info.sample_rate!s}kHz'
        self.print(to_print)

        album_location = album_location.replace('\\', '/')

        # Ignores "single_full_path_format" and just downloads every track as an album
        if self.global_settings['formatting']['force_album_format'] and self.download_mode in {
            DownloadTypeEnum.track, DownloadTypeEnum.playlist}:
            # Fetch every needed album_info tag and create an album_location
            album_info: AlbumInfo = self.service.get_album_info(track_info.album_id)
            # Save the playlist path to save all the albums in the playlist path
            path = self.path if album_location == '' else album_location
            # Apply source subdirectories if not already applied
            if album_location == '' and self.global_settings['formatting'].get('source_subdirectories', False):
                service_folder = self.module_settings[self.service_name].service_name
                path += f'{service_folder}/'
            album_location = self._create_album_location(path, track_info.album_id, album_info)
            album_location = album_location.replace('\\', '/')

            # Download booklet, animated album cover and album cover if present
            self._download_album_files(album_location, album_info)

        if self.download_mode is DownloadTypeEnum.track and not self.global_settings['formatting']['force_album_format']:  # Python 3.10 can't become popular sooner, ugh
            # Apply source subdirectories for individual track downloads
            track_path = self.path
            if self.global_settings['formatting'].get('source_subdirectories', False):
                service_folder = self.module_settings[self.service_name].service_name
                track_path += f'{service_folder}/'
            track_location_name = track_path + self.global_settings['formatting']['single_full_path_format'].format(**track_tags)
        elif track_info.tags.total_tracks == 1 and not self.global_settings['formatting']['force_album_format']:
            track_location_name = album_location + self.global_settings['formatting']['single_full_path_format'].format(**track_tags)
        else:
            if track_info.tags.total_discs and track_info.tags.total_discs > 1 and self.global_settings['formatting'].get('disc_subdirectories', False):
                album_location += f'Disc {track_info.tags.disc_number!s}/'
            track_location_name = album_location + self.global_settings['formatting']['track_filename_format'].format(**track_tags)
        # fix file byte limit
        track_location_name = fix_byte_limit(track_location_name)
        os.makedirs(track_location_name[:track_location_name.rfind('/')], exist_ok=True)

        try:
            conversions = {CodecEnum[k.upper()]: CodecEnum[v.upper()] for k, v in self.global_settings['advanced']['codec_conversions'].items()}
        except:
            conversions = {}
            self.print('Warning: codec_conversions setting is invalid!')
        
        container = codec_data[codec].container
        track_location = f'{track_location_name}.{container.name}'

        check_codec = conversions[track_info.codec] if track_info.codec in conversions else track_info.codec
        check_location = f'{track_location_name}.{codec_data[check_codec].container.name}'

        if os.path.isfile(check_location) and not self.global_settings['advanced']['ignore_existing_files']:
            self.print('Track file already exists')

            # also make sure to add already existing tracks to the m3u playlist
            if m3u_playlist:
                self._add_track_m3u_playlist(m3u_playlist, track_info, track_location)

            self.print(f'=== Track {track_id} skipped ===', drop_level=1)
            return True  # Consider existing files as successful

        if track_info.description:
            with open(track_location_name + '.txt', 'w', encoding='utf-8') as f: f.write(track_info.description)

        # Begin process
        print()
        self.print("Downloading track file")
        try:
            download_info: TrackDownloadInfo = self.service.get_track_download(**track_info.download_extra_kwargs)
            download_file(download_info.file_url, track_location, headers=download_info.file_url_headers, enable_progress_bar=True, indent_level=self.oprinter.indent_number) \
                if download_info.download_type is DownloadEnum.URL else shutil.move(download_info.temp_file_path, track_location)

            # check if get_track_download returns a different codec, for example ffmpeg failed
            if download_info.different_codec:
                # overwrite the old known codec with the new
                codec = download_info.different_codec
                container = codec_data[codec].container
                old_track_location = track_location
                # create the new track_location and move the old file to the new location
                track_location = f'{track_location_name}.{container.name}'
                shutil.move(old_track_location, track_location)
        except KeyboardInterrupt:
            self.print('^C pressed, exiting')
            sys.exit(0)
        except Exception:
            if self.global_settings['advanced']['debug_mode']: raise
            self.print('Warning: Track download failed: ' + str(sys.exc_info()[1]))
            self.print(f'=== Track {track_id} failed ===', drop_level=1)
            return False

        delete_cover = False
        if not cover_temp_location:
            cover_temp_location = create_temp_filename()
            delete_cover = True
            covers_module_name = self.third_party_modules[ModuleModes.covers]
            covers_module_name = covers_module_name if covers_module_name != self.service_name else None
            if covers_module_name: print()
            self.print('Downloading artwork' + ((' with ' + covers_module_name) if covers_module_name else ''))
            
            jpg_cover_options = CoverOptions(file_type=ImageFileTypeEnum.jpg, resolution=self.global_settings['covers']['main_resolution'], \
                compression=CoverCompressionEnum[self.global_settings['covers']['main_compression'].lower()])
            ext_cover_options = CoverOptions(file_type=ImageFileTypeEnum[self.global_settings['covers']['external_format']], \
                resolution=self.global_settings['covers']['external_resolution'], \
                compression=CoverCompressionEnum[self.global_settings['covers']['external_compression'].lower()])
            
            if covers_module_name:
                default_temp = download_to_temp(track_info.cover_url)
                test_cover_options = CoverOptions(file_type=ImageFileTypeEnum.jpg, resolution=get_image_resolution(default_temp), compression=CoverCompressionEnum.high)
                cover_module = self.loaded_modules[covers_module_name]
                rms_threshold = self.global_settings['advanced']['cover_variance_threshold']

                results: list[SearchResult] = self.search_by_tags(covers_module_name, track_info)
                self.print('Covers to test: ' + str(len(results)))
                attempted_urls = []
                for i, r in enumerate(results, start=1):
                    test_cover_info: CoverInfo = cover_module.get_track_cover(r.result_id, test_cover_options, **r.extra_kwargs)
                    if test_cover_info.url not in attempted_urls:
                        attempted_urls.append(test_cover_info.url)
                        test_temp = download_to_temp(test_cover_info.url)
                        rms = compare_images(default_temp, test_temp)
                        silentremove(test_temp)
                        self.print(f'Attempt {i} RMS: {rms!s}') # The smaller the root mean square, the closer the image is to the desired one
                        if rms < rms_threshold:
                            self.print('Match found below threshold ' + str(rms_threshold))
                            jpg_cover_info: CoverInfo = cover_module.get_track_cover(r.result_id, jpg_cover_options, **r.extra_kwargs)
                            download_file(jpg_cover_info.url, cover_temp_location, artwork_settings=self._get_artwork_settings(covers_module_name))
                            silentremove(default_temp)
                            if self.global_settings['covers']['save_external']:
                                ext_cover_info: CoverInfo = cover_module.get_track_cover(r.result_id, ext_cover_options, **r.extra_kwargs)
                                download_file(ext_cover_info.url, f'{track_location_name}.{ext_cover_info.file_type.name}', artwork_settings=self._get_artwork_settings(covers_module_name, is_external=True))
                            break
                else:
                    self.print('Third-party module could not find cover, using fallback')
                    shutil.move(default_temp, cover_temp_location)
            else:
                download_file(track_info.cover_url, cover_temp_location, artwork_settings=self._get_artwork_settings())
                if self.global_settings['covers']['save_external'] and ModuleModes.covers in self.module_settings[self.service_name].module_supported_modes:
                    ext_cover_info: CoverInfo = self.service.get_track_cover(track_id, ext_cover_options, **track_info.cover_extra_kwargs)
                    download_file(ext_cover_info.url, f'{track_location_name}.{ext_cover_info.file_type.name}', artwork_settings=self._get_artwork_settings(is_external=True))

        if track_info.animated_cover_url and self.global_settings['covers']['save_animated_cover']:
            self.print('Downloading animated cover')
            download_file(track_info.animated_cover_url, track_location_name + '_cover.mp4', enable_progress_bar=True)

        # Get lyrics
        embedded_lyrics = ''
        if self.global_settings['lyrics']['embed_lyrics'] or self.global_settings['lyrics']['save_synced_lyrics']:
            lyrics_info = LyricsInfo()
            if self.third_party_modules[ModuleModes.lyrics] and self.third_party_modules[ModuleModes.lyrics] != self.service_name:
                lyrics_module_name = self.third_party_modules[ModuleModes.lyrics]
                self.print('Retrieving lyrics' + ((' with ' + lyrics_module_name) if lyrics_module_name else ''))
                lyrics_module = self.loaded_modules[lyrics_module_name]
                results: list[SearchResult] = self.search_by_tags(lyrics_module_name, track_info)
                if results:
                    lyrics_info = lyrics_module.get_track_lyrics(results[0].result_id, **results[0].extra_kwargs)
            elif ModuleModes.lyrics in self.module_settings[self.service_name].module_supported_modes:
                self.print('Retrieving lyrics')
                lyrics_info = self.service.get_track_lyrics(track_id, **track_info.lyrics_extra_kwargs)
            
            if lyrics_info.embedded:
                embedded_lyrics = lyrics_info.embedded
                if self.global_settings['lyrics']['save_synced_lyrics'] and lyrics_info.synced:
                    with open(track_location_name + '.lrc', 'w', encoding='utf-8') as f: f.write(lyrics_info.synced)

        # Get credits
        credits_list = []
        if self.third_party_modules[ModuleModes.credits] and self.third_party_modules[ModuleModes.credits] != self.service_name:
            credits_module_name = self.third_party_modules[ModuleModes.credits]
            self.print('Retrieving credits' + ((' with ' + credits_module_name) if credits_module_name else ''))
            credits_module = self.loaded_modules[credits_module_name]
            results: list[SearchResult] = self.search_by_tags(credits_module_name, track_info)
            if results:
                credits_list = credits_module.get_track_credits(results[0].result_id, **results[0].extra_kwargs)
        elif ModuleModes.credits in self.module_settings[self.service_name].module_supported_modes:
            self.print('Retrieving credits')
            credits_list = self.service.get_track_credits(track_id, **track_info.credits_extra_kwargs)
            # if credits_list:
            #     self.print('Credits retrieved')
            # else:
            #     self.print('No credits available')
        
        # Do conversions
        old_track_location, old_container = None, None
        if codec in conversions:
            old_codec_data = codec_data[codec]
            new_codec = conversions[codec]
            new_codec_data = codec_data[new_codec]
            self.print(f'Converting to {new_codec_data.pretty_name}')
                
            if old_codec_data.spatial or new_codec_data.spatial:
                self.print('Warning: converting spacial formats is not allowed, skipping')
            elif not old_codec_data.lossless and new_codec_data.lossless and not self.global_settings['advanced']['enable_undesirable_conversions']:
                self.print('Warning: Undesirable lossy-to-lossless conversion detected, skipping')
            elif not old_codec_data and not self.global_settings['advanced']['enable_undesirable_conversions']:
                self.print('Warning: Undesirable lossy-to-lossy conversion detected, skipping')
            else:
                if not old_codec_data.lossless and new_codec_data.lossless:
                    self.print('Warning: Undesirable lossy-to-lossless conversion')
                elif not old_codec_data:
                    self.print('Warning: Undesirable lossy-to-lossy conversion')

                try:
                    conversion_flags = {CodecEnum[k.upper()]:v for k,v in self.global_settings['advanced']['conversion_flags'].items()}
                except:
                    conversion_flags = {}
                    self.print('Warning: conversion_flags setting is invalid, using defaults')
                
                conv_flags = conversion_flags[new_codec] if new_codec in conversion_flags else {}
                temp_track_location = f'{create_temp_filename()}.{new_codec_data.container.name}'
                new_track_location = f'{track_location_name}.{new_codec_data.container.name}'
                
                stream: ffmpeg = ffmpeg.input(track_location, hide_banner=None, y=None)
                # capture_stderr is required for the error output to be captured
                try:
                    # capture_stderr is required for the error output to be captured
                    stream.output(
                        temp_track_location,
                        acodec=new_codec.name.lower(),
                        **conv_flags,
                        loglevel='error'
                    ).run(capture_stdout=True, capture_stderr=True)
                except Error as e:
                    error_msg = e.stderr.decode('utf-8')
                    # get the error message from ffmpeg and search foe the non-experimental encoder
                    encoder = re.search(r"(?<=non experimental encoder ')[^']+", error_msg)
                    if encoder:
                        self.print(f'Encoder {new_codec.name.lower()} is experimental, trying {encoder.group(0)}')
                        # try to use the non-experimental encoder
                        stream.output(
                            temp_track_location,
                            acodec=encoder.group(0),
                            **conv_flags,
                            loglevel='error'
                        ).run()
                    else:
                        # raise any other occurring error
                        raise Exception(f'ffmpeg error converting to {new_codec.name.lower()}:\n{error_msg}')

                # remove file if it requires an overwrite, maybe os.replace would work too?
                if track_location == new_track_location:
                    silentremove(track_location)
                    # just needed so it won't get deleted
                    track_location = temp_track_location

                # move temp_file to new_track_location and delete temp file
                shutil.move(temp_track_location, new_track_location)
                silentremove(temp_track_location)

                if self.global_settings['advanced']['conversion_keep_original']:
                    old_track_location = track_location
                    old_container = container
                else:
                    silentremove(track_location)

                container = new_codec_data.container    
                track_location = new_track_location

        # Add the playlist track to the m3u playlist
        if m3u_playlist:
            self._add_track_m3u_playlist(m3u_playlist, track_info, track_location)

        # Finally tag file
        self.print('Tagging file')
        try:
            tag_file(track_location, cover_temp_location if self.global_settings['covers']['embed_cover'] else None,
                     track_info, credits_list, embedded_lyrics, container)
            if old_track_location:
                tag_file(old_track_location, cover_temp_location if self.global_settings['covers']['embed_cover'] else None,
                         track_info, credits_list, embedded_lyrics, old_container)
        except TagSavingFailure:
            self.print('Tagging failed, tags saved to text file')
        if delete_cover:
            silentremove(cover_temp_location)
        
        self.print(f'=== Track {track_id} downloaded ===', drop_level=1)
        return True

    def _get_artwork_settings(self, module_name = None, is_external = False):
        if not module_name:
            module_name = self.service_name
        return {
            'should_resize': ModuleFlags.needs_cover_resize in self.module_settings[module_name].flags,
            'resolution': self.global_settings['covers']['external_resolution'] if is_external else self.global_settings['covers']['main_resolution'],
            'compression': self.global_settings['covers']['external_compression'] if is_external else self.global_settings['covers']['main_compression'],
            'format': self.global_settings['covers']['external_format'] if is_external else 'jpg'
        }
