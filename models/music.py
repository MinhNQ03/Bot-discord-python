import pafy
import discord
import asyncio
import io
import textwrap
import traceback
import aiohttp
from contextlib import redirect_stdout
import json
import asyncio
import inspect
import datetime
import json
import logging
import random
import os
import time as timeModule
import random
import youtube_dl
import requests
import pdb
from youtubesearchpython import VideosSearch
from youtubesearchpython import *
from datetime import datetime
from pprint import pprint
from youtube_dl import YoutubeDL
from discord.ext.commands import Bot
from discord.ext import commands
from discord import FFmpegPCMAudio
from yt_dlp import YoutubeDL


song_queue = {}
loop_status = {}

async def play_song(ctx, song):
    options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }
    player = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(song['url'], **options))
    player.volume = 0.5
    voice_client = ctx.voice_client
    if voice_client:
        voice_client.stop()
    else:
        voice_channel = ctx.author.voice.channel
        voice_client = await voice_channel.connect()

    voice_client.play(player)
    await ctx.send(f"Đang phát bài hát: {song['title']}")

    while voice_client.is_playing():
        await asyncio.sleep(1)

    # Check if the loop is enabled for this guild
    guild_id = ctx.guild.id
    loop_enabled = loop_status.get(guild_id, False)

    if loop_enabled:
        await play_song(ctx, song)  # If loop is enabled, play the song again


async def play_from_queue(ctx):
    guild_id = ctx.guild.id
    queue = song_queue.get(guild_id)

    if not queue:
        await ctx.send("Không có bài hát trong hàng đợi.")
        return

    loop_enabled = loop_status.get(guild_id, False)

    try:
        while True:
            for index, song in enumerate(queue, start=1):
                # Fetch video URL using yt-dlp
                url = await fetch_video_url(song['title'], song.get('artist', ''))
                if url is None:
                    await ctx.send(f"Không tìm thấy video cho bài hát '{song['title']}'.")
                    continue

                options = {
                    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                    'options': '-vn'
                }

                player = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **options))
                player.volume = 0.5

                voice_client = ctx.voice_client
                if not voice_client:
                    voice_channel = ctx.author.voice.channel
                    voice_client = await voice_channel.connect()

                voice_client.play(player)
                await ctx.send(f"Đang phát bài hát {index}/{len(queue)}: {song['title']}")

                while voice_client.is_playing():
                    await asyncio.sleep(1)

                if not loop_enabled:
                    break

            if not loop_enabled:
                break

        song_queue.pop(guild_id, None)
        await ctx.send("Hàng đợi đã không còn bài hát nào.")
    except Exception as e:
        await ctx.send(f"Có lỗi xảy ra khi phát nhạc: {e}")

async def fetch_video_url(title, artist=''):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',  # Force IPv4, remove this line if not needed
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(id)s.%(ext)s',
        'logger': None,
    }

    with YoutubeDL(ydl_opts) as ydl:
        query = f'{title} {artist}' if artist else title
        try:
            result = ydl.extract_info(query, download=False)
            if 'entries' in result:
                return result['entries'][0]['url']
            else:
                return result['url']
        except Exception as e:
            print(f"Error fetching video URL: {e}")
            return None

async def play_index(ctx, index: int):
    queue = song_queue.get(ctx.guild.id)
    if not queue:
        await ctx.send("Không có bài hát trong hàng đợi.")
        return

    if index <= 0 or index > len(queue):
        await ctx.send("Số thứ tự không hợp lệ.")
        return

    # Play the specified song
    song = queue[index - 1]
    await play_song(ctx, song)

async def add_song_to_queue(ctx, query):
    if not ctx.author.voice:
        await ctx.send("Bạn cần tham gia voice channel trước khi sử dụng lệnh này.")
        return

    channel = ctx.author.voice.channel

    # Lấy voice_client nếu đã tồn tại, nếu chưa thì tạo mới
    voice_client = ctx.voice_client
    try:
        if not voice_client:
            voice_client = await channel.connect()

        # Check if the input is a URL
        if "youtube.com" in query or "youtu.be" in query:
            url = query
        else:
            # If not a URL, perform a search using the query
            videos_search = VideosSearch(query, limit=1)
            result = videos_search.result()

            if result and 'result' in result and result['result']:
                url = result['result'][0]['link']
            else:
                await ctx.send(f"Không tìm thấy video cho bài hát '{query}'.")
                return

        video = pafy.new(url, ydl_opts={'skip_download': True})  # Thêm tùy chọn 'skip_download' để không tải xuống video

        bestaudio = video.getbestaudio()

        song = {'index': 0,'title': video.title,'url': bestaudio.url}
        # Kiểm tra xem có đang phát nhạc hay không
        if ctx.guild.id in song_queue:
            song_queue[ctx.guild.id].append(song)
        else:
            song_queue[ctx.guild.id] = [song]

        # Update the index of the song based on the position in the queue
        song['index'] = len(song_queue[ctx.guild.id])

        await ctx.send(f"{video.title} đã được thêm vào hàng đợi.")
    except Exception as e:
        logging.error(f"An error occurred while adding a song to the queue: {e}")
        await ctx.send(f"Có lỗi xảy ra khi thêm nhạc vào hàng đợi: {e}")


async def queue(ctx):
    queue = song_queue.get(ctx.guild.id)
    if not queue:
        await ctx.send("Không có bài hát trong hàng đợi.")
        return

    queue_list = "\n".join(f"{song['index']}. {song['title']}" for song in queue)
    await ctx.send(f"Hàng đợi nhạc:\n{queue_list}")


async def remove(ctx, index: int):
    queue = song_queue.get(ctx.guild.id)
    if not queue:
        await ctx.send("Không có bài hát trong hàng đợi.")
        return

    if index <= 0 or index > len(queue):
        await ctx.send("Số thứ tự không hợp lệ.")
        return

    removed_song = queue.pop(index - 1)
    await ctx.send(f"Đã xóa bài hát {removed_song['title']} khỏi hàng đợi.")

async def adjust_volume(ctx, vol: float):
    voice_client = ctx.voice_client
    if voice_client:
        if voice_client.is_playing():
            if 0.0 <= vol <= 2.0:
                voice_client.source.volume = vol
                await ctx.send(f"Âm lượng đã được đặt thành {vol}.")
            else:
                await ctx.send("Vui lòng nhập một giá trị âm lượng hợp lệ (từ 0.0 đến 2.0).")
        else:
            await ctx.send("Bot không đang phát nhạc.")
    else:
        await ctx.send("Bot không tham gia voice channel.")

async def on_voice_state_update(member, before, after):
    if not member.bot:  # Chỉ xử lý khi người tham gia voice channel không phải là bot
        if before.channel:  # Kiểm tra trước khi truy cập thuộc tính channel của voice state trước khi update
            voice_channel = before.channel
            voice_client = member.guild.voice_client
            if voice_client and voice_client.channel == voice_channel and len(voice_channel.members) == 1:
                # Nếu bot đang ở trong cùng voice channel và là người duy nhất trong channel,
                # và sau khi cập nhật thành viên không còn ở trong bất kỳ voice channel nào
                # thì bot sẽ rời khỏi channel tự động để giải phóng tài nguyên
                if not after.channel:
                    await voice_client.disconnect()
                    players.pop(member.guild.id, None)
                    song_queue.pop(member.guild.id, None)
                else:
                    if not voice_client.is_playing():
                        await play_from_queue(member.guild)  # Phát bài hát kế tiếp từ hàng đợi

