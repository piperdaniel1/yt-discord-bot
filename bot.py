# This example requires the 'message_content' intent.

import discord
from discord.member import Member
from yt_dl import *
from typing import List, Union
import logging
logging.basicConfig(filename='bot-log.txt',
                    format='%(asctime)s, %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)

# Must implement a global queue class
# Should store paths to mp3 so that they
# can be immediately played
#
# Need to have a listener to change queue
# when the bot finishes a song.

class Song:
    def __init__(self, path: str, title: str, user: Member):
        assert(isinstance(user, Member))

        self.path: str = path
        self.title: str = title
        self.user: Member = user

    def __eq__(self, other) -> bool:
        try:
            return self.path == other.path and self.user.name == other.user.name
        except AttributeError:
            return False

# Keeps track of songs
class MusicBot:
    def __init__(self):
        self.current_song: Union[Song, None] = None
        self.backlog: List[Song] = []
        self.is_playing: bool = False
        self.latest_song: Union[Song, None] = None

    def fmt_queue(self):
        queue_str = ""

        if not self.is_playing:
            queue_str += "The queue is currently empty."
        else:
            assert(self.current_song is not None)

            queue_str += "Current Queue:\n"
            queue_str += "🎶 " + self.current_song.title + "\n"
            
            for song in self.backlog:
                queue_str += "▫️ " + song.title + "\n"

        return queue_str

    def clear_queue(self):
        self.current_channel = None;
        self.backlog = []
        self.is_playing = False
        self.latest_song = None

    def push_song_back(self, song: Song):
        if self.current_song is None:
            self.current_song = song
            self.is_playing = True
        else:
            self.backlog.append(song)

        self.latest_song = song

    def push_song_front(self, song: Song):
        if self.current_song is None:
            self.current_song = song
            self.is_playing = True
        else:
            self.backlog.insert(0, song)

        self.latest_song = song

    # Returns the number of songs that are left to play (including the current one)
    def next_song(self):
        if len(self.backlog) != 0:
            self.current_song = self.backlog.pop(0)
            return 1 + len(self.backlog)
        else:
            self.current_song = None
            self.is_playing = False
            self.current_channel = None
            return 0

    def next_song_exists(self):
        return len(self.backlog) > 0

    # Always gets the best match locally no matter how little it actually matches
    def add_song_locally(self, query, user: Member, add_next = None):
        path, title = download_from_search(query, force=False, threshold=0)

        if path is None or title is None:
            return 1
        
        new_song = Song(path, title, user)

        if add_next:
            self.push_song_front(new_song)
        else:
            self.push_song_back(new_song)

        return 0
    
    # Checks locally first, then gets from yt_dlp if needed
    # Returns 0 everything was successful (song is now on queue)
    # Returns 1 if there was some kind of error that prevented the song
    # from entering the queue
    def add_song_from_query(self, query, user: Member, add_next=False):
        path, title = download_from_search(query, force=False, threshold=60)

        if path is None or title is None:
            return 1
        
        new_song = Song(path, title, user)

        if add_next:
            self.push_song_front(new_song)
        else:
            self.push_song_back(new_song)

        return 0
    
    # Finds song on YouTube with yt_dlp
    def add_song_remotely(self, query, user: Member, add_next = False):
        path, title = download_from_search(query, force=True)

        if path is None or title is None:
            return 1
        
        new_song = Song(path, title, user)

        if add_next:
            self.push_song_front(new_song)
        else:
            self.push_song_back(new_song)

        return 0
