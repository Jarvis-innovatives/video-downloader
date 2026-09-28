import os
import json
import re
import tempfile
import shutil
import glob
import requests
import imageio_ffmpeg
import yt_dlp

import threading
import uuid
import time
import io
import base64
from PIL import Image, ImageEnhance, ImageFilter

from django.shortcuts import render
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.templatetags.static import static
from .models import DownloadLog



def get_ffmpeg_path():
    """Returns path to binary ffmpeg executable provided by imageio-ffmpeg."""
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def get_base_ydl_opts():
    """Returns resilient yt-dlp options bypassing YouTube bot detection and IP challenges."""
    browser_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Sec-Fetch-Mode': 'navigate',
    }

    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'http_headers': browser_headers,
        'cookiesfrombrowser': None,
        'extractor_args': {
            'youtube': {
                'player_client': ['tv', 'mweb', 'ios', 'android'],
                'player_skip': ['webpage', 'configs'],
            }
        },
        'geo_bypass': True,
        'ignoreerrors': False,
    }

    # Use cookies.txt file if present and valid
    cookie_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cookies.txt')
    if os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 50:
        opts['cookiefile'] = cookie_file

    return opts


def detect_platform(url: str) -> str | None:
    """Detects social/media platform from URL."""
    u = url.lower().strip()
    if 'youtube.com' in u or 'youtu.be' in u:
        return 'YouTube'
    if 'instagram.com' in u:
        return 'Instagram'
    if 'tiktok.com' in u:
        return 'TikTok'
    if 'moviebox' in u or 'movie-box' in u:
        return 'MovieBox'
    return None


def format_duration(seconds):
    """Formats duration in seconds to MM:SS or HH:MM:SS."""
    if not seconds:
        return "N/A"
    try:
        seconds = int(seconds)
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    except Exception:
        return "N/A"


def format_views(count):
    """Formats view count to human readable format (e.g. 2.4M views)."""
    if not count:
        return "N/A"
    try:
        count = int(count)
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M views"
        elif count >= 1_000:
            return f"{count / 1_000:.1f}K views"
        return f"{count} views"
    except Exception:
        return "N/A"


def fetch_moviebox_metadata(url: str):
    """Extracts metadata and full feature movie stream URL from MovieBox links, bypassing the 4-minute web preview restriction."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    title = 'MovieBox Full Movie'
    thumb_url = None
    duration_str = "N/A"
    full_video_url = None
    is_preview_clip = True

    # 1. Scrape original page HTML for title, thumbnail, and stream links
    try:
        r = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        html = r.text

        m_title = re.search(r'<title>(.*?)</title>', html, re.I)
        if m_title:
            clean_t = m_title.group(1).replace('Watch ', '').replace(' Streaming Online on Moviebox', '').replace(' Moviebox', '').replace(' Free', '').strip()
            if clean_t:
                title = clean_t

        m_thumb = re.search(r'"thumbnailUrl"\s*:\s*\[\s*"([^"]+)"', html)
        if not m_thumb:
            m_thumb = re.search(r'property="og:image"\s+content="([^"]+)"', html)
        if m_thumb:
            thumb_url = m_thumb.group(1).replace('\\/', '/')

        m_dur = re.search(r'"duration"\s*:\s*(\d+)', html)
        if m_dur:
            dur_secs = int(m_dur.group(1))
            if dur_secs > 600:
                duration_str = format_duration(dur_secs)

        # Check for candidates in HTML
        candidates = re.findall(r'https?://[^\s"\'<>]+\.(?:mp4|m3u8)[^\s"\'<>]*', html, re.I)
        for cand in candidates:
            cand_lower = cand.lower()
            if not any(k in cand_lower for k in ['-ld.mp4', 'trailer', 'preview', 'sample', 'teaser', 'promo', 'short']):
                full_video_url = cand
                is_preview_clip = False
                break
    except Exception:
        pass

    # 2. If the page only provides a -ld.mp4 / trailer preview clip, bypass restriction by resolving full movie stream
    if not full_video_url or is_preview_clip:
        clean_search_title = re.sub(r'[^\w\s]', ' ', title).strip()
        if clean_search_title and clean_search_title.lower() != 'moviebox full movie':
            try:
                ffmpeg_path = get_ffmpeg_path()
                ydl_opts = get_base_ydl_opts()
                ydl_opts.update({
                    'extract_flat': False,
                    'http_headers': headers,
                })
                if ffmpeg_path:
                    ydl_opts['ffmpeg_location'] = ffmpeg_path

                search_query = f"ytsearch1:{clean_search_title} full movie"
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    search_info = ydl.extract_info(search_query, download=False)
                    if search_info and 'entries' in search_info and search_info['entries']:
                        match = search_info['entries'][0]
                        dur = match.get('duration')
                        if dur:
                            duration_str = format_duration(dur)
                        if not thumb_url:
                            thumb_url = match.get('thumbnail')

                        formats = match.get('formats', [])
                        for f in reversed(formats):
                            f_url = f.get('url')
                            if f_url and f.get('vcodec') != 'none':
                                full_video_url = f_url
                                break
                        if not full_video_url:
                            full_video_url = match.get('url') or match.get('webpage_url')
            except Exception:
                pass

    return {
        'title': title,
        'channel': 'MovieBox Full Feature',
        'duration': duration_str,
        'views': 'Full Movie Stream',
        'thumbnail_url': thumb_url,
        'preview_url': full_video_url,
        'direct_url': full_video_url or url,
    }


ALL_VIDEO_QUALITIES = ["240p", "360p", "480p", "720p", "1080p", "1440p", "2160p"]
MP3_QUALITIES = ["128 kbps", "192 kbps", "256 kbps", "320 kbps"]


def index(request):
    """Renders main SnapGrab single-page view."""
    return render(request, 'index.html')


def enhance_image(request):
    """Renders the enhance-image landing page using the static background image."""
    return render(request, 'enhance_image.html')


@csrf_exempt
def api_enhance_image(request):
    """Backend endpoint to process and enhance uploaded image to HD or Ultra HD quality using PIL filters."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    image_file = request.FILES.get('image')
    quality = request.POST.get('quality', 'hd').lower().strip()

    if not image_file:
        try:
            data = json.loads(request.body)
            b64_data = data.get('image_b64', '')
            quality = data.get('quality', 'hd').lower().strip()
            if b64_data and ',' in b64_data:
                b64_data = b64_data.split(',')[1]
            if b64_data:
                image_bytes = base64.b64decode(b64_data)
                image_file = io.BytesIO(image_bytes)
        except Exception:
            pass

    if not image_file:
        return JsonResponse({'error': 'No image file uploaded. Please upload a valid image.'}, status=400)

    try:
        img = Image.open(image_file)
        orig_width, orig_height = img.size

        # Determine scale factor and enhancement parameters based on requested quality
        if quality in ['ultra-hd', 'ultrahd', '4k', 'ultra']:
            scale_factor = 2.0
            sharpness_val = 1.8
            contrast_val = 1.15
            color_val = 1.12
            unsharp_radius = 2.0
            unsharp_percent = 150
            quality_label = 'Ultra HD Quality'
        else:  # Default HD
            scale_factor = 1.5
            sharpness_val = 1.4
            contrast_val = 1.08
            color_val = 1.06
            unsharp_radius = 1.5
            unsharp_percent = 120
            quality_label = 'HD Quality'

        new_width = max(1, int(orig_width * scale_factor))
        new_height = max(1, int(orig_height * scale_factor))

        # Resample with Lanczos filter for high quality upscaling
        try:
            resample_filter = Image.Resampling.LANCZOS
        except AttributeError:
            resample_filter = getattr(Image, 'LANCZOS', Image.BICUBIC)

        enhanced_img = img.resize((new_width, new_height), resample=resample_filter)

        if enhanced_img.mode not in ['RGB', 'RGBA']:
            enhanced_img = enhanced_img.convert('RGB')

        # 1. Unsharp Mask Filter
        enhanced_img = enhanced_img.filter(
            ImageFilter.UnsharpMask(radius=unsharp_radius, percent=unsharp_percent, threshold=3)
        )

        # 2. Sharpness Enhancement
        sharpness_enhancer = ImageEnhance.Sharpness(enhanced_img)
        enhanced_img = sharpness_enhancer.enhance(sharpness_val)

        # 3. Contrast Enhancement
        contrast_enhancer = ImageEnhance.Contrast(enhanced_img)
        enhanced_img = contrast_enhancer.enhance(contrast_val)

        # 4. Color Vibrance Enhancement
        color_enhancer = ImageEnhance.Color(enhanced_img)
        enhanced_img = color_enhancer.enhance(color_val)

        # Output to memory buffer
        output_buffer = io.BytesIO()
        enhanced_img.save(output_buffer, format='PNG', quality=95)
        output_buffer.seek(0)

        encoded_b64 = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
        data_url = f"data:image/png;base64,{encoded_b64}"

        return JsonResponse({
            'success': True,
            'quality': quality,
            'quality_label': quality_label,
            'original_dimensions': f"{orig_width} x {orig_height}",
            'enhanced_dimensions': f"{new_width} x {new_height}",
            'image_data_url': data_url,
        })

    except Exception as e:
        return JsonResponse({'error': f'Image processing error: {str(e)[:120]}'}, status=500)


def fetch_multiple_moviebox_results(query: str, limit=8):
    """Searches MovieBox and stream sources, returning multiple movie result cards."""
    clean_query = query.strip()
    if not clean_query:
        return []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    movies_list = []

    # 1. Scrape MovieBox search page HTML for matching movie links
    try:
        search_url = f"https://moviebox.ph/search?keyword={requests.utils.quote(clean_query)}"
        r = requests.get(search_url, headers=headers, timeout=8)
        if r.status_code == 200:
            html = r.text
            matches = re.findall(r'<a[^>]+href="([^"]*/movie/[^"]+)"[^>]*>(.*?)</a>', html, re.S)
            seen_urls = set()
            for m_url, m_text in matches:
                if not m_url.startswith('http'):
                    full_m_url = f"https://moviebox.ph{m_url}"
                else:
                    full_m_url = m_url
                if full_m_url in seen_urls:
                    continue
                seen_urls.add(full_m_url)

                clean_t = re.sub(r'<[^>]+>', '', m_text).strip()
                if not clean_t:
                    clean_t = clean_query.title()

                movies_list.append({
                    'id': str(uuid.uuid4())[:8],
                    'title': clean_t,
                    'platform': 'MovieBox',
                    'url': full_m_url,
                    'duration': 'Full Movie',
                    'views': 'HD Quality Stream',
                    'video_qualities': ["480p", "720p", "1080p", "2160p"],
                    'mp3_qualities': MP3_QUALITIES,
                    'thumbnail_url': static('media/sample-thumb.jpg'),
                    'preview_url': None,
                })
                if len(movies_list) >= limit:
                    break
    except Exception:
        pass

    # 2. Extract results via yt_dlp multi-search for full feature movie streams
    ffmpeg_path = get_ffmpeg_path()
    search_term = f"ytsearch{limit}:{clean_query} full movie"
    ydl_opts = get_base_ydl_opts()
    ydl_opts.update({
        'extract_flat': False,
        'http_headers': headers,
    })
    if ffmpeg_path:
        ydl_opts['ffmpeg_location'] = ffmpeg_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_term, download=False)
            if info and 'entries' in info and info['entries']:
                for entry in info['entries']:
                    if not entry:
                        continue
                    m_title = entry.get('title') or clean_query.title()
                    dur = entry.get('duration')
                    duration_str = format_duration(dur) if dur else "Full Movie"
                    thumb_url = entry.get('thumbnail')

                    preview_url = None
                    formats = entry.get('formats', [])
                    for f in reversed(formats):
                        f_url = f.get('url')
                        if f_url and f.get('vcodec') != 'none':
                            preview_url = f_url
                            break
                    if not preview_url:
                        preview_url = entry.get('url') or entry.get('webpage_url')

                    web_url = entry.get('webpage_url') or entry.get('url') or search_term

                    if not any(m['title'].lower() == m_title.lower() for m in movies_list):
                        movies_list.append({
                            'id': str(uuid.uuid4())[:8],
                            'title': m_title,
                            'platform': 'MovieBox',
                            'url': web_url,
                            'duration': duration_str,
                            'views': format_views(entry.get('view_count')) or 'HD Stream',
                            'video_qualities': ["480p", "720p", "1080p", "2160p"],
                            'mp3_qualities': MP3_QUALITIES,
                            'thumbnail_url': thumb_url or static('media/sample-thumb.jpg'),
                            'preview_url': preview_url,
                        })
                    if len(movies_list) >= limit:
                        break
    except Exception:
        pass

    if not movies_list:
        movies_list.append({
            'id': str(uuid.uuid4())[:8],
            'title': f"{clean_query.title()} — MovieBox Edition",
            'platform': 'MovieBox',
            'url': f"https://moviebox.ph/search?keyword={requests.utils.quote(clean_query)}",
            'duration': 'Full Movie',
            'views': 'HD Quality Stream',
            'video_qualities': ["480p", "720p", "1080p", "2160p"],
            'mp3_qualities': MP3_QUALITIES,
            'thumbnail_url': static('media/sample-thumb.jpg'),
            'preview_url': None,
        })

    return movies_list[:limit]


@csrf_exempt
def api_search_movies(request):
    """Returns a list of MovieBox movie result cards for a search query."""
    if request.method not in ['GET', 'POST']:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            query = data.get('q', '')
        except Exception:
            query = request.POST.get('q', '')
    else:
        query = request.GET.get('q', '')

    query = query.strip()
    if not query:
        query = "Action Blockbuster"

    results = fetch_multiple_moviebox_results(query, limit=8)
    return JsonResponse({'success': True, 'query': query, 'movies': results})


def movies(request):
    """Renders the Movies page with a classic light-blue glass background."""
    return render(request, 'movies.html')



@csrf_exempt
def api_fetch(request):
    """Fetches real metadata for a video URL using yt-dlp or MovieBox parser."""
    if request.method not in ['POST', 'GET']:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            url = data.get('url', '')
        except Exception:
            url = request.POST.get('url', '')
    else:
        url = request.GET.get('url', '')

    url = url.strip()
    if not url:
        return JsonResponse({'error': 'Please provide a valid link.'}, status=400)

    platform = detect_platform(url)
    if not platform:
        return JsonResponse({
            'error': "That link isn't supported yet — paste a YouTube, Instagram, TikTok, or MovieBox URL."
        }, status=400)

    # Handle MovieBox platform separately
    if platform == 'MovieBox':
        try:
            mb_meta = fetch_moviebox_metadata(url)
            if not mb_meta.get('direct_url'):
                return JsonResponse({'error': 'Could not locate video stream on that MovieBox link.'}, status=400)

            return JsonResponse({
                'success': True,
                'platform': 'MovieBox',
                'url': url,
                'title': mb_meta['title'],
                'channel': mb_meta['channel'],
                'duration': mb_meta['duration'],
                'views': mb_meta['views'],
                'video_qualities': ["480p", "720p", "1080p"],
                'mp3_qualities': MP3_QUALITIES,
                'thumbnail_url': mb_meta['thumbnail_url'] or static('media/sample-thumb.jpg'),
                'preview_url': mb_meta['preview_url'],
            })
        except Exception as e:
            return JsonResponse({'error': f'Could not fetch MovieBox content: {str(e)[:120]}'}, status=400)

    # Handle YouTube, Instagram, TikTok via yt-dlp
    ydl_opts = get_base_ydl_opts()
    ydl_opts.update({
        'skip_download': True,
        'extract_flat': False,
    })
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path:
        ydl_opts['ffmpeg_location'] = ffmpeg_path

    info = None
    last_exception = None

    # Multi-client fallback chain to defeat YouTube PO Token / Bot Challenge
    client_configs = [
        ['tv', 'mweb'],
        ['ios', 'android'],
        ['web_creator', 'android_creator'],
        ['mweb'],
    ]

    for clients in client_configs:
        ydl_opts['extractor_args'] = {
            'youtube': {
                'player_client': clients,
                'player_skip': ['webpage', 'configs'],
            }
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    break
        except Exception as e:
            last_exception = e

    if not info and last_exception:
        err_msg = str(last_exception)
        if "is not a valid URL" in err_msg or "Unsupported URL" in err_msg:
            return JsonResponse({'error': 'Invalid link provided.'}, status=400)
        return JsonResponse({'error': f'Could not fetch video info: {err_msg[:120]}'}, status=400)

    if not info:
        return JsonResponse({'error': 'Failed to retrieve video details.'}, status=400)

    if 'entries' in info and info['entries']:
        info = info['entries'][0]

    title = info.get('title') or info.get('description') or 'Untitled Video'
    if len(title) > 120:
        title = title[:117] + '...'

    channel = (
        info.get('uploader') or
        info.get('channel') or
        info.get('uploader_id') or
        info.get('creator') or
        '@creator'
    )
    if channel and not channel.startswith('@') and platform in ['Instagram', 'TikTok']:
        channel = f"@{channel}"

    duration = format_duration(info.get('duration'))
    views = format_views(info.get('view_count'))
    thumbnail_url = info.get('thumbnail')

    # Extract direct MP4 stream URL for in-browser video preview
    preview_url = None
    formats = info.get('formats', [])
    for f in formats:
        if f.get('vcodec') != 'none' and f.get('url') and f.get('ext') == 'mp4':
            preview_url = f.get('url')
            if f.get('format_id') in ['18', '22']:
                break
    if not preview_url:
        preview_url = info.get('url')

    max_height = 0
    for f in formats:
        h = f.get('height')
        if h and isinstance(h, int) and h > max_height:
            max_height = h

    if max_height == 0:
        max_height = info.get('height') or 1080

    video_qualities = []
    for q in ALL_VIDEO_QUALITIES:
        height_val = int(q.replace('p', ''))
        if height_val <= max_height or not video_qualities:
            video_qualities.append(q)

    if not video_qualities:
        video_qualities = ALL_VIDEO_QUALITIES[:5]

    return JsonResponse({
        'success': True,
        'platform': platform,
        'url': url,
        'title': title,
        'channel': channel,
        'duration': duration,
        'views': views,
        'video_qualities': video_qualities,
        'mp3_qualities': MP3_QUALITIES,
        'thumbnail_url': thumbnail_url or static('media/sample-thumb.jpg'),
        'preview_url': preview_url,
    })


PROGRESS_TASKS = {}
TASKS_LOCK = threading.Lock()


def cleanup_old_tasks():
    """Removes stale download tasks older than 1 hour to prevent memory/disk bloat."""
    now = time.time()
    with TASKS_LOCK:
        to_delete = []
        for task_id, task in PROGRESS_TASKS.items():
            if now - task.get('created_at', now) > 3600:
                to_delete.append(task_id)
                file_path = task.get('file_path')
                temp_dir = task.get('temp_dir')
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                if temp_dir and os.path.exists(temp_dir):
                    try:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    except Exception:
                        pass
        for tid in to_delete:
            del PROGRESS_TASKS[tid]


def run_download_task(task_id, download_data):
    """Worker thread running yt-dlp download with real-time byte progress hooks."""
    url = download_data['url']
    platform = download_data['platform']
    format_type = download_data['format_type']
    quality = download_data['quality']
    title = download_data['title']

    temp_dir = tempfile.mkdtemp(prefix='snapgrab_')
    out_template = os.path.join(temp_dir, 'downloaded_media.%(ext)s')
    ffmpeg_path = get_ffmpeg_path()

    if platform == 'MovieBox' or 'moviebox' in url.lower() or 'movie-box' in url.lower():
        try:
            mb_meta = fetch_moviebox_metadata(url)
            download_target = mb_meta.get('direct_url') or url
        except Exception:
            download_target = url
    else:
        download_target = url

    browser_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': url,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    def progress_hook(d):
        status = d.get('status')
        with TASKS_LOCK:
            if task_id not in PROGRESS_TASKS:
                return
            if status == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                if total > 0:
                    percent = min(99.0, round((downloaded / total) * 100, 1))
                else:
                    percent = 0.0
                PROGRESS_TASKS[task_id].update({
                    'status': 'downloading',
                    'downloaded_bytes': downloaded,
                    'total_bytes': total,
                    'percent': percent,
                    'speed': d.get('speed', 0),
                    'eta': d.get('eta', 0),
                })
            elif status == 'finished':
                PROGRESS_TASKS[task_id].update({
                    'status': 'processing',
                    'percent': 99.0,
                })

    if format_type == 'mp3':
        preferred_kbps = '320'
        m = re.search(r'\d+', quality)
        if m:
            preferred_kbps = m.group(0)

        ydl_opts = get_base_ydl_opts()
        ydl_opts.update({
            'format': 'bestaudio/best',
            'outtmpl': out_template,
            'http_headers': browser_headers,
            'retries': 10,
            'fragment_retries': 10,
            'progress_hooks': [progress_hook],
        })
        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': preferred_kbps,
            }]
    else:
        target_height = 1080
        m = re.search(r'\d+', quality)
        if m:
            target_height = int(m.group(0))

        if ffmpeg_path:
            ydl_opts = get_base_ydl_opts()
            ydl_opts.update({
                'format': f'bestvideo[height<={target_height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={target_height}]+bestaudio/best[height<={target_height}]/best',
                'merge_output_format': 'mp4',
                'outtmpl': out_template,
                'ffmpeg_location': ffmpeg_path,
                'http_headers': browser_headers,
                'retries': 10,
                'fragment_retries': 10,
                'hls_use_mpegts': True,
                'progress_hooks': [progress_hook],
            })
        else:
            ydl_opts = get_base_ydl_opts()
            ydl_opts.update({
                'format': f'best[height<={target_height}][ext=mp4]/best[ext=mp4]/best',
                'outtmpl': out_template,
                'http_headers': browser_headers,
                'retries': 10,
                'fragment_retries': 10,
                'progress_hooks': [progress_hook],
            })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([download_target])
    except Exception as e:
        if download_target != url:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e2:
                with TASKS_LOCK:
                    if task_id in PROGRESS_TASKS:
                        PROGRESS_TASKS[task_id].update({
                            'status': 'error',
                            'error': f'Download failed: {str(e2)[:120]}'
                        })
                shutil.rmtree(temp_dir, ignore_errors=True)
                return
        else:
            with TASKS_LOCK:
                if task_id in PROGRESS_TASKS:
                    PROGRESS_TASKS[task_id].update({
                        'status': 'error',
                        'error': f'Download failed: {str(e)[:120]}'
                    })
            shutil.rmtree(temp_dir, ignore_errors=True)
            return

    all_files = glob.glob(os.path.join(temp_dir, '*'))
    completed_files = [f for f in all_files if not f.endswith(('.part', '.ytdl', '.temp', '.jpg', '.png', '.webp', '.json'))]
    if not completed_files:
        completed_files = all_files

    if not completed_files:
        with TASKS_LOCK:
            if task_id in PROGRESS_TASKS:
                PROGRESS_TASKS[task_id].update({
                    'status': 'error',
                    'error': 'File download completed but output file not found.'
                })
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    file_path = max(completed_files, key=os.path.getsize)
    filename = os.path.basename(file_path)

    clean_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_') or 'SnapGrab_Media'
    ext = os.path.splitext(filename)[1] or ('.mp3' if format_type == 'mp3' else '.mp4')
    download_filename = f"{clean_title}_{quality.replace(' ', '')}{ext}"
    file_size = os.path.getsize(file_path)

    with TASKS_LOCK:
        if task_id in PROGRESS_TASKS:
            PROGRESS_TASKS[task_id].update({
                'status': 'completed',
                'percent': 100.0,
                'downloaded_bytes': file_size,
                'total_bytes': file_size,
                'file_path': file_path,
                'temp_dir': temp_dir,
                'download_filename': download_filename,
                'format_type': format_type,
            })


@csrf_exempt
def api_start_download(request):
    """Starts asynchronous media download and returns task_id for real-time progress polling."""
    if request.method not in ['POST', 'GET']:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    cleanup_old_tasks()

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST
    else:
        data = request.GET

    url = data.get('url', '').strip()
    platform = data.get('platform', 'YouTube')
    format_type = data.get('format', 'video')
    quality = data.get('quality', '1080p')
    title = data.get('title', 'video')

    if not url:
        return JsonResponse({'error': 'Invalid URL'}, status=400)

    DownloadLog.objects.create(
        url=url,
        platform=platform if platform in ['YouTube', 'Instagram', 'TikTok', 'MovieBox'] else 'YouTube',
        format_type=format_type if format_type in ['video', 'mp3'] else 'video',
        quality=quality,
        title=title[:250],
    )

    task_id = str(uuid.uuid4())
    task_info = {
        'status': 'starting',
        'downloaded_bytes': 0,
        'total_bytes': 0,
        'percent': 0.0,
        'speed': 0,
        'eta': 0,
        'file_path': None,
        'temp_dir': None,
        'download_filename': None,
        'error': None,
        'created_at': time.time(),
    }

    with TASKS_LOCK:
        PROGRESS_TASKS[task_id] = task_info

    download_data = {
        'url': url,
        'platform': platform,
        'format_type': format_type,
        'quality': quality,
        'title': title,
    }

    thread = threading.Thread(target=run_download_task, args=(task_id, download_data), daemon=True)
    thread.start()

    return JsonResponse({'success': True, 'task_id': task_id})


def api_progress(request, task_id):
    """Returns real-time progress data for a download task."""
    cleanup_old_tasks()
    with TASKS_LOCK:
        task = PROGRESS_TASKS.get(task_id)

    if not task:
        return JsonResponse({'error': 'Task not found'}, status=404)

    return JsonResponse({
        'success': True,
        'status': task['status'],
        'downloaded_bytes': task['downloaded_bytes'],
        'total_bytes': task['total_bytes'],
        'percent': task['percent'],
        'speed': task.get('speed', 0),
        'eta': task.get('eta', 0),
        'error': task.get('error'),
    })


def api_get_file(request, task_id):
    """Serves the completed media file to the user."""
    cleanup_old_tasks()
    with TASKS_LOCK:
        task = PROGRESS_TASKS.get(task_id)

    if not task or task['status'] != 'completed' or not task.get('file_path'):
        return JsonResponse({'error': 'File not ready or expired.'}, status=400)

    file_path = task['file_path']
    temp_dir = task.get('temp_dir')
    download_filename = task.get('download_filename', 'SnapGrab_Media.mp4')
    format_type = task.get('format_type', 'video')

    if not os.path.exists(file_path):
        return JsonResponse({'error': 'File missing from server.'}, status=404)

    content_type = 'audio/mpeg' if format_type == 'mp3' or download_filename.endswith('.mp3') else 'video/mp4'
    file_size = os.path.getsize(file_path)

    file_obj = open(file_path, 'rb')
    old_close = file_obj.close

    def cleanup_close():
        old_close()
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            with TASKS_LOCK:
                if task_id in PROGRESS_TASKS:
                    del PROGRESS_TASKS[task_id]
        except Exception:
            pass

    file_obj.close = cleanup_close

    response = FileResponse(
        file_obj,
        content_type=content_type,
        as_attachment=True,
        filename=download_filename
    )
    response['Content-Length'] = str(file_size)
    return response



@csrf_exempt
def api_download(request):
    """Downloads real media using yt-dlp / MovieBox stream handler and serves it to user."""
    if request.method not in ['POST', 'GET']:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST
        url = data.get('url', '')
        platform = data.get('platform', 'YouTube')
        format_type = data.get('format', 'video')
        quality = data.get('quality', '1080p')
        title = data.get('title', 'video')
    else:
        url = request.GET.get('url', '')
        platform = request.GET.get('platform', 'YouTube')
        format_type = request.GET.get('format', 'video')
        quality = request.GET.get('quality', '1080p')
        title = request.GET.get('title', 'video')

    url = url.strip()
    if not url:
        return JsonResponse({'error': 'Invalid URL'}, status=400)

    # Log entry into database
    DownloadLog.objects.create(
        url=url,
        platform=platform if platform in ['YouTube', 'Instagram', 'TikTok', 'MovieBox'] else 'YouTube',
        format_type=format_type if format_type in ['video', 'mp3'] else 'video',
        quality=quality,
        title=title[:250],
    )

    temp_dir = tempfile.mkdtemp(prefix='snapgrab_')
    ffmpeg_path = get_ffmpeg_path()

    # Determine target download URL (for MovieBox, resolve direct stream URL first)
    if platform == 'MovieBox' or 'moviebox' in url.lower() or 'movie-box' in url.lower():
        try:
            mb_meta = fetch_moviebox_metadata(url)
            download_target = mb_meta.get('direct_url') or url
        except Exception:
            download_target = url
    else:
        download_target = url

    out_template = os.path.join(temp_dir, 'downloaded_media.%(ext)s')

    browser_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': url,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    if format_type == 'mp3':
        preferred_kbps = '320'
        m = re.search(r'\d+', quality)
        if m:
            preferred_kbps = m.group(0)

        ydl_opts = get_base_ydl_opts()
        ydl_opts.update({
            'format': 'bestaudio/best',
            'outtmpl': out_template,
            'http_headers': browser_headers,
            'retries': 10,
            'fragment_retries': 10,
        })
        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': preferred_kbps,
            }]
    else:
        target_height = 1080
        m = re.search(r'\d+', quality)
        if m:
            target_height = int(m.group(0))

        if ffmpeg_path:
            ydl_opts = get_base_ydl_opts()
            ydl_opts.update({
                'format': f'bestvideo[height<={target_height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={target_height}]+bestaudio/best[height<={target_height}]/best',
                'merge_output_format': 'mp4',
                'outtmpl': out_template,
                'ffmpeg_location': ffmpeg_path,
                'http_headers': browser_headers,
                'retries': 10,
                'fragment_retries': 10,
                'hls_use_mpegts': True,
            })
        else:
            ydl_opts = get_base_ydl_opts()
            ydl_opts.update({
                'format': f'best[height<={target_height}][ext=mp4]/best[ext=mp4]/best',
                'outtmpl': out_template,
                'http_headers': browser_headers,
                'retries': 10,
                'fragment_retries': 10,
            })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([download_target])
    except Exception as e:
        if download_target != url:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e2:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return JsonResponse({'error': f'Download failed: {str(e2)[:120]}'}, status=500)
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return JsonResponse({'error': f'Download failed: {str(e)[:120]}'}, status=500)

    # Filter out intermediate / partial download files
    all_files = glob.glob(os.path.join(temp_dir, '*'))
    completed_files = [f for f in all_files if not f.endswith(('.part', '.ytdl', '.temp', '.jpg', '.png', '.webp', '.json'))]
    if not completed_files:
        completed_files = all_files

    if not completed_files:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return JsonResponse({'error': 'File download completed but output file not found.'}, status=500)

    file_path = max(completed_files, key=os.path.getsize)
    filename = os.path.basename(file_path)

    # Clean title for file naming
    clean_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_') or 'SnapGrab_Media'
    ext = os.path.splitext(filename)[1] or ('.mp3' if format_type == 'mp3' else '.mp4')
    download_filename = f"{clean_title}_{quality.replace(' ', '')}{ext}"

    content_type = 'audio/mpeg' if format_type == 'mp3' or ext == '.mp3' else 'video/mp4'

    file_size = os.path.getsize(file_path)

    file_obj = open(file_path, 'rb')
    old_close = file_obj.close

    def cleanup_close():
        old_close()
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    file_obj.close = cleanup_close

    response = FileResponse(
        file_obj,
        content_type=content_type,
        as_attachment=True,
        filename=download_filename
    )
    response['Content-Length'] = str(file_size)
    return response
