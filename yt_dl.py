from yt_dlp import DownloadError, YoutubeDL
import time
import asyncio
import os

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
            info = downloader.extract_info(f"ytsearch:{term}", download=False)

            if info != None:
                video = info['entries'][0]

                return video['webpage_url']
            else:
                return 1
    except:
        return 1

def download_from_search(term, type='yt'):
    assert(downloader != None)
    try:
        if type == 'yt':
            info = downloader.extract_info(f"ytsearch:{term}", download=True)
            if info != None:
                print(info['entries'][0]['title'])
                return f"{MEDIA_PATH}/{info['entries'][0]['title']}.mp3", \
                        info['entries'][0]['title']
            return 1
    except:
        return 1

read_config()

if not os.path.exists(MEDIA_PATH):
    init_media_dir()
