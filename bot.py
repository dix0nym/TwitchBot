import os
import json
from twitchio.ext import commands
import logging
from logging.config import fileConfig
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
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
        self.logger = logging.getLogger("Bot")

    async def event_ready(self):
        self.logger.info(f"Logged in as | {os.environ['BOT_NICK']}")

    async def event_message(self, message):
        # ignore own messages
        if message.echo:
            return

        await self.handle_commands(message)

    @commands.command(name='sr')
    async def sr(self, ctx: commands.Context, url):
        self.logger.info(
            f"received song-request from {ctx.author.name}: {url}")
        twitch_user = await ctx.author.user()
        session = Session(engine)

        user_select = select(User).where(User.id == twitch_user.id)
        user = session.scalar(user_select)

        if not user:
            self.logger.info(f"User {ctx.author.name} unkown -> creating")
            user = User(id=twitch_user.id, name=twitch_user.name,
                        display_name=twitch_user.display_name, created_at=twitch_user.created_at)
            session.add(user)
            session.commit()
        else:
            self.logger.info(f"User {ctx.author.name} found in DB: {user.id}")

        song_select = select(Song).where(Song.url == url)
        song = session.scalar(song_select)

        if not song:
            self.logger.info(f"Song {url} unkown -> creating")
            ytdlp_options = {
                'noprogress': True,
                'verbose': False,
                "quiet": True,
            }
            with yt_dlp.YoutubeDL(ytdlp_options) as ydl:
                info = ydl.extract_info(url, download=False)
                song = Song(id=info['id'], title=info['title'], url=info['webpage_url'],
                            duration=info['duration'], upload_date=info['upload_date'], channel=info['channel'])
                session.add(song)
                session.commit()
        else:
            self.logger.info(f"Song {url} found in DB: {song.id}")

        request = Request(timestamp=datetime.now(),
                          user_id=user.id, song_id=song.id)
        session.add(request)
        session.commit()

        self.logger.info(
            f"Request {request.id} created ({user.id}, {song.id})")

        session.close()

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
    logging.config.dictConfig(json.load(open("logging_config.json", "r")))
    logger = logging.getLogger()
    setupSQLLogging()

    logger.info("creating DB engine")

    engine = create_engine(r"sqlite:///database.db", echo=False)

    logger.info("creating DB schema")
    Base.metadata.create_all(engine)

    logger.info("starting Twitch bot")
    bot = Bot(engine)
    bot.run()
