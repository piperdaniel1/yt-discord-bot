import discord
from discord.member import Member
from discord.message import Message
from discord.player import FFmpegPCMAudio
from discord.voice_client import VoiceClient
from yt_dl import *
from bot import MusicBot, Song
import logging
import asyncio

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

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
music = MusicBot()
current_vc: Union[VoiceClient, None] = None
current_vc_song: Union[Song, None] = None

'''
def play_next_song(error=None):
    global current_channel
    print("Current channel:", current_channel)

    if current_channel != None:
        print("Connection status:", current_channel.is_connected())

    if len(queue) > 1:
        queue.pop(0)

    if len(queue) > 0:
        next = queue[0]

        if current_channel != None:
            current_channel.play(discord.FFmpegPCMAudio(next), after=play_next_song)
'''

# Advances the queue and resyncs with the voice call
def play_next_song(error):
    # If there was an error we may as well replay
    # the song by trying to resync the voice call
    if error is not None:
        logging.warning("[play_next_song] function called with error:", error) 

        coroutine = sync_vc_status(reconnect_to_vc = True)
        new_loop = asyncio.new_event_loop()
        new_loop.run_until_complete(coroutine)

        return

    music.next_song()
    logging.debug("[play_next_song] advanced to next song") 

    coroutine = sync_vc_status()
    new_loop = asyncio.new_event_loop()
    new_loop.run_until_complete(coroutine)

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
async def sync_vc_status(reconnect_to_vc = False):
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
            if current_vc.is_playing() and current_vc_song != music.current_song:
                logging.debug(f"[sync_vc_status] stopped current song to play other one")
                current_vc.stop()

            # if this is true then we are already playing the right song and
            # therefore do not need to do anything to sync
            if current_vc.is_playing() and current_vc_song == music.current_song:
                logging.debug(f"[sync_vc_status] we are already playing the right song")
                return

            logging.debug(f"[sync_vc_status] playing the correct song...")
            current_vc.play(FFmpegPCMAudio(music.current_song.path), after=play_next_song)
            current_vc_song = music.current_song
        except Exception as e:
            logging.warning(f"[sync_vc_status] had error while syncing state, disconnecting and returning 2: {e}")

            await current_vc.disconnect()
            current_vc = None
            current_vc_song = None

            return 2

    '''
    path, title = val

    activities = message.author.voice

    global current_channel
    if current_channel == None:
        current_channel = await activities.channel.connect()
        print("Connecting to new channel")
    else:
        if not current_channel.is_connected():
            current_channel = await activities.channel.connect()
            print("Connecting to new channel")

    queue.append(path)

    if len(queue) == 1:
        play_next_song()

    await message.channel.send(f"Added {title} to the queue!")
    '''

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message: Message):
    global client
    global dc_bot
    global current_vc

    if message.author == client.user:
        return

    if message.content.startswith('$help'):
        logging.debug("[on_message] Printing help message")
        await message.channel.send(f'.\nCommand help:\n$play [song title or url]\
                                    \n$stop - pause the current song\
                                    \n$resume - unpause the current song\
                                    \n$clear - clears the queue\
                                    \n$next - skip the current song in the queue\
                                    \n$help - shows this message\
                                    \n\nMost commands can be abbreviated to one letter.')

    if message.content.startswith('$p ') or message.content.startswith('$play '):
        logging.debug("[on_message] trying to play song...")
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

            term = message.content[3:]
            await message.add_reaction('⌛')

            status = music.add_song_from_query(term, user = author)

            if status == 0:
                assert(music.latest_song is not None)

                logging.debug("[on_message] added song to queue")
                await message.channel.send(f"Added {music.latest_song.title} to the queue! ✅")
            else:
                logging.warning("[on_message] yt_dl module failed to find song")
                await message.channel.send(f"Sorry, I'm a little confused... 😕")
                return

            await sync_vc_status()
        except Exception as e:
            print("Caught exception while trying to play a song: ", e)
            logging.warning(f"[on_message] encountered exception while trying to play song: {e}")
            await message.channel.send(f"Sorry, I'm a little confused... 😕")


        '''
        path, title = val

        activities = message.author.voice

        global current_channel
        if current_channel == None:
            current_channel = await activities.channel.connect()
            print("Connecting to new channel")
        else:
            if not current_channel.is_connected():
                current_channel = await activities.channel.connect()
                print("Connecting to new channel")

        queue.append(path)

        if len(queue) == 1:
            play_next_song()

        await message.channel.send(f"Added {title} to the queue!")
        '''

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
        music.next_song()

        if refresh_state:
            await sync_vc_status()

        emoji = '⏭️'
        await message.add_reaction(emoji)

    if message.content.startswith('$q') or message.content.startswith('$queue'):
        logging.debug("[on_message] showing queue to user")
        await message.channel.send(f".\n{music.fmt_queue()}")

with open(".dc-token", "r") as f:
    token = f.readline()

client.run(token)

