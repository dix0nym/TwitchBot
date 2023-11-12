from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import DateTime
from typing import List
from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[DateTime] = mapped_column(DateTime())

    requests: Mapped[List["Request"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, name={self.name!r}, display_name={self.display_name!r})"


class Request(Base):
    __tablename__ = "request"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[DateTime] = mapped_column(DateTime())
    user_id: Mapped[id] = mapped_column(ForeignKey("user.id"))
    user: Mapped["User"] = relationship(back_populates="requests")

    song_id: Mapped[int] = mapped_column(ForeignKey("song.id"))
    song: Mapped["Song"] = relationship(back_populates="requests")

    def __repr__(self) -> str:
        return f"Request(id={self.id!r}, timestamp={self.timestamp!r}, user={self.user!r}), song={self.song!r})"


class Song(Base):
    __tablename__ = "song"

    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(255))
    duration: Mapped[int] = mapped_column(Integer())
    upload_date: Mapped[str] = mapped_column(String(8))
    channel: Mapped[str] = mapped_column(String(100))
    thumbnail: Mapped[str] = mapped_column(String(255))

    requests: Mapped[List["Request"]] = relationship(
        back_populates="song", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Request(id={self.id!r}, title={self.title!r}, url={self.url!r})"
