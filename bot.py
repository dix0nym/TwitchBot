import os
import json
from twitchio.ext import commands
import logging
import logging.config
import discord
from discord import Webhook
from discord import Colour
import aiohttp
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from urllib.parse import urlparse
from sqlalchemy import select
from orm import Base, User, Request, Song
import yt_dlp
from datetime import datetime


class Bot(commands.Bot):

    def __init__(self, engine):
        super().__init__(token=os.environ['TMI_TOKEN'],
                         client_id=os.environ['CLIENT_ID'],
                         nick=os.environ['BOT_NICK'],
                         prefix=os.environ['BOT_PREFIX'],
                         initial_channels=[os.environ['CHANNEL']]
                         )
        self.engine = engine
        self.logger = logging.getLogger("Bot")

    async def event_ready(self):
        self.logger.info(f"Logged in as | {os.environ['BOT_NICK']}")

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

    @commands.command(name='sr')
    async def sr(self, ctx: commands.Context, url):
        self.logger.info(
            f"Song-request from {ctx.author.name}: {url}")

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
            user = User(id=twitch_user.id, name=twitch_user.name,
                        display_name=twitch_user.display_name, created_at=twitch_user.created_at)
            session.add(user)
            session.commit()
        else:
            self.logger.info(f"User found: '{ctx.author.name}' -> '{user.id}'")

        song_select = select(Song).where(Song.url == url)
        song = session.scalar(song_select)

        if not song:
            self.logger.info(f"New Song: '{url}'")
            ydl_opts = {
                'outtmpl': f'{os.environ["OUTPUT"]}/%(title)s-%(id)s.%(ext)s',
                'format': 'm4a/bestaudio/best',
                'overwrites': True,
                'restrictfilenames': True,
                'writethumbnail': 'true',
                'postprocessors': [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'opus'},
                    {'key': 'FFmpegMetadata', 'add_metadata': True},
                    {'key': 'EmbedThumbnail', 'already_have_thumbnail': False}
                ],
                'noprogress': True,
                'verbose': False,
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if os.environ['OUTPUT']:
                    ydl.process_info(info)
                song = Song(id=info['id'], title=info['title'], url=info['webpage_url'],
                            duration=info['duration'], upload_date=info['upload_date'],
                            channel=info['channel'], thumbnail=info['thumbnail'])
                session.add(song)
                session.commit()
        else:
            self.logger.info(f"Song found: '{url}' -> '{song.id}'")

        request = Request(timestamp=datetime.now(),
                          user_id=user.id, song_id=song.id)
        session.add(request)
        session.commit()

        self.logger.info(
            f"New Request: {request.id} -> ({user.id}, {song.id})")

        session.close()
        if os.environ['WEBHOOK']:
            await self.send_notification(os.environ['WEBHOOK'], ctx.author.name, song.title, song.url)

    async def send_notification(self, webhook, author, title, url):
        async with aiohttp.ClientSession() as session:
            webhook = Webhook.from_url(webhook, session=session)
            e = discord.Embed(title="Song Reqest", description=f"{title}", timestamp=datetime.now(),
                              color=Colour.dark_blue())
            e.add_field(name="Title", value=f"{title}")
            e.add_field(name="URL", value=f"{url}")
            e.add_field(name="Requester", value=f"{author}")

            await webhook.send(content="", embed=e, username="Twitch-SR")
            await webhook.send(content=f"{url}")


def setupSQLLogging():
    sqlLogger = logging.getLogger('sqlalchemy')
    sqlLogger.propagate = False
    # Ensure logfile is truncated for demonstration
    handler = logging.FileHandler('sql.log', mode='w')
    sqlLogger.setLevel(logging.DEBUG)

    sqlLogger.handlers = []

    handler.setLevel(logging.DEBUG)
    sqlLogger.addHandler(handler)

    # Suppress output from child loggers
    logging.getLogger('sqlalchemy.engine').handlers = []
    logging.getLogger('sqlalchemy.pool').handlers = []


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

    if os.environ['OUTPUT']:
        os.makedirs(os.environ['OUTPUT'], exist_ok=True)

    logger.info("creating DB engine")
    engine = create_engine(r"sqlite:///database.db", echo=False)

    logger.info("creating DB schema")
    Base.metadata.create_all(engine)

    logger.info("starting Twitch bot")
    bot = Bot(engine)
    bot.run()
