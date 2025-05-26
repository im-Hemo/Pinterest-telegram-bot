import os
import re
import requests
import threading
import signal
#imoort Hemo
from pathlib import Path
from typing import List
from telebot import TeleBot as xgv
from telebot.types import Message
from telebot import types
from concurrent.futures import ThreadPoolExecutor
import yt_dlp
import logging
from fake_useragent import UserAgent

token = 'bot token'
logging.getLogger('xgv').setLevel(logging.CRITICAL)

# made with  ♡゙ by @x_g_v
class PinterestDownloader:
    def __init__(self, bot: 'xgv'):
        self.bot = bot
        self.ua = UserAgent()
        self.pin_dir = Path('Pin')
        self.pin_dir.mkdir(exist_ok=True)
        self.bot.message_handler(commands=['start'])(self.start_CMD)
        self.bot.message_handler(content_types=['text'])(self.message_mng)        
        self.executor = ThreadPoolExecutor(max_workers=5)

    def start_CMD(self, message: Message):
        markup = types.InlineKeyboardMarkup()
        x1 = types.InlineKeyboardButton("‹ Me ›", url="https://t.me/x_g_v")
        x2 = types.InlineKeyboardButton("‹ Ch ›", url="https://t.me/lmmm5")
        markup.add(x1, x2)

        mention = f'<a href="https://t.me/{message.from_user.username}">{message.from_user.first_name}</a>'

        caption = (
            f"• مرحباً بك، {mention}! 👋\n"
            "• أنا بوت تحميل من <b>Pinterest</b> 🎨\n\n"
            "<blockquote> دز رابط صورة او فيديو بنترست وراح احمله لك 😁</blockquote>"
        )

        pic_url = "https://i.ibb.co/0yzZHrjc/image.jpg"
        self.bot.send_photo(
            chat_id=message.chat.id,
            photo=pic_url,
            caption=caption,
            parse_mode="HTML",
            has_spoiler=True,
            reply_markup=markup
        )


    def _resolve_url(self, url: str) -> str:
        try:
            resp = requests.get(url, headers={'User-Agent': self.ua.random}, allow_redirects=True, timeout=10)
            resp.raise_for_status()
            return resp.url
        except Exception:
            return url

    def _extract_pin_id(self, url: str) -> str:
        patterns = [
            r"pinterest\.com/pin/(\d+)",
            r"pin\.it/(\w+)"
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _fetch_pin_metadata(self, pin_id: str) -> dict:
        api_url = "https://www.pinterest.com/resource/PinResource/get/"
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": self.ua.random,
            "X-Pinterest-PWS-Handler": f"www/pin/{pin_id}/feedback.js"
        }
        params = {
            "source_url": f"/pin/{pin_id}",
            "data": f'{{"options":{{"id":"{pin_id}","field_set_key":"auth_web_main_pin"}}}}'
        }
        resp = requests.get(api_url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get('resource_response', {}).get('data', {})

    def _extract_media(self, pin_data: dict) -> dict:
        media_info = {'type': None, 'resources': [], 'signature': pin_data.get('id') or str(hash(str(pin_data)))}
        if pin_data.get('videos'):
            video_versions = pin_data['videos'].get('video_list', {})
            for quality in ['V_EXP7', 'V_720P', 'V_480P']:
                if video_versions.get(quality):
                    media_info.update({'type': 'video', 'resources': [video_versions[quality]['url']]})
                    return media_info
        if pin_data.get('carousel_data'):
            slots = pin_data['carousel_data'].get('carousel_slots', [])
            urls = []
            for item in slots:
                img = item.get('images', {}).get('orig', {}).get('url')
                if img:
                    urls.append(img)
            if urls:
                media_info.update({'type': 'carousel', 'resources': urls})
                return media_info
        img = pin_data.get('images', {}).get('orig', {}).get('url')
        if img:
            media_info.update({'type': 'image', 'resources': [img]})
            return media_info
        raise ValueError("Unsupported pin content type")

    def _download_resource(self, url: str, file_path: Path):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if url.endswith('.m3u8'):
            opts = {'outtmpl': str(file_path)}
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        else:
            r = requests.get(url, stream=True, timeout=10)
            r.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)

    def _send_results(self, chat_id: int, files: List[Path], media_type: str):
        bot_info = self.bot.get_me()
        username = bot_info.username
        caption = f"• تـم التحميل ☑️ | بواسطة @{username}"
        
        for fpath in files:
            with open(fpath, 'rb') as f:
                if media_type == 'video':
                    self.bot.send_video(chat_id, f, caption=caption)
                else:
                    self.bot.send_photo(chat_id, f, caption=caption)
        for fpath in files:
            try:
                fpath.unlink()
            except:
                pass
                
                                

    def process_pin(self, url: str, chat_id: int):
        resolved = self._resolve_url(url)
        pin_id = self._extract_pin_id(resolved)
        if not pin_id:
            self.bot.send_message(chat_id, "• رابـط غلط حب !")
            return
        msg = self.bot.send_message(chat_id, "⏳ جاري فحص الرابط...")
        try:
            pin_data = self._fetch_pin_metadata(pin_id)
            media_info = self._extract_media(pin_data)
            self.bot.edit_message_text("📥 جاري التحميل...", chat_id, msg.message_id)
            download_dir = self.pin_dir / media_info['signature']
            download_dir.mkdir(exist_ok=True)
            files = []
            for idx, res in enumerate(media_info['resources']):
                ext = 'mp4' if media_info['type']=='video' else 'jpg'
                name = f"{idx}.{ext}" if media_info['type']=='carousel' else f"content.{ext}"
                path = download_dir / name
                self._download_resource(res, path)
                files.append(path)
            self._send_results(chat_id, files, media_info['type'])
            self.bot.delete_message(chat_id, msg.message_id)
        except Exception as e:
            self.bot.send_message(chat_id, f"• اووبـس, حصل خطا \n `{e}`")

    def message_mng(self, message: Message):
        url = message.text.strip()
        if re.search(r"pinterest\.com|pin\.it", url):
            threading.Thread(target=self.process_pin, args=(url, message.chat.id)).start()


# © All rights reserved | by @x_g_v 

def Hemo_run(token: str) -> xgv:
    Hemo = xgv(token)
    PinterestDownloader(Hemo)
    return Hemo

def __del__(self):
    self.executor.shutdown(wait=True)
    
if __name__ == '__main__':
    Hemo = Hemo_run(token)
    
    def signal_Core(sig, frame):
        Hemo.stop_polling()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_Core)
    
    try:
        Hemo.infinity_polling()
    except Exception:
        Hemo.stop_polling()