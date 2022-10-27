# This example requires the 'message_content' intent.

import discord
from discord.voice_client import VoiceClient
from yt_dl import *
from bot import MusicBot, Song

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

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    global client
    global dc_bot
    global current_vc

    if message.author == client.user:
        return

    if message.content.startswith('$help'):
        await message.channel.send(f'.\nCommand help:\n$play [song title or url]\
                                    \n$stop - pause the current song\
                                    \n$resume - unpause the current song\
                                    \n$clear - clears the queue\
                                    \n$next - skip the current song in the queue\
                                    \n$help - shows this message\
                                    \n\nMost commands can be abbreviated to one letter.')

    if message.content.startswith('$t '):
        activities = message.author.voice
        print(activities)
        print(activities.channel)
        print(message.author)

        my_channel = await activities.channel.connect()
        print(my_channel)

    if message.content.startswith('$p ') or message.content.startswith('$play '):
        term = message.content[3:]
        await message.add_reaction('⌛')

        status = music.add_song_from_query(term, user = message.author)

        if status == 0:
            assert(music.latest_song is not None)

            await message.channel.send(f"Added {music.latest_song.title} to the queue! ✅")
        else:
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
        '''
        if current_channel == None:
            await message.channel.send(f"I'm not playing anything right now!")
            return

        if current_channel.is_playing():
            current_channel.pause()
        '''

        emoji = '⏸️'
        await message.add_reaction(emoji)

    if message.content.startswith('$r') or message.content.startswith('$resume'):
        '''
        if current_channel == None:
            await message.channel.send(f"I'm not playing anything right now!")
            return

        if current_channel.is_paused():
            current_channel.resume()
        '''

        emoji = '▶️'
        await message.add_reaction(emoji)

    if message.content.startswith('$c') or message.content.startswith('$clear'):
        '''
        if current_channel == None:
            await message.channel.send(f"I'm not playing anything right now!")
            return

        await current_channel.disconnect()
        '''
        music.clear_queue()

        emoji = '🛑'
        await message.add_reaction(emoji)

    if message.content.startswith('$n') or message.content.startswith('$next'):
        '''
        if current_channel == None:
            await message.channel.send(f"I'm not playing anything right now!")
            return

        current_channel.stop()
        play_next_song()
        '''
        music.next_song()

        emoji = '⏭️'
        await message.add_reaction(emoji)

    if message.content.startswith('$q') or message.content.startswith('$queue'):
        await message.channel.send(f".\n{music.fmt_queue()}")

with open(".dc-token", "r") as f:
    token = f.readline()

client.run(token)

