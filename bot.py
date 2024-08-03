import asyncio
import json
import logging
import logging.config
import os
from datetime import datetime
from urllib.parse import urlparse

import aiohttp
import discord
import dotenv
import requests
import yt_dlp
from discord import Colour, Webhook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from twitchio.ext import commands

from orm import Base, Request, Song, User

config = {
    "client_id": os.environ["CLIENT_ID"],
    "client_secret": os.environ["CLIENT_SECRET"],
    "nick": os.environ["BOT_NICK"],
    "prefix": os.environ["BOT_PREFIX"],
    "access_token": os.environ["ACCESS_TOKEN"],
    "refresh_token": os.environ["REFRESH_TOKEN"],
    "channel": os.environ["CHANNEL"],
}


class Bot(commands.Bot):

    def __init__(self, engine):
        super().__init__(
            token=config["access_token"],
            client_id=config["client_id"],
            nick=config["nick"],
            prefix=config["prefix"],
            initial_channels=[config["channel"]],
        )
        self.engine = engine
        self.logger = logging.getLogger("Bot")

    async def event_ready(self):
        self.logger.info(f"Logged in as | {config['nick']}")
        while True:
            expiration = await self.refresh_token()
            self.logger.info("Access-Token expired, refreshing")
            await asyncio.sleep(expiration - 1800)

    async def refresh_token(self):
        url = "https://id.twitch.tv/oauth2/token"
        data = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "grant_type": "refresh_token",
            "refresh_token": config["refresh_token"],
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(url, data=data, headers=headers)
        token = response.json()

        config["access_token"] = token["access_token"]
        config["refresh_token"] = token["refresh_token"]
        self._connection._token = token["access_token"]

        dotenv_file = dotenv.find_dotenv()
        dotenv.set_key(dotenv_file, "ACCESS_TOKEN", config["access_token"])
        dotenv.set_key(dotenv_file, "REFRESH_TOKEN", config["refresh_token"])

        self.logger.info(f"Access-Token refreshed, expires in {token['expires_in']}")

        return token["expires_in"]

    async def event_message(self, message):
        # ignore own messages
        if message.echo:
            return

        await self.handle_commands(message)

    async def event_command_error(self, context: commands.Context, error: Exception):
        if isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, commands.ArgumentParsingFailed):
            return

    @commands.command(name="sr")
    async def sr(self, ctx: commands.Context, url):
        self.logger.info(f"Song-request from {ctx.author.name}: {url}")

        parsed_url = urlparse(url=url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            self.logger.error(f"Skipping invalid argument: '{url}'")
            return

        twitch_user = await ctx.author.user()
        session = Session(self.engine)

        user_select = select(User).where(User.id == twitch_user.id)
        user = session.scalar(user_select)

        if not user:
            self.logger.info(f"New User: '{ctx.author.name}'")
            user = User(
                id=twitch_user.id,
                name=twitch_user.name,
                display_name=twitch_user.display_name,
                created_at=twitch_user.created_at,
            )
            session.add(user)
            session.commit()
        else:
            self.logger.info(f"User found: '{ctx.author.name}' -> '{user.id}'")

        song_select = select(Song).where(Song.url == url)
        song = session.scalar(song_select)

        if not song:
            self.logger.info(f"New Song: '{url}'")
            ydl_opts = {
                "outtmpl": f'{os.environ["OUTPUT"]}/%(title)s-%(id)s.%(ext)s',
                "format": "m4a/bestaudio/best",
                "overwrites": True,
                "restrictfilenames": True,
                "writethumbnail": "true",
                "postprocessors": [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "opus"},
                    {"key": "FFmpegMetadata", "add_metadata": True},
                    {"key": "EmbedThumbnail", "already_have_thumbnail": False},
                ],
                "noprogress": True,
                "verbose": False,
                "quiet": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if os.environ["OUTPUT"]:
                    ydl.process_info(info)
                song = Song(
                    id=info["id"],
                    title=info["title"],
                    url=info["webpage_url"],
                    duration=info["duration"],
                    upload_date=info["upload_date"],
                    channel=info["channel"],
                    thumbnail=info["thumbnail"],
                )
                session.add(song)
                session.commit()
        else:
            self.logger.info(f"Song found: '{url}' -> '{song.id}'")

        request = Request(timestamp=datetime.now(), user_id=user.id, song_id=song.id)
        session.add(request)
        session.commit()

        self.logger.info(f"New Request: {request.id} -> ({user.id}, {song.id})")

        session.close()
        if os.environ["WEBHOOK"]:
            await self.send_notification(
                os.environ["WEBHOOK"], ctx.author.name, song.title, song.url
            )

    async def send_notification(self, webhook, author, title, url):
        async with aiohttp.ClientSession() as session:
            webhook = Webhook.from_url(webhook, session=session)
            embed = discord.Embed(
                title="Song Reqest",
                description=f"{title}",
                timestamp=datetime.now(),
                color=Colour.dark_blue(),
            )
            embed.add_field(name="Title", value=f"{title}")
            embed.add_field(name="URL", value=f"{url}")
            embed.add_field(name="Requester", value=f"{author}")

            await webhook.send(content="", embed=embed, username="Twitch-SR")
            await webhook.send(content=f"{url}")


def setupSQLLogging():
    sqlLogger = logging.getLogger("sqlalchemy")
    sqlLogger.propagate = False
    # Ensure logfile is truncated for demonstration
    handler = logging.FileHandler("sql.log", mode="w")
    sqlLogger.setLevel(logging.DEBUG)

    sqlLogger.handlers = []

    handler.setLevel(logging.DEBUG)
    sqlLogger.addHandler(handler)

    # Suppress output from child loggers
    logging.getLogger("sqlalchemy.engine").handlers = []
    logging.getLogger("sqlalchemy.pool").handlers = []


def filter_maker(level):
    level = getattr(logging, level)

    def filter(record):
        return record.levelno <= level

    return filter


if __name__ == "__main__":
    # setup logging
    logging.config.dictConfig(json.load(open("logging_config.json", "r")))
    logger = logging.getLogger()
    setupSQLLogging()

    if os.environ["OUTPUT"]:
        os.makedirs(os.environ["OUTPUT"], exist_ok=True)

    logger.info("creating DB engine")
    engine = create_engine(r"sqlite:///database.db", echo=False)

    logger.info("creating DB schema")
    Base.metadata.create_all(engine)

    logger.info("starting Twitch bot")
    bot = Bot(engine)
    bot.run()
