import discord
from discord.channel import TextChannel
from discord.member import Member, VoiceState
from discord.message import Message
from discord.player import FFmpegPCMAudio
from discord.voice_client import VoiceClient
from yt_dlp.extractor import myspace
from yt_dl import *
from bot import MusicBot, Song
import logging
import asyncio
import re

logging.basicConfig(handlers=[\
                        logging.FileHandler(filename='bot-log.txt', encoding='utf-8', mode='w'),\
                        logging.StreamHandler()],
                    format='%(asctime)s, %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)

#
# Playlist Feature
# You will be able to store multiple songs in a playlist. Then you can
# $p play <playlist_name> to play the playlist
#
# Playlists can be created one song at a time:
# $list add <playlist_name> <song_name>
# To aid the parsing, the playlist name cannot have spaces in it
# If there was no playlist with that name, it will be created
#
# You can also create a playlist by adding all songs from a queue:
# $queue dump <playlist_name>
# This will add all songs currently in the queue to the playlist
#

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
music = MusicBot()
current_vc: Union[VoiceClient, None] = None
current_vc_song: Union[Song, None] = None

# Advances the queue and resyncs with the voice call
def play_next_song(error):
    # If there was an error we may as well replay
    # the song by trying to resync the voice call
    if error is not None:
        logging.warning("[play_next_song] function called with error:", error) 

        client.loop.create_task(sync_vc_status(reconnect_to_vc = True))

        return

    music.next_song()
    logging.debug("[play_next_song] advanced to next song") 

    client.loop.create_task(sync_vc_status())

    logging.debug("[play_next_song] synced vc status") 

# Does a complex series of checks to try to make sure
# that the song that is currently at the front of the queue
# is playing in the voice call of the user who requested it.
#
# Will go as far as to join another voice call or leave all voice
# calls to keep everything in sync
# 
# Return codes:
# 0 - Sync was successful
# 1 - Not successful, only way to recover is to skip to the next song
# 2 - Not successful, may be worth retrying the sync before skipping
#
# I acknowledge that this is a bit of a mess, but it works (mostly)
async def sync_vc_status(reconnect_to_vc = False, attempt = 0):
    logging.debug("[sync_vc_status] syncing voice status")
    global current_vc
    global current_vc_song
    global music

    if not music.is_playing:
        logging.debug("[sync_vc_status] we should not be playing music")
        # Make sure we are not playing anything in voice
        if current_vc is not None:
            logging.debug("[sync_vc_status] we are in a voice call but should not be playing")
            # If we are not connected zero out the variables and return
            if not current_vc.is_connected():
                logging.debug("[sync_vc_status] voice call is not really connected, zeroing out variables")
                current_vc = None
                current_vc_song = None
                return

            # Stop any currently playing audio
            logging.debug("[sync_vc_status] voice call is still connected")
            if current_vc.is_playing() or current_vc.is_paused():
                logging.debug("[sync_vc_status] pausing currently playing audio")
                current_vc.stop()

            # Disconnect from the voice call
            logging.debug("[sync_vc_status] disconnecting from voice call...")
            await current_vc.disconnect()

            logging.debug("[sync_vc_status] disconnected. zeroing out variables...")
            # Zero out the variables
            current_vc = None
            current_vc_song = None
            return
        else:
            logging.debug("[sync_vc_status] good, we are not connected to a call")
            # If we are not in a call then we are not playing anything,
            # therefore we must be synced so we return
            return
    else:
        logging.debug("[sync_vc_status] we should be playing music")
        # This should not be none if music.is_playing is True
        assert(music.current_song is not None)

        # Make sure that the user who asked us to play is still in a channel
        # If they are not, we just return because there is not a way to play
        # the song it wants us to.
        try:
            assert(music.current_song.user.voice is not None)
            assert(music.current_song.user.voice.channel is not None)
        except AssertionError:
            logging.debug("[sync_vc_status] music.current_song was missing correct user details, exiting with a status of 1")
            return 1

        # Force reconnect to voice call if the flag is set
        if reconnect_to_vc and current_vc is not None:
            logging.debug("[sync_vc_status] disconnecting from vc due to flag")
            await current_vc.disconnect()
            current_vc = None
            current_vc_song = None

        # Make sure we are playing the right thing in voice
        if current_vc is None:
            logging.debug("[sync_vc_status] connecting to the right channel")
            # We need to connect to the right voice channel
            current_vc = await music.current_song.user.voice.channel.connect()
        else:
            # Check if we need to switch channels to be in the right voice call
            # Switch if necessary
            if current_vc.channel.name != music.current_song.user.voice.channel.name:
                logging.debug(f"[sync_vc_status] switching channels from {current_vc.channel.name} to {music.current_song.user.voice.channel.name}")
                await current_vc.disconnect()

                current_vc = await music.current_song.user.voice.channel.connect()

        # We are now in the right voice channel, play the song
        try:
            logging.debug(f"[sync_vc_status] attempting to play song in the right channel")
            # we may not be able to have play_next_song be a coroutine
            if (current_vc.is_playing() and current_vc_song != music.current_song) or music.skip_flag:
                logging.debug(f"[sync_vc_status] stopped current song to play other one")
                music.skip_flag = False
                current_vc.stop()
                # Once we call the stop function the after function will be called,
                # it will handle everything

                return

            # if this is true then we are already playing the right song and
            # therefore do not need to do anything to sync
            if current_vc.is_playing() and current_vc_song == music.current_song:
                logging.debug(f"[sync_vc_status] we are already playing the right song")
                return

            logging.debug(f"[sync_vc_status] playing the correct song...")
            current_vc.play(FFmpegPCMAudio(music.current_song.path), after=play_next_song)
            current_vc_song = music.current_song
        except Exception as e:
            if attempt == 0:
                logging.warning(f"[sync_vc_status] had error while syncing state: {e}, trying again with fresh call vars.")
            else:
                logging.warning(f"[sync_vc_status] had error while syncing state: {e}, returning 2 due to too many attempts.")
                pass

            await current_vc.disconnect()
            current_vc = None
            current_vc_song = None

            if attempt == 0:
                return await sync_vc_status(attempt=attempt+1)

            return 2

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

#
# Checks if any message received by the bot is a command of some sort
# Currently, all commands are received this way, the official discort
# slash command system is not used
#
@client.event
async def on_message(message: Message):
    global client
    global dc_bot
    global current_vc

    try:
        assert(isinstance(message.channel, TextChannel))
    except AssertionError:
        logging.warning("[on_message] skipping analysis due to invalid channel")
        return

    if message.channel.name != "harlough":
        return

    if message.author == client.user:
        return

    if message.content.startswith('$help'):
        logging.debug("[on_message] Printing help message")
        await message.channel.send(f'.\nCommand help:\nThe Basics\
                                    \n$[p]lay [song title or url]\
                                    \n    -l Only search locally for the song\
                                    \n    -r Only search remotely for the song\
                                    \n    -n Put this at the front of the queue\
                                    \n$[s]top - pause the current song\
                                    \n$[r]esume - unpause the current song\
                                    \n$[c]lear - clears the queue\
                                    \n$[n]ext - skip the current song in the queue\
                                    \n$[q]ueue - shows the current queue\
                                    \n$[h]elp - shows this message\
                                    \n\nOthers\
                                    \n$[d]elete [s]ong [queue index] - deletes the song at the given index from the queue\
                                    \n$[sw]ap [queue index] [new index] - moves the song at the given index to the new index\
                                    \n$[q]ueue [d]ump [playlist_name (no spaces)] - dumps the current queue to a playlist with the provided name\
                                    \n$[q]ueue [l]oad [playlist_name (no spaces)] - loads the playlist with the provided name into the queue\
                                    \n\nMost commands can be abbreviated to one letter. Flags should be appended to the end of the command. You must include a space before your flags. For example:\
                                    \n$play Avicii - The Nights -l-f')

    if message.content.startswith('$p ') or message.content.startswith('$play '):
        msg_content = message.content
        VALID_FLAGS = ["-n", "-l", "-r"]

        try:
            cmd_flags = message.content.split(" ")[-1].lower()

            # Don't search for the flags if they are present
            for flag in VALID_FLAGS:
                if flag in cmd_flags:
                    msg_content = " ".join(message.content.split(" ")[0:-1])
                    break
        except:
            cmd_flags = ""

        logging.debug(f"[on_message] trying to play song with flags: '{cmd_flags}'")

        try:
            author = message.author

            try:
                assert(isinstance(author, Member)) 
            except AssertionError:
                logging.debug("[on_message] did not have access to channel")
                await message.channel.send(f"I can't join that channel!")
                return

            if author.voice is None:
                logging.debug("[on_message] user was not in a channel")
                await message.channel.send(f"Join a voice channel first! 😴")
                return

            # Don't search for the command string
            term = " ".join(msg_content.split(" ")[1:])

            await message.add_reaction('⌛')

            add_song_next = "-n" in cmd_flags

            if "-l" in cmd_flags:
                status = music.add_song_locally(term, user = author, add_next=add_song_next)
            elif "-r" in cmd_flags:
                status = music.add_song_remotely(term, user = author, add_next=add_song_next)
            else:
                status = music.add_song_from_query(term, user = author, add_next=add_song_next)

            if status == 0:
                assert(music.latest_song is not None)

                logging.debug("[on_message] added song to queue")
                await message.channel.send(f"Added {music.latest_song.title} to the queue! ✅")
            else:
                logging.warning("[on_message] yt_dl module failed to find song")
                await message.channel.send(f"Sorry, I'm a little confused... 😕")
                return

            await sync_vc_status()

            try:
                assert(client.user != None)
                assert(message.guild != None)
            except AssertionError:
                logging.debug("[on_message] error, cannot play song outside of a guild")
                return

            myself = message.guild.get_member(client.user.id)

            assert(myself != None)

            await message.remove_reaction('⌛', myself)
            #await message.add_reaction('🎵')
        except Exception as e:
            print("Caught exception while trying to play a song: ", e)
            logging.warning(f"[on_message] encountered exception while trying to play song: {e}")
            await message.channel.send(f"Sorry, I'm a little confused... 😕")

    if message.content.startswith('$s') or message.content.startswith('$stop'):
        logging.debug("[on_message] stopping song")
        if current_vc == None:
            logging.debug("[on_message] no song was playing")
            await message.channel.send(f"I'm not playing anything right now!")
            return

        if current_vc.is_playing():
            current_vc.pause()

        emoji = '⏸️'
        await message.add_reaction(emoji)

        logging.debug("[on_message] song stopped")

    if message.content.startswith('$r') or message.content.startswith('$resume'):
        logging.debug("[on_message] resuming song")
        if current_vc == None:
            logging.debug("[on_message] there was no song to resume")
            await message.channel.send(f"I'm not playing anything right now!")
            return

        if current_vc.is_paused():
            current_vc.resume()

        emoji = '▶️'
        await message.add_reaction(emoji)
        logging.debug("[on_message] song resumed")

    if message.content.startswith('$c') or message.content.startswith('$clear'):
        logging.debug("[on_message] clearing queue")
        music.clear_queue()
        await sync_vc_status()

        emoji = '🛑'
        await message.add_reaction(emoji)

    if message.content.startswith('$n') or message.content.startswith('$next'):
        logging.debug("[on_message] skipping to next song")
        refresh_state = music.current_song is not None
        #music.next_song()
        music.skip_flag = True

        if refresh_state:
            await sync_vc_status()

        emoji = '⏭️'
        await message.add_reaction(emoji)

    if message.content == '$q' or message.content == '$queue':
        logging.debug("[on_message] showing queue to user")
        await message.channel.send(f".\n{music.fmt_queue()}")

    if message.content.startswith('$ds ') or message.content.startswith('$delete song '):
        logging.debug("[on_message] deleting song from queue")
        try:
            index = int(message.content.split(" ")[-1])
            status = music.remove_song(index-1)

            assert(status == 0)
    
            await sync_vc_status()
            await message.add_reaction('🗑️')
            await message.channel.send(f".\n{music.fmt_queue()}")
        except:
            await message.channel.send(f"Invalid queue index, refer to $queue for valid indices.")

    if message.content.startswith('$sw ') or message.content.startswith('$swap '):
        logging.debug("[on_message] swapping songs in queue")
        try:
            indices = message.content.split(" ")[-2:]
            status = music.swap_songs(int(indices[0]), int(indices[1]))

            assert(status == 0)

            await sync_vc_status()
            await message.add_reaction('🔄')
        except:
            await message.channel.send(f"Invalid queue indices, refer to $queue for valid indices.")

    if message.content.startswith('$qd ') or message.content.startswith('$queue dump '):
        logging.debug("[on_message] dumping queue to file")
        try:
            playlist_name = message.content.split(" ")[-1]
            status = music.dump_queue_to_playlist_file(playlist_name)

            if status == 0:
                logging.debug("[on_message] dumped queue")
                await message.add_reaction('📥')
            elif status == 1:
                await message.add_reaction('❌')
                logging.debug("[on_message] could not dump, name already exists")
                await message.channel.send(f"Error, playlist name already exists.")
            else:
                await message.add_reaction('❌')
                logging.debug("[on_message] could not dump, queue empty")
                await message.channel.send(f"There are no songs in the queue!")
        except Exception as e:
            logging.debug("[on_message] could not dump, exception: ", e)
            await message.channel.send(f"Error, could not dump queue to playlist.")

    if message.content.startswith('$ql ') or message.content.startswith('$queue load '):
        logging.debug("[on_message] loading queue from file")
        try:
            playlist_name = message.content.split(" ")[-1]
            author = message.author

            try:
                assert(isinstance(author, Member)) 
            except AssertionError:
                logging.debug("[on_message] did not have access to channel")
                await message.channel.send(f"I can't join that channel!")
                return

            if author.voice is None:
                logging.debug("[on_message] user was not in a channel")
                await message.channel.send(f"Join a voice channel first! 😴")
                return

            status = music.add_songs_from_playlist(playlist_name, author)

            if status == 0:
                await sync_vc_status()
                await message.add_reaction('📤')
            elif status == 1:
                await message.add_reaction('❌')
                await message.channel.send(f"Error, playlist name does not exist.")
            else:
                await message.add_reaction('❌')
                await message.channel.send(f"Error, could not load playlist.")
        except:
            await message.channel.send(f"Error, could not load playlist.")

@client.event
async def on_voice_state_update(member: Member, before: VoiceState, after: VoiceState):
    assert(client.user is not None)

    if (before.channel is None or (before.channel.name != "Lobby" and before.channel.name != "Gaming")) and after.channel is not None \
            and member.id != client.user.id and after.channel.name != "afk"\
            and after.channel.name != "kinda-fucked" and after.channel.name != "robo-bitches":
        channels = list(client.get_all_channels())

        for channel in channels:
            if channel.name == "on-announcement" and \
                isinstance(channel, TextChannel) and \
                channel.guild.name == after.channel.guild.name:

                await channel.send(f"@here {member.display_name} has joined the {after.channel.name} voice channel!")

with open(".dc-token", "r") as f:
    token = f.readline()

client.run(token)

