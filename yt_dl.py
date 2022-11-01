from typing import Tuple, Union
from yt_dlp import DownloadError, YoutubeDL
from fuzzywuzzy import fuzz
import re
import os
import logging
logging.basicConfig(filename='bot-log.txt',
                    format='%(asctime)s, %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)
#
# Idea, on query from discord bot:
# Check file directory for a similar song name
# If there is, just return that.
# Otherwise, look for a new one.
# Maybe have a flag to always look for a new one.
#



# Interfaces with .mediacache format
class MediaCache:
    pass

DEBUG_PROGRAM = True
MEDIA_PATH = "~/.bot-media/"

downloader = None 

def dprint(str, type='other', priority='low'):
    if DEBUG_PROGRAM:
        print(f"[{type}]", str)

def simplify_song_title(title) -> str:
    # Remove anything wrapped in ()
    title = re.sub(r"\([^\)]+\)", '', title)

    # Remove anything wrapped in []
    title = re.sub(r"\[[^\]]+\]", '', title)

    # Remove featured artists
    title = re.sub(r"ft.[^\.\(\)\[\]]*\.*", '', title)
    title = re.sub(r"Ft.[^\.\(\)\[\]]*\.*", '', title)
    title = re.sub(r"FT.[^\.\(\)\[\]]*\.*", '', title)
    title = re.sub(r"feat.[^\.\(\)\[\]]*\.*", '', title)

    # Remove three letter file extension
    title = re.sub(r"\....$", '', title)

    # Remove leading whitespace
    title = re.sub(r"\s+$", '', title)

    # Remove trailing whitespace
    title = re.sub(r"^\s+", '', title)

    return title

# Look for a .botconfig in the current working directory
# If it exists, read in the contents
def read_config():
    try:
        with open(".botconfig") as f:
            lines = f.readlines()

        for line in lines:
            split_line = line.split("=")

            if len(split_line) != 2:
                continue

            if split_line[0] == "mediapath":
                global MEDIA_PATH
                MEDIA_PATH = split_line[1].replace("\n", "")
                dprint(f"Overrode mediapath to '{MEDIA_PATH}'", type='config')
    except FileNotFoundError:
        pass

    global downloader
    downloader = YoutubeDL({'format':'bestaudio',
                            'noplaylist': True,
                            'outtmpl': f'{MEDIA_PATH}/%(title)s.%(ext)s',
                            'postprocessors': [{
                                'key': 'FFmpegExtractAudio',
                                'preferredcodec': 'mp3'}],
                            })

def init_media_dir():
    # Create a new directory at MEDIA_PATH
    dprint(f"mediapath does not exist, initializing new directory", type='mediapath')
    os.makedirs(MEDIA_PATH)

    # Create new .mediacache
    with open(f"{MEDIA_PATH}/.mediacache", "w") as f:
        pass

# Save new media
# YoutubeDL automatically figures out if it has already downloaded something
# and skips it
def save_media(path, path_type='yt'):
    assert(downloader != None)
    try:
        if path_type == 'yt':
            info = downloader.extract_info(path)
            if info != None:
                dprint(f"Retrieved {info['title']} from YouTube", type='mediapath')
        else:
            return 1
    except DownloadError:
        dprint(f"Error, unable to find a video at {path} on YouTube.",
               type='mediapath', priority='high')
        return 1
    return 0


def get_search_url(term, type='yt'):
    assert(downloader != None)
    try:

        if type == 'yt':
            if re.match(r"[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)", term):
                info = downloader.extract_info(f"{term}", download=False)
            else:
                info = downloader.extract_info(f"ytsearch:{term}", download=False)

            if info != None:
                video = info['entries'][0]

                return video['webpage_url']
            else:
                return 1
    except:
        return 1

def find_local_file(term, threshold):
    media = os.listdir(MEDIA_PATH)

    media = [entry for entry in media if os.path.isfile(MEDIA_PATH + "/" + entry) and\
            entry != ".mediacache"]

    best_title = ""
    best_score = 999999999

    # Match using subset
    # Favor song titles that are shorter to break ties
    for file_title in media:
        original_title = file_title
        file_title = file_title.split(".")[0]
        file_title = file_title.lower()
        term = term.lower()
        file_title.strip("\n.!?,;:()[]{}-& ")
        term.strip("\n.!?,;:()[]{}-& ")

        if term in file_title:
            if len(file_title) < best_score:
                best_score = len(file_title)
                best_title = original_title

    if best_title != "":
        return best_title, best_score, "strict subset"

    # Match using Fuzzy Finder
    # This approach is a bit limited, sometimes it can be great sometimes
    # it really does a poor job. Therefore, we leave it for a last resort.
    best_title = ""
    best_score = 0

    for file_title in media:
        original_title = file_title
        file_title = file_title.split(".")[0]
        file_title = file_title.lower()
        term = term.lower()
        file_title.strip("\n.!?,;:()[]{}-& ")
        term.strip("\n.!?,;:()[]{}-& ")

        if fuzz.ratio(term, file_title) > max(threshold, best_score):
            best_title = original_title
            best_score = fuzz.ratio(term, file_title)

    return best_title, best_score, "fuzzy find"

# Returns a tuple of path, title to a song
# Downloads from YouTube if neccessary, always
# downloads form YouTube if force=True
# Always uses local file if threshold=0
def download_from_search(term, type='yt', force=False, threshold=60) -> \
        Union[Tuple[str, str], Tuple[None, None]]:
    logging.debug(f"[download_from_search] - Searching for {term}")

    if not force:
        logging.debug(f"[download_from_search] Searching local directory")

        best_title, best_score, method = find_local_file(term, threshold)

        if best_title != "":
            logging.debug(f"[download_from_search] Found suitable local song with score {best_score} using {method} method.")
            dprint("Returning local MP3 file", type='media')
            return MEDIA_PATH + "/" + best_title, best_title
        
        logging.debug(f"[download_from_search] No suitable local song found, searching remotely...")

    try:
        assert(downloader != None)
    except AssertionError:
        logging.warning(f"[download_from_search] Error, could not retrieve song because yt_dlp downloader was None.")
        return None, None

    try:
        if type == 'yt':
            if re.match(r"[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)", term):
                logging.debug(f"[download_from_search] Found URL, downloading specific video...")
                info = downloader.extract_info(f"{term}", download=True)
            else:
                info = downloader.extract_info(f"ytsearch:{term}", download=True)
            if info != None:
                print(info['entries'][0]['title'])
                logging.debug(f"[download_from_search] Found song on YouTube, returning path and title...")

                unproc_title = f"{info['entries'][0]['title']}.mp3"
                proc_title = simplify_song_title(unproc_title)

                # Makes sure we still have some characters
                if proc_title != "":
                    before_path = f'{MEDIA_PATH}/{unproc_title}'
                    after_path = f'{MEDIA_PATH}/{proc_title}'
                    os.rename(before_path, after_path)

                    return f"{MEDIA_PATH}/{proc_title}", \
                            proc_title
                else:
                    return f"{MEDIA_PATH}/{info['entries'][0]['title']}.mp3", \
                            info['entries'][0]['title']

        logging.debug(f"[download_from_search] No suitable song found")
        return None, None
    except Exception as e:
        logging.debug(f"[download_from_search] No suitable song found due to exception: {e}")
        raise e
        return None, None

read_config()

if not os.path.exists(MEDIA_PATH):
    init_media_dir()
