# This example requires the 'message_content' intent.

import discord
from discord.member import Member
from yt_dl import *
from typing import List, Union
import logging
logging.basicConfig(handlers=[\
                        logging.FileHandler(filename='bot-log.txt', encoding='utf-8', mode='w'),\
                        logging.StreamHandler()],
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

#
# Song class without the Member field
# This is great for playlists as they do not have a user
# associated with them. Each PrePlaySong is converted to a song
# when a user asks for it to be played.
#
class PrePlaySong:
    def __init__(self, path: str, title: str):
        self.path: str = path
        self.title: str = title

    def __eq__(self, other) -> bool:
        try:
            return self.path == other.path
        except AttributeError:
            return False

    def convert_to_song(self, user: Member) -> Song:
        return Song(self.path, self.title, user)

class Playlist:
    def __init__(self, name: str, songs: List[Union[Song, PrePlaySong]] = []):
        self.songs: List[Union[Song, PrePlaySong]] = songs
        self.playlist_name = name
        self.READY_TO_PLAY = False

    # Dump the playlist to a file
    # Returns 1 if file already exists, 0 if the dump was successful
    def dump_to_file(self, force = False):
        # Check if file already exists
        if os.path.exists(f"{MEDIA_PATH}/playlists/{self.playlist_name}.hpl") and not force:
            return 1

        # .hpl stands for Harlough PlayList
        with open(f"{MEDIA_PATH}/playlists/{self.playlist_name}.hpl", 'w') as f:
            # Write the playlist name to the top of the file
            f.write(self.playlist_name + '\n')

            # Write each song to the file while sanitizing the input
            for song in self.songs:
                f.write(song.title.replace('^', '') + "^" + song.path.replace('^', '') + '\n')

        return 0

    def import_from_file(self, playlist_name: str):
        with open(f"{MEDIA_PATH}/playlists/{playlist_name}.hpl", 'r') as f:
            # Read the playlist name
            self.name = f.readline().strip()

            # Read each song from the file
            for line in f:
                title, path = line.split('^')
                title = title.strip()
                path = path.strip()

                self.songs.append(PrePlaySong(path, title))

    # This must be run before the playlist is turned into a Queue
    def convert_songs(self, user: Member):
        new_arr: List[Song | PrePlaySong] = []
        for song in self.songs:
            if isinstance(song, PrePlaySong):
                new_arr.append(song.convert_to_song(user))
            else:
                new_arr.append(song)

        self.songs = new_arr
        self.READY_TO_PLAY = True

# Keeps track of songs
class MusicBot:
    def __init__(self):
        self.current_song: Union[Song, None] = None
        self.backlog: List[Song] = []
        self.is_playing: bool = False
        self.latest_song: Union[Song, None] = None
        self.skip_flag = False

    def dump_queue_to_playlist_file(self, playlist_name: str):
        try:
            assert(self.current_song is not None)
        except AssertionError:
            return 2

        song_list: List[Song | PrePlaySong] = [self.current_song]
        song_list.extend(self.backlog)

        conv_song_list: List[Song | PrePlaySong] = []
        for song in song_list:
            conv_song_list.append(PrePlaySong(song.path, song.title))

        song_list = conv_song_list
        playlist = Playlist(playlist_name, song_list)

        return playlist.dump_to_file()

    # Returns 1 if the playlist does not exist,
    # 0 if the playlist was successfully loaded
    def add_songs_from_playlist(self, playlist_name: str, user: Member):
        playlist = Playlist(playlist_name)

        try:
            with open(f"{MEDIA_PATH}/playlists/{playlist_name}.hpl", 'r') as f:
                # Read the playlist name
                playlist_name = f.readline().strip()

                # Read each song from the file
                for line in f:
                    title, path = line.split('^')
                    title = title.strip()
                    path = path.strip()
                    playlist.songs.append(PrePlaySong(path, title))
        except FileNotFoundError:
            return 1

        playlist.convert_songs(user)

        # Effectively guaranteed to be true
        assert(playlist.READY_TO_PLAY)

        for song in playlist.songs:
            # This should always pass if playlist.READY_TO_PLAY is true
            assert(isinstance(song, Song))
            self.push_song_back(song)

        return 0

    def remove_song(self, song_ind: int):
        if song_ind == 0:
            self.skip_flag = True
        else:
            try:
                self.backlog.pop(song_ind - 1)
            except IndexError:
                return 1

        return 0

    def swap_songs(self, song_ind_1: int, song_ind_2: int):
        if song_ind_1 == 0 or song_ind_2 == 0:
            return 1

        try:
            self.backlog[song_ind_1 - 1], self.backlog[song_ind_2 - 1] = \
                    self.backlog[song_ind_2 - 1], self.backlog[song_ind_1 - 1]
        except IndexError:
            return 1

        return 0

    def fmt_queue(self):
        queue_str = ""

        if not self.is_playing:
            queue_str += "The queue is currently empty."
        else:
            assert(self.current_song is not None)

            queue_str += "Current Queue:\n"
            queue_str += "1 🎶 " + self.current_song.title + "\n"
            
            for i, song in enumerate(self.backlog):
                queue_str += f"{i+2} ▫️ " + song.title + "\n"

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
