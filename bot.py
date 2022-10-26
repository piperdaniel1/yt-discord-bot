# This example requires the 'message_content' intent.

import discord
from yt_dl import *

# Must implement a global queue class
# Should store paths to mp3 so that they
# can be immediately played
#
# Need to have a listener to change queue
# when the bot finishes a song.

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

current_channel = None

queue = []

def play_next_song(error=None):
    if len(queue) > 1:
        queue.pop(0)

    if len(queue) > 0:
        next = queue[0]

        if current_channel != None:
            current_channel.play(discord.FFmpegPCMAudio(next), after=play_next_song)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
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
        await message.add_reaction('🔃')
        val = download_from_search(term, force=False)

        if val == 1 or val == None:
            await message.channel.send("Hmm, I'm a little confused.")
            return

        path, title = val

        activities = message.author.voice

        global current_channel
        if activities.channel != current_channel or current_channel == None:
            if current_channel != None:
                await current_channel.disconnect()
            current_channel = await activities.channel.connect()

        queue.append(path)

        if len(queue) == 1:
            play_next_song()

        await message.channel.send(f"Added {title} to the queue!")

    if message.content.startswith('$s') or message.content.startswith('$stop'):
        if current_channel == None:
            await message.channel.send(f"I'm not playing anything right now!")
            return

        if current_channel.is_playing():
            current_channel.pause()

        emoji = '⏸️'
        await message.add_reaction(emoji)

    if message.content.startswith('$r') or message.content.startswith('$resume'):
        if current_channel == None:
            await message.channel.send(f"I'm not playing anything right now!")
            return

        if current_channel.is_paused():
            current_channel.resume()

        emoji = '▶️'
        await message.add_reaction(emoji)

    if message.content.startswith('$c') or message.content.startswith('$clear'):
        if current_channel == None:
            await message.channel.send(f"I'm not playing anything right now!")
            return

        current_channel.stop()

        emoji = '🛑'
        await message.add_reaction(emoji)

    if message.content.startswith('$n') or message.content.startswith('$next'):
        if current_channel == None:
            await message.channel.send(f"I'm not playing anything right now!")
            return

        current_channel.stop()
        play_next_song()

        emoji = '⏭️'
        await message.add_reaction(emoji)

with open(".dc-token", "r") as f:
    token = f.readline()

client.run(token)

