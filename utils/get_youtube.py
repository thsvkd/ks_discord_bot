import asyncio
from youtubesearchpython import VideosSearch
from pytube import YouTube
from urllib.parse import urlparse

ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
before_args = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
loop = asyncio.get_event_loop()


async def get_youtube(url: str):
    if is_valid_url(url):
        return await loop.run_in_executor(None, _get_youtube, url)
    else:
        url = search_youtube(url)
        return await loop.run_in_executor(None, _get_youtube, url)


def _get_youtube(url: str):
    yt = YouTube(url)
    if not bool(
        url.startswith("https://")
        or url.startswith("http://")
        or url.startswith("youtu.be")
        or url.startswith("youtube.com")
    ):
        print("not youtube url...")
        return False

    target_url = yt.streams.filter(only_audio=True).last()
    info = dict(
        webpage_url=url,
        title=yt.title,
        uploader=yt.author,
        uploader_url=yt.channel_url,
        target_url=target_url.url,
        thumbnail=yt.thumbnail_url,
    )
    return info


def search_youtube(query: str, max_results=1):
    try:
        videos_search = VideosSearch(query, limit=max_results)

        if videos_search.result()["result"]:
            first_video = videos_search.result()["result"][0]
            video_url = first_video["link"]
            return video_url
        else:
            return None
    except Exception as e:
        print(f"오류 발생: {e}")
        return None


def is_valid_url(input_string):
    try:
        result = urlparse(input_string)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


if __name__ == "__main__":
    # res = loop.run_until_complete(get_youtube("https://www.youtube.com/watch?v=1SAXBLZLYbA"))
    # print(res)
    res = loop.run_until_complete(get_youtube("이무진 신호등"))
    print(res)
