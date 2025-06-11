import base64
import logging
from dataclasses import asdict
import json
import os

from PIL import Image
from mutagen.easyid3 import EasyID3
from mutagen.easymp4 import EasyMP4
from mutagen.flac import FLAC, Picture
from mutagen.id3 import PictureType, APIC, USLT, TDAT, COMM, TPUB
from mutagen.mp3 import EasyMP3
from mutagen.mp4 import MP4Cover
from mutagen.mp4 import MP4Tags
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from utils.exceptions import *
from utils.models import ContainerEnum, TrackInfo

# Needed for Windows tagging support
MP4Tags._padding = 0

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'settings.json')

def get_tagging_settings():
    with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
        settings = json.load(f)
    return settings['global'].get('tagging', {})

def tag_file(file_path: str, image_path: str, track_info: TrackInfo, credits_list: list, embedded_lyrics: str, container: ContainerEnum):
    tagging_settings = get_tagging_settings()
    save_tags = set(tagging_settings.get('save_tags', []))
    overwrite_tags_only = tagging_settings.get('overwrite_tags_only', False)

    if container == ContainerEnum.flac:
        tagger = FLAC(file_path)
    elif container == ContainerEnum.opus:
        tagger = OggOpus(file_path)
    elif container == ContainerEnum.ogg:
        tagger = OggVorbis(file_path)
    elif container == ContainerEnum.mp3:
        tagger = EasyMP3(file_path)

        if tagger.tags is None:
            tagger.tags = EasyID3()  # Add EasyID3 tags if none are present

        # Register encoded, rating, barcode, compatible_brands, major_brand and minor_version
        tagger.tags.RegisterTextKey('encoded', 'TSSE')
        tagger.tags.RegisterTXXXKey('compatible_brands', 'compatible_brands')
        tagger.tags.RegisterTXXXKey('major_brand', 'major_brand')
        tagger.tags.RegisterTXXXKey('minor_version', 'minor_version')
        tagger.tags.RegisterTXXXKey('Rating', 'Rating')
        tagger.tags.RegisterTXXXKey('upc', 'BARCODE')

        tagger.tags.pop('encoded', None)
    elif container == ContainerEnum.m4a:
        tagger = EasyMP4(file_path)

        # Register ISRC, lyrics, cover and explicit tags
        tagger.RegisterTextKey('isrc', '----:com.apple.itunes:ISRC')
        tagger.RegisterTextKey('upc', '----:com.apple.itunes:UPC')
        tagger.RegisterTextKey('explicit', 'rtng') if track_info.explicit is not None else None
        tagger.RegisterTextKey('covr', 'covr')
        tagger.RegisterTextKey('lyrics', '\xa9lyr') if embedded_lyrics else None
    else:
        raise Exception('Unknown container for tagging')

    # Remove all useless MPEG-DASH ffmpeg tags
    if tagger.tags is not None:
        if 'major_brand' in tagger.tags:
            del tagger.tags['major_brand']
        if 'minor_version' in tagger.tags:
            del tagger.tags['minor_version']
        if 'compatible_brands' in tagger.tags:
            del tagger.tags['compatible_brands']
        if 'encoder' in tagger.tags:
            del tagger.tags['encoder']

    # Helper to check if a tag should be saved
    def should_save(tag):
        return tag in save_tags or not save_tags  # If save_tags is empty, save all

    # Set tags only if they are in save_tags
    if should_save('title'): tagger['title'] = track_info.name
    if should_save('album') and track_info.album: tagger['album'] = track_info.album
    if should_save('album_artist') and track_info.tags.album_artist: tagger['albumartist'] = track_info.tags.album_artist
    if should_save('artist'): tagger['artist'] = track_info.artists

    if container == ContainerEnum.m4a or container == ContainerEnum.mp3:
        if should_save('track_number') and track_info.tags.track_number and track_info.tags.total_tracks:
            tagger['tracknumber'] = str(track_info.tags.track_number) + '/' + str(track_info.tags.total_tracks)
        elif should_save('track_number') and track_info.tags.track_number:
            tagger['tracknumber'] = str(track_info.tags.track_number)
        if should_save('disc_number') and track_info.tags.disc_number and track_info.tags.total_discs:
            tagger['discnumber'] = str(track_info.tags.disc_number) + '/' + str(track_info.tags.total_discs)
        elif should_save('disc_number') and track_info.tags.disc_number:
            tagger['discnumber'] = str(track_info.tags.disc_number)
    else:
        if should_save('track_number') and track_info.tags.track_number: tagger['tracknumber'] = str(track_info.tags.track_number)
        if should_save('disc_number') and track_info.tags.disc_number: tagger['discnumber'] = str(track_info.tags.disc_number)
        if should_save('total_tracks') and track_info.tags.total_tracks: tagger['totaltracks'] = str(track_info.tags.total_tracks)
        if should_save('total_discs') and track_info.tags.total_discs: tagger['totaldiscs'] = str(track_info.tags.total_discs)

    if should_save('date') and track_info.tags.release_date:
        if container == ContainerEnum.mp3:
            release_dd_mm = f'{track_info.tags.release_date[8:10]}{track_info.tags.release_date[5:7]}'
            tagger.tags._EasyID3__id3._DictProxy__dict['TDAT'] = TDAT(encoding=3, text=release_dd_mm)
            tagger['date'] = str(track_info.release_year)
        else:
            tagger['date'] = track_info.tags.release_date
    elif should_save('year'):
        tagger['date'] = str(track_info.release_year)

    if should_save('copyright') and track_info.tags.copyright: tagger['copyright'] = track_info.tags.copyright
    if should_save('explicit') and track_info.explicit is not None:
        if container == ContainerEnum.m4a:
            tagger['explicit'] = b'\x01' if track_info.explicit else b'\x02'
        elif container == ContainerEnum.mp3:
            tagger['Rating'] = 'Explicit' if track_info.explicit else 'Clean'
        else:
            tagger['Rating'] = 'Explicit' if track_info.explicit else 'Clean'
    if should_save('genre') and track_info.tags.genres: tagger['genre'] = track_info.tags.genres
    if should_save('isrc') and track_info.tags.isrc: tagger['isrc'] = track_info.tags.isrc.encode() if container == ContainerEnum.m4a else track_info.tags.isrc
    if should_save('upc') and track_info.tags.upc: tagger['UPC'] = track_info.tags.upc.encode() if container == ContainerEnum.m4a else track_info.tags.upc
    if should_save('label') and track_info.tags.label:
        if container in {ContainerEnum.flac, ContainerEnum.ogg}:
            tagger['Label'] = track_info.tags.label
        elif container == ContainerEnum.mp3:
            tagger.tags._EasyID3__id3._DictProxy__dict['TPUB'] = TPUB(
                encoding=3,
                text=track_info.tags.label
            )
        elif container == ContainerEnum.m4a:
            tagger.RegisterTextKey('label', '\xa9pub')
            tagger['label'] = track_info.tags.label
    if should_save('description') and track_info.tags.description and container == ContainerEnum.m4a:
        tagger.RegisterTextKey('desc', 'description')
        tagger['description'] = track_info.tags.description
    if should_save('comment') and track_info.tags.comment:
        if container == ContainerEnum.m4a:
            tagger.RegisterTextKey('comment', '\xa9cmt')
            tagger['comment'] = track_info.tags.comment
        elif container == ContainerEnum.mp3:
            tagger.tags._EasyID3__id3._DictProxy__dict['COMM'] = COMM(
                encoding=3,
                lang=u'eng',
                desc=u'',
                text=track_info.tags.description
            )
    # Extra tags
    if container in {ContainerEnum.flac, ContainerEnum.ogg}:
        for key, value in track_info.tags.extra_tags.items():
            if should_save(key):
                tagger[key] = value
    elif container is ContainerEnum.m4a:
        for key, value in track_info.tags.extra_tags.items():
            if should_save(key):
                tagger.RegisterTextKey(key, '----:com.apple.itunes:' + key)
                tagger[key] = str(value).encode()
    # Credits
    if credits_list:
        for credit in credits_list:
            if should_save(credit.type):
                if container == ContainerEnum.m4a:
                    tagger.RegisterTextKey(credit.type, '----:com.apple.itunes:' + credit.type)
                    tagger[credit.type] = [con.encode() for con in credit.names]
                elif container == ContainerEnum.mp3:
                    tagger.tags.RegisterTXXXKey(credit.type.upper(), credit.type)
                    tagger[credit.type] = credit.names
                else:
                    try:
                        tagger.tags[credit.type] = credit.names
                    except:
                        pass
    # Lyrics
    if should_save('lyrics') and embedded_lyrics:
        if container == ContainerEnum.mp3:
            tagger.tags._EasyID3__id3._DictProxy__dict['USLT'] = USLT(
                encoding=3,
                lang=u'eng',
                text=embedded_lyrics
            )
        else:
            tagger['lyrics'] = embedded_lyrics
    # Replay gain/peak
    if should_save('replay_gain') and track_info.tags.replay_gain and should_save('replay_peak') and track_info.tags.replay_peak and container != ContainerEnum.m4a:
        tagger['REPLAYGAIN_TRACK_GAIN'] = str(track_info.tags.replay_gain)
        tagger['REPLAYGAIN_TRACK_PEAK'] = str(track_info.tags.replay_peak)
    # Cover
    if not overwrite_tags_only and image_path:
        with open(image_path, 'rb') as c:
            data = c.read()
        picture = Picture()
        picture.data = data
        if len(picture.data) < picture._MAX_SIZE:
            if container == ContainerEnum.flac:
                picture.type = PictureType.COVER_FRONT
                picture.mime = u'image/jpeg'
                tagger.add_picture(picture)
            elif container == ContainerEnum.m4a:
                tagger['covr'] = [MP4Cover(data, imageformat=MP4Cover.FORMAT_JPEG)]
            elif container == ContainerEnum.mp3:
                tagger.tags._EasyID3__id3._DictProxy__dict['APIC'] = APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,
                    desc='Cover',
                    data=data
                )
            elif container in {ContainerEnum.ogg, ContainerEnum.opus}:
                im = Image.open(image_path)
                width, height = im.size
                picture.type = 17
                picture.desc = u'Cover Art'
                picture.mime = u'image/jpeg'
                picture.width = width
                picture.height = height
                picture.depth = 24
                encoded_data = base64.b64encode(picture.write())
                tagger['metadata_block_picture'] = [encoded_data.decode('ascii')]
        else:
            print(f'\tCover file size is too large, only {(picture._MAX_SIZE / 1024 ** 2):.2f}MB are allowed. Track will not have cover saved.')
    try:
        tagger.save(file_path, v1=2, v2_version=3, v23_sep=None) if container == ContainerEnum.mp3 else tagger.save()
    except:
        logging.debug('Tagging failed.')
        tag_text = '\n'.join((f'{k}: {v}' for k, v in asdict(track_info.tags).items() if v and k != 'credits' and k != 'lyrics'))
        tag_text += '\n\ncredits:\n    ' + '\n    '.join(f'{credit.type}: {", ".join(credit.names)}' for credit in credits_list if credit.names) if credits_list else ''
        tag_text += '\n\nlyrics:\n    ' + '\n    '.join(embedded_lyrics.split('\n')) if embedded_lyrics else ''
        open(file_path.rsplit('.', 1)[0] + '_tags.txt', 'w', encoding='utf-8').write(tag_text)
        raise TagSavingFailure
