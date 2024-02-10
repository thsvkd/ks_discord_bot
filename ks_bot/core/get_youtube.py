import asyncio
from youtubesearchpython import VideosSearch
from urllib.parse import urlparse
from yt_dlp import YoutubeDL


async def is_valid_url(input_string) -> bool:
    try:
        result = urlparse(input_string)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


async def get_youtube_info(url: str) -> dict:
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
    }

    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, lambda: extract_info_with_ydl(ydl_opts, url))
    return info


def extract_info_with_ydl(ydl_opts, url):
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        if not info_dict:
            return {}
        return {
            'webpage_url': info_dict.get('webpage_url', ''),
            'title': info_dict.get('title', ''),
            'uploader': info_dict.get('uploader', ''),
            'uploader_url': info_dict.get('channel_url', ''),
            'target_url': info_dict.get('url', ''),
            'thumbnail': info_dict.get('thumbnail', ''),
        }


async def search_youtube(query: str, max_results=1) -> str:
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


async def get_youtube(url: str) -> dict:
    if not await is_valid_url(url):
        url = await search_youtube(url)
    if not url:
        print("No valid URL found.")
        return {}
    return await get_youtube_info(url)


if __name__ == "__main__":
    url_or_query = "이무진 신호등"
    result = asyncio.run(get_youtube(url_or_query))
    print(result)
