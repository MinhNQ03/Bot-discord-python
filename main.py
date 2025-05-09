import discord
import os
import json
import urllib.parse
import typing as t
import datetime as dt
import wavelink
import aiohttp
import lyricsgenius
import requests
import pdb
import logging
from youtubesearchpython import VideosSearch
from bs4 import BeautifulSoup
from enum import Enum
from vagalume import lyrics
from discord.ext import commands
from dotenv import load_dotenv
from lyricsgenius import Genius
from models.music import (
    add_song_to_queue,
    play_from_queue,
    on_voice_state_update as music_on_voice_state_update,
    queue as music_queue,
    remove as music_remove,
    play_index,
    adjust_volume
)
logging.basicConfig(level=logging.INFO)
load_dotenv()
intents = discord.Intents.default()
intents.voice_states = True
TOKEN = os.getenv("YOUTUTBE_TOKEN")
GENIUS_API_KEY = os.getenv("YOUR_GENIUS_API_KEY")  # Thay YOUR_GENIUS_API_KEY bằng API key của riêng bạn từ Genius API


client = commands.Bot(command_prefix ='=', intents=discord.Intents.all(), help_command=None)

song_queue = {}
players = {}
loop_status = {}


@client.event
async def on_ready():
    print('Bot is connected to discord')

@client.command()
async def ping(ctx):
    await ctx.send("Pong!")

class NoLyricsFound(commands.CommandError):
    pass


@client.command(pass_context=True)
async def pause(ctx):
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await ctx.send("Nhạc đã được tạm dừng.")
    else:
        await ctx.send("Bot không đang phát nhạc.")

@client.command(pass_context=True)
async def resume(ctx):
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await ctx.send("Nhạc đã được tiếp tục.")
    else:
        await ctx.send("Bot không đang tạm dừng.")

@client.command(pass_context=True)
async def skip(ctx):
    queue = song_queue.get(ctx.guild.id)

    voice_client = ctx.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("Nhạc đã được skip.")
        song_queue.pop(ctx.guild.id, None)
        if not queue:
            return
        else:
            await play_from_queue(ctx)  # Phát bài hát kế tiếp từ hàng đợi
    else:
        await ctx.send("Bot không đang phát nhạc.")

@client.command(pass_context=True)
async def clear(ctx):
    voice_client = ctx.voice_client
    if voice_client:
        await voice_client.disconnect()
        players.pop(ctx.guild.id, None)
        await ctx.send("Bot đã rời khỏi voice channel.")
    else:
        await ctx.send("Bot không tham gia voice channel.")

@client.command(pass_context=True)
async def join(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
    else:
        await ctx.send("Bạn cần tham gia voice channel trước khi sử dụng lệnh này.")

@client.command(pass_context=True)
async def leave(ctx):
    server = ctx.message.guild
    voice_client = client.voice_clients[0]
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        players.pop(ctx.guild.id, None)
        await ctx.send("Bot đã rời khỏi voice channel.")
    else:
        await ctx.send("Bot không tham gia voice channel.")

@client.command(pass_context=True)
async def play(ctx, *, arg=None):
    if arg is None:
        await ctx.send("Bạn cần cung cấp URL hoặc số thứ tự của bài hát để phát hoặc tên bài và tên ca sĩ.")
        return

    if arg.isdigit():
        index = int(arg)
        await play_index(ctx, index)
    else:
        await add_song_to_queue(ctx, arg)
        if not ctx.voice_client.is_playing():
            await play_from_queue(ctx)  # Phát bài hát kế tiếp từ hàng đợi

    # Update the loop status for the current guild
    guild_id = ctx.guild.id
    loop_enabled = loop_status.get(guild_id, False)
    await ctx.send(f"Loop {'enabled' if loop_enabled else 'disabled'} for the current song.")


@client.command(pass_context=True)
async def queue(ctx):
    await music_queue(ctx)  # Gọi hàm từ file music.py

@client.command(pass_context=True)
async def remove(ctx, index: int):
    await music_remove(ctx, index)  # Gọi hàm từ file music.py

@client.command(pass_context=True)
async def lyrics_command(ctx, name):
    name = name or (ctx.voice_client and ctx.voice_client.source.title)
    if not name:
        await ctx.send("Vui lòng cung cấp tên bài hát hoặc sử dụng lệnh này trong một voice channel.")
        return
    try:
        headers = {
            'Authorization': f'Bearer {GENIUS_API_KEY}'
        }
        response = requests.get(f'https://api.genius.com/search?q={urllib.parse.quote(name)}', headers=headers)
        data = response.json()

        if 'response' in data and 'hits' in data['response']:
            hits = data['response']['hits']
            if hits:
                song = hits[0]['result']
                lyrics_url = song['url']
                lyrics = f"{song['full_title']}:\n\n{lyrics_url}"

                await ctx.send(lyrics)  # Sending lyrics as a message to the Discord channel
            else:
                await ctx.send("Không tìm thấy lời bài hát.")
        else:
            await ctx.send("Không tìm thấy lời bài hát này.")
    except Exception as e:
        await ctx.send("Đã xảy ra lỗi khi lấy lời bài hát.")
        print(e)

@client.command(pass_context=True)
async def volume(ctx, vol: float):
    await adjust_volume(ctx, vol)

@client.command(pass_context=True)
async def loop(ctx):
    guild_id = ctx.guild.id
    # Check if the loop status is already set for this guild
    if guild_id in loop_status:
        # Toggle the loop status
        loop_status[guild_id] = not loop_status[guild_id]
    else:
        # If loop status is not set, enable the loop by default
        loop_status[guild_id] = True

    loop_enabled = loop_status[guild_id]
    await ctx.send(f"Loop {'enabled' if loop_enabled else 'disabled'} for the current song.")

@client.command()
async def help(ctx):
    help_embed = discord.Embed(title="Bot Help", description="Here is a list of available commands and their usage:", color=discord.Color.blue())

    help_embed.add_field(name=":loud_sound: =join", value="Make the bot join your voice channel.")
    help_embed.add_field(name=":mute: =leave", value="Make the bot leave the voice channel.")
    help_embed.add_field(name=":musical_note: =play <URL or search query>", value="Play a song from a URL or search query.")
    help_embed.add_field(name=":pause_button: =pause", value="Pause the currently playing song.")
    help_embed.add_field(name=":play_pause: =resume", value="Resume the paused song.")
    help_embed.add_field(name=":fast_forward: =skip", value="Skip the currently playing song.")
    help_embed.add_field(name=":stop_button: =clear", value="Clear the song queue and disconnect the bot.")
    help_embed.add_field(name=":inbox_tray: =queue", value="Show the song queue.")
    help_embed.add_field(name=":x: =remove <index>", value="Remove a song from the queue by its index.")
    help_embed.add_field(name=":sound: =volume <0.0-2.0>", value="Adjust the bot's volume (0.0 = minimum, 2.0 = maximum).")
    help_embed.add_field(name=":musical_note: =lyrics <song name>", value="Show the lyrics of a song.")
    help_embed.add_field(name=":ping_pong: =ping", value="Check if the bot is online and responsive.")

    help_embed.set_footer(text="You can use these commands by typing = followed by the command name.")
    help_embed.set_thumbnail(url="https://haycafe.vn/wp-content/uploads/2022/06/Hinh-anh-songoku-344x600.jpg")

    await ctx.send(embed=help_embed)

@client.event
async def on_voice_state_update(member, before, after):
    await music_on_voice_state_update(member, before, after)  # Gọi hàm từ file music.py

client.run(TOKEN)
