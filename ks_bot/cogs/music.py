"""유튜브 음악 재생 코그.

이전 구현은 길드별 상태를 중첩 dict(`queue["playing"]["vol"]`)로 관리하고,
1초 간격 폴링으로 다음 곡을 재생했다. 여기서는 상태를 데이터클래스로 모델링하고,
FFmpeg 재생 완료 콜백(`after`)이 이벤트를 깨우는 방식으로 바꿔 폴링을 없앴다.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field

import discord
from discord.ext import commands
from discord.voice_client import VoiceClient

from ks_bot.bot import KSBot
from ks_bot.core.youtube import FFMPEG_BEFORE_ARGS, TrackInfo, get_youtube
from ks_bot.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_VOLUME = 0.3
QUEUE_PAGE_SIZE = 5
CONFIRM_TIMEOUT = 30.0
MUSIC_EMBED_COLOR = discord.Colour.from_rgb(255, 0, 0)


@dataclass(frozen=True)
class Track:
    """재생 대기열의 한 곡."""

    info: TrackInfo
    requester_id: int

    @property
    def title(self) -> str:
        return self.info.title or '제목 없음'


@dataclass
class GuildPlayer:
    """길드 하나의 재생 상태."""

    guild_id: int
    voice: VoiceClient
    text_channel: discord.abc.Messageable
    queue: list[Track] = field(default_factory=list)
    current: Track | None = None
    volume: float = DEFAULT_VOLUME
    loop: bool = False
    shuffle: bool = False
    next_event: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None

    def pop_next(self) -> Track | None:
        """다음에 재생할 곡을 꺼낸다. 반복 재생이면 현재 곡을 유지한다."""
        if self.loop and self.current is not None:
            return self.current
        if not self.queue:
            return None
        index = random.randrange(len(self.queue)) if self.shuffle else 0
        return self.queue.pop(index)


def _guild_icon_url(guild: discord.Guild) -> str | None:
    return guild.icon.url if guild.icon else None


def _track_value(info: TrackInfo) -> str:
    return f'업로더: [`{info.uploader}`]({info.uploader_url})\n제목: [`{info.title}`]({info.webpage_url})'


class ConfirmView(discord.ui.View):
    """⭕/❌ 버튼으로 확인을 받는 뷰."""

    def __init__(self, author_id: int, timeout: float = CONFIRM_TIMEOUT):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.value: bool | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message('명령을 실행한 사람만 선택할 수 있어요.', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='확인', emoji='⭕', style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.value = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label='취소', emoji='❌', style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.value = False
        await interaction.response.defer()
        self.stop()


class PaginatorView(discord.ui.View):
    """임베드 목록을 버튼으로 넘겨보는 뷰."""

    def __init__(self, author_id: int, pages: list[discord.Embed], timeout: float = CONFIRM_TIMEOUT):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.pages = pages
        self.index = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    async def _show(self, interaction: discord.Interaction) -> None:
        self.index = max(0, min(self.index, len(self.pages) - 1))
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(emoji='⬅', style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.index -= 1
        await self._show(interaction)

    @discord.ui.button(emoji='⏹', style=discord.ButtonStyle.secondary)
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(view=None)
        self.stop()

    @discord.ui.button(emoji='➡', style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.index += 1
        await self._show(interaction)


async def confirm(ctx: commands.Context, message: discord.Message, timeout: float = CONFIRM_TIMEOUT) -> bool | None:
    """확인/취소를 물어본다. 승인=True, 거절=False, 시간초과=None."""
    view = ConfirmView(author_id=ctx.author.id, timeout=timeout)
    await message.edit(view=view)
    await view.wait()
    await message.edit(view=None)
    return view.value


class Music(commands.Cog, name='음악'):
    """유튜브 음악 재생."""

    def __init__(self, bot: KSBot):
        self.bot = bot
        self.players: dict[int, GuildPlayer] = {}

    async def cog_unload(self) -> None:
        for player in list(self.players.values()):
            await self._teardown(player)

    # ---------- 내부 헬퍼 ----------

    def get_player(self, ctx: commands.Context) -> GuildPlayer | None:
        return self.players.get(ctx.guild.id)

    async def _teardown(self, player: GuildPlayer) -> None:
        self.players.pop(player.guild_id, None)
        if player.task and not player.task.done():
            player.task.cancel()
        if player.voice.is_connected():
            await player.voice.disconnect(force=True)

    async def ensure_voice(self, ctx: commands.Context, *, allow_paused: bool = False) -> GuildPlayer | None:
        """음성 채널/재생 상태를 검사하고 플레이어를 반환한다. 문제가 있으면 안내 후 None."""
        if ctx.author.voice is None:
            await ctx.send(f'{ctx.author.mention} 먼저 음성 채널에 들어와주세요.')
            return None

        player = self.get_player(ctx)
        if player is None or not player.voice.is_connected():
            await ctx.send(f'{ctx.author.mention} 재생을 먼저 해주세요.')
            return None

        if not player.voice.is_playing() and not (allow_paused and player.voice.is_paused()):
            await ctx.send(f'{ctx.author.mention} 현재 재생중인 노래가 없습니다.')
            return None

        return player

    def _now_playing_embed(self, track: Track, *, title: str, field_name: str) -> discord.Embed:
        embed = discord.Embed(title=title, color=MUSIC_EMBED_COLOR)
        embed.add_field(name=field_name, value=_track_value(track.info), inline=False)
        requester = self.bot.get_user(track.requester_id)
        if requester is not None:
            embed.add_field(name='요청자', value=f'{requester.mention} (`{requester}`)', inline=False)
        if track.info.thumbnail:
            embed.set_image(url=track.info.thumbnail)
        return embed

    async def _player_loop(self, player: GuildPlayer) -> None:
        """대기열이 빌 때까지 순서대로 재생한다."""
        try:
            while True:
                track = player.pop_next()
                if track is None:
                    await player.text_channel.send(f'음악이 끝났어요. `{player.voice.channel}`에서 나갈께요.')
                    break

                is_repeat = player.loop and player.current is track
                player.current = track
                player.next_event.clear()

                source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(track.info.target_url, before_options=FFMPEG_BEFORE_ARGS),
                    volume=player.volume,
                )
                player.voice.play(source, after=lambda error: self._on_track_end(player, error))

                if not is_repeat:
                    await player.text_channel.send(embed=self._now_playing_embed(track, title='유튜브 음악 재생', field_name='재생 시작'))

                await player.next_event.wait()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('재생 루프에서 오류가 발생했습니다. guild_id=%s', player.guild_id)
        finally:
            player.task = None
            await self._teardown(player)

    def _on_track_end(self, player: GuildPlayer, error: Exception | None) -> None:
        """FFmpeg 재생 완료 콜백(별도 스레드에서 호출된다)."""
        if error:
            logger.error('재생 중 오류가 발생했습니다. guild_id=%s, error=%s', player.guild_id, error)
        self.bot.loop.call_soon_threadsafe(player.next_event.set)

    async def _toggle_option(self, ctx: commands.Context, *, attribute: str, on_text: str, off_text: str, label: str) -> None:
        """반복/랜덤 재생처럼 확인을 거쳐 켜고 끄는 옵션을 처리한다."""
        player = await self.ensure_voice(ctx, allow_paused=True)
        if player is None:
            return

        turning_on = not getattr(player, attribute)
        question = f'{ctx.author.mention} 정말로 {label}을(를) {"켤까요" if turning_on else "해제할까요"}?'
        message = await ctx.send(question)

        if await confirm(ctx, message) is not True:
            await message.edit(content=f'{ctx.author.mention} {label} 변경이 취소되었습니다.')
            return

        setattr(player, attribute, turning_on)
        await message.edit(content=on_text if turning_on else off_text)

    # ---------- 커맨드 ----------

    @commands.command(
        name='재생',
        help='음악을 재생할 수 있는 명령어. 사용법: /재생 <유튜브 링크> 또는 /재생 <검색어>',
        description='음악을 재생합니다.',
        aliases=['play'],
    )
    @commands.guild_only()
    async def play(self, ctx: commands.Context, *, url: str) -> None:
        message = await ctx.send('잠시만 기다려주세요...')

        if ctx.author.voice is None or ctx.author.voice.channel is None:
            await message.edit(content=f'{ctx.author.mention} 먼저 음성 채널에 들어와주세요.')
            return

        info = await get_youtube(url)
        if not info.is_playable:
            await message.edit(content=f'{ctx.author.mention} 재생할 수 있는 음악을 찾지 못했습니다.')
            return

        track = Track(info=info, requester_id=ctx.author.id)

        player = self.get_player(ctx)
        if player is None or not player.voice.is_connected():
            voice = ctx.voice_client or await ctx.author.voice.channel.connect()
            player = GuildPlayer(guild_id=ctx.guild.id, voice=voice, text_channel=ctx.channel)
            self.players[ctx.guild.id] = player

        player.queue.append(track)
        is_first = player.task is None

        embed = self._now_playing_embed(track, title='유튜브 음악 재생', field_name='재생 시작' if is_first else '재생 목록에 추가됨')
        await message.edit(content=None, embed=embed)

        if is_first:
            player.task = asyncio.create_task(self._player_loop(player))

    @commands.command(
        name='반복',
        help='재생중인 음악을 무한 반복하거나 무한 반복을 해제합니다.',
        description='재생중인 음악을 무한 반복하거나 무한 반복을 해제합니다.',
        aliases=['loop', 'repeat'],
    )
    @commands.guild_only()
    async def music_loop(self, ctx: commands.Context) -> None:
        await self._toggle_option(
            ctx,
            attribute='loop',
            label='무한반복',
            on_text=f'{ctx.author.mention} 이 음악을 무한반복할께요!',
            off_text=f'{ctx.author.mention} 무한반복이 해제되었습니다.',
        )

    @commands.command(
        name='랜덤재생',
        help='대기 리스트에서 음악을 무작위로 재생합니다.',
        description='대기 리스트에서 음악을 무작위로 재생합니다.',
        aliases=['random', 'shuffle'],
    )
    @commands.guild_only()
    async def shuffle(self, ctx: commands.Context) -> None:
        await self._toggle_option(
            ctx,
            attribute='shuffle',
            label='랜덤 재생',
            on_text=f'{ctx.author.mention} 랜덤 재생이 켜졌어요!',
            off_text=f'{ctx.author.mention} 랜덤 재생이 해제되었습니다.',
        )

    @commands.command(name='스킵', help='재생중인 음악을 스킵합니다.', description='재생중인 음악을 스킵합니다.', aliases=['skip'])
    @commands.guild_only()
    async def skip(self, ctx: commands.Context) -> None:
        player = await self.ensure_voice(ctx)
        if player is None:
            return
        # 스킵은 반복 재생보다 우선한다.
        player.current = None
        player.voice.stop()
        await ctx.send(f'{ctx.author.mention} 다음 곡으로 넘어갈께요.')

    @commands.command(name='정지', help='음악 재생을 멈춥니다.', description='음악 재생을 멈춥니다.', aliases=['stop'])
    @commands.guild_only()
    async def stop(self, ctx: commands.Context) -> None:
        player = await self.ensure_voice(ctx, allow_paused=True)
        if player is None:
            return
        player.queue.clear()
        player.loop = False
        player.current = None
        player.voice.stop()
        await ctx.send(f'{ctx.author.mention} 재생을 멈췄습니다.')

    @commands.command(name='일시정지', help='음악을 일시정지합니다.', description='음악을 일시정지합니다.', aliases=['pause'])
    @commands.guild_only()
    async def pause(self, ctx: commands.Context) -> None:
        player = await self.ensure_voice(ctx)
        if player is None:
            return
        player.voice.pause()
        await ctx.send(f'{ctx.author.mention} 플레이어를 일시정지했습니다.')

    @commands.command(name='계속재생', help='음악 일시정지를 해제합니다.', description='음악 일시정지를 해제합니다.', aliases=['resume'])
    @commands.guild_only()
    async def resume(self, ctx: commands.Context) -> None:
        player = await self.ensure_voice(ctx, allow_paused=True)
        if player is None:
            return
        player.voice.resume()
        await ctx.send(f'{ctx.author.mention} 음악을 계속 재생합니다.')

    @commands.command(
        name='강제연결해제',
        help='봇 오류로 음악 재생에 문제가 발생했을 때 강제로 접속을 해제합니다.',
        description='봇 오류로 음악 재생에 문제가 발생했을 때 강제로 접속을 해제합니다.',
        aliases=['나가', '제발나가', 'quit', 'leave', 'l', 'ㅣ', 'dc'],
    )
    @commands.guild_only()
    async def force_quit(self, ctx: commands.Context) -> None:
        player = self.get_player(ctx)
        if player is not None:
            await self._teardown(player)
        elif ctx.voice_client is not None:
            await ctx.voice_client.disconnect(force=True)
        else:
            await ctx.send('연결된 음성 채널이 없습니다.')
            return
        await ctx.send('강제 연결 해제가 완료되었습니다.')

    @commands.command(name='볼륨', help='음악의 볼륨을 조절합니다.', description='음악의 볼륨을 조절합니다.', aliases=['volume'])
    @commands.guild_only()
    async def volume(self, ctx: commands.Context, vol: int | None = None) -> None:
        player = await self.ensure_voice(ctx, allow_paused=True)
        if player is None:
            return

        if vol is None:
            await ctx.send(f'{ctx.author.mention} 현재 볼륨은 `{player.volume * 100:.0f}%` 입니다.')
            return
        if vol > 100:
            await ctx.send('숫자가 너무 큽니다.')
            return
        if vol <= 0:
            await ctx.send('숫자가 너무 작습니다.')
            return

        player.volume = vol / 100
        if isinstance(player.voice.source, discord.PCMVolumeTransformer):
            player.voice.source.volume = player.volume
        await ctx.send(f'{ctx.author.mention} 볼륨이 `{vol}%`로 변경되었습니다.')

    @commands.command(name='대기리스트', help='현재 대기 리스트를 보여줍니다.', description='현재 대기 리스트를 보여줍니다.', aliases=['playlist'])
    @commands.guild_only()
    async def queue_list(self, ctx: commands.Context) -> None:
        player = self.get_player(ctx)
        if player is None or player.current is None:
            await ctx.send('현재 재생중이 아닙니다.')
            return

        pages = self._build_queue_pages(ctx, player)
        if len(pages) == 1:
            await ctx.send(embed=pages[0])
            return
        await ctx.send(embed=pages[0], view=PaginatorView(author_id=ctx.author.id, pages=pages))

    def _build_queue_pages(self, ctx: commands.Context, player: GuildPlayer) -> list[discord.Embed]:
        icon_url = _guild_icon_url(ctx.guild)

        now_embed = discord.Embed(title='현재 재생중', colour=discord.Color.green())
        now_embed.set_author(name=ctx.guild.name, icon_url=icon_url)
        now_embed.add_field(name='정보', value=_track_value(player.current.info), inline=False)
        requester = self.bot.get_user(player.current.requester_id)
        if requester is not None:
            now_embed.add_field(name='요청자', value=f'{requester.mention} (`{requester}`)', inline=False)
        now_embed.add_field(name='현재 볼륨', value=f'{player.volume * 100:.0f}%', inline=False)
        now_embed.add_field(name='대기중인 음악 개수', value=f'{len(player.queue)}개')
        if player.voice.is_paused():
            now_embed.add_field(name='플레이어 상태', value='현재 일시정지 상태입니다.', inline=False)
        elif player.shuffle:
            now_embed.add_field(name='플레이어 상태', value='랜덤 재생 기능이 켜져있습니다.', inline=False)
        if player.current.info.thumbnail:
            now_embed.set_image(url=player.current.info.thumbnail)

        pages = [now_embed]
        for start in range(0, len(player.queue), QUEUE_PAGE_SIZE):
            chunk = player.queue[start : start + QUEUE_PAGE_SIZE]
            embed = discord.Embed(title='뮤직 대기 리스트', color=discord.Colour.from_rgb(225, 225, 225))
            embed.set_author(name=ctx.guild.name, icon_url=icon_url)
            for offset, track in enumerate(chunk, start=start + 1):
                track_requester = self.bot.get_user(track.requester_id)
                requester_text = f'{track_requester.mention} (`{track_requester}`)' if track_requester else '알 수 없음'
                embed.add_field(
                    name=f'대기리스트{offset}',
                    value=f'제목: [`{track.title}`]({track.info.webpage_url})\n요청자: {requester_text}',
                    inline=False,
                )
            pages.append(embed)

        return pages


async def setup(bot: KSBot) -> None:
    await bot.add_cog(Music(bot))
