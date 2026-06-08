import asyncio
import feedparser
from telegram import Bot
from telegram.error import TelegramError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import time
from datetime import datetime, timedelta, timezone
import logging
import pytz
import re
import urllib.request
import urllib.error
import io
import json

# --- تنظیمات ---
BOT_TOKEN = "8541579071:AAEN4cGyQUdAX1E5IRF4m7oa7M5TiQ1hn1Q"
CHANNEL_ID = "@news_iran_1405"
VPN_LINK = "https://t.me/Reyhan_vpn"

# لیست فیدهای RSS (فقط منابع فعال)
RSS_FEEDS = {
    "radio_farda": "https://www.radiofarda.com/api/zk_rss",
    "bbc": "https://www.bbc.com/persian/index.xml",
    "israel_hayom": "https://www.israelhayom.co.il/rss",
    "ynet": "https://www.ynetnews.com/Integration/StoryRss1862.xml",
    "times_of_israel": "https://www.timesofisrael.com/feed/",
}

# کلمات کلیدی جنگ
WAR_KEYWORDS = [
    'جنگ', 'حمله', 'موشک', 'انفجار', 'ارتش', 'نظامی', 'سپاه', 'شلیک',
    'درگیری', 'تهاجم', 'دفاع', 'جنگنده', 'پهپاد', 'تانک', 'عملیات', 'ترور',
    'اسرائیل', 'آمریکا', 'ایران', 'نتانیاهو', 'بایدن', 'خامنه‌ای', 'سلیمانی',
    'هسته‌ای', 'نطنز', 'تحریم', 'war', 'attack', 'missile', 'explosion',
    'شهید', 'قدس', 'حزب الله', 'hezbollah', 'hamas', 'غزه', 'تهران'
]

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def escape_markdown(text):
    """ایمن کردن متن برای مارکداون تلگرام"""
    if not text:
        return ""
    # کاراکترهای خاص مارکداون رو escape کن
    special_chars = r'_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, '\\' + char)
    return text

def get_crypto_prices():
    try:
        prices = {}
        coins = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum', 
            'USDT': 'tether',
            'BNB': 'binancecoin',
            'SOL': 'solana',
            'XRP': 'ripple',
        }
        
        for symbol, coin_id in coins.items():
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                if coin_id in data:
                    price = data[coin_id].get('usd', 0)
                    change = data[coin_id].get('usd_24h_change', 0)
                    prices[symbol] = {'price': price, 'change': change}
            time.sleep(0.3)
        return prices
    except Exception as e:
        logger.error(f"Crypto error: {e}")
        return None

def get_forex_rates():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            rates = data.get('rates', {})
            important = ['EUR', 'GBP', 'JPY', 'CAD', 'CHF', 'CNY', 'TRY', 'AED', 'INR', 'RUB']
            return {k: rates.get(k, 0) for k in important if k in rates}
    except Exception as e:
        logger.error(f"Forex error: {e}")
        return None

def get_iran_rates():
    try:
        url = "https://raw.githubusercontent.com/HosseinOdd/Navasan-API/main/data/fiat.json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            return {
                'usd': data.get('USD', {}).get('value', 'نامشخص'),
                'eur': data.get('EUR', {}).get('value', 'نامشخص'),
            }
    except Exception as e:
        logger.error(f"Iran rates error: {e}")
        return None

def get_gold_prices():
    try:
        url = "https://raw.githubusercontent.com/HosseinOdd/Navasan-API/main/data/gold.json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            return {
                'gold_18': data.get('18', {}).get('value', 'نامشخص'),
                'emami_coin': data.get('emami', {}).get('value', 'نامشخص'),
            }
    except Exception as e:
        logger.error(f"Gold error: {e}")
        return None

def format_market_report():
    report = "📊 *گزارش لحظه‌ای بازار*\n\n"
    
    crypto = get_crypto_prices()
    if crypto:
        report += "*💎 ارزهای دیجیتال:*\n"
        for symbol, data in crypto.items():
            if data['price'] > 0:
                emoji = "🟢" if data['change'] >= 0 else "🔴"
                report += f"  {symbol}: ${data['price']:,.0f} {emoji} ({data['change']:+.1f}%)\n"
        report += "\n"
    
    forex = get_forex_rates()
    if forex:
        report += "*🌍 ارزهای جهانی (به USD):*\n"
        for curr, rate in forex.items():
            if rate > 0:
                report += f"  {curr}: {rate:.2f}\n"
        report += "\n"
    
    iran = get_iran_rates()
    if iran:
        report += "*🇮🇷 بازار ایران:*\n"
        report += f"  دلار آمریکا: {iran['usd']} تومان\n"
        report += f"  یورو: {iran['eur']} تومان\n"
    
    gold = get_gold_prices()
    if gold:
        report += f"  طلای ۱۸ عیار: {gold['gold_18']} تومان\n"
        report += f"  سکه امامی: {gold['emami_coin']} تومان\n"
    
    return report

class WarNewsBot:
    def __init__(self, token, channel_id):
        self.bot = Bot(token=token)
        self.channel_id = channel_id
        self.seen_links = set()
        self.tehran_tz = pytz.timezone('Asia/Tehran')
        self.last_market_time = 0
        self.load_seen_links()
    
    def load_seen_links(self):
        try:
            with open("seen_links.txt", "r") as f:
                self.seen_links = set(line.strip() for line in f)
            logger.info(f"Loaded {len(self.seen_links)} seen links")
        except FileNotFoundError:
            logger.info("No existing seen links file")
    
    def save_seen_links(self):
        with open("seen_links.txt", "w") as f:
            for link in self.seen_links:
                f.write(f"{link}\n")
    
    def parse_date(self, date_string):
        if not date_string:
            return None
        
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',
            '%a, %d %b %Y %H:%M:%S %Z',
            '%d %b %Y %H:%M:%S %z',
            '%Y-%m-%dT%H:%M:%S%z',
        ]
        
        for fmt in formats:
            try:
                cleaned = date_string.replace('GMT', '+0000')
                dt = datetime.strptime(cleaned, fmt)
                return dt
            except:
                continue
        
        return None
    
    def is_today_tomorrow_yesterday(self, news_date):
        if news_date is None:
            return False
        
        if news_date.tzinfo is None:
            news_date = news_date.replace(tzinfo=timezone.utc)
        
        tehran_time = news_date.astimezone(self.tehran_tz)
        tehran_now = datetime.now(self.tehran_tz)
        
        today = tehran_now.date()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        
        news_date_only = tehran_time.date()
        
        if news_date_only in [today, yesterday, tomorrow]:
            return True
        return False
    
    def get_persian_date(self, dt):
        if dt is None:
            return "تاریخ نامشخص"
        
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        tehran_time = dt.astimezone(self.tehran_tz)
        tehran_now = datetime.now(self.tehran_tz)
        diff_days = (tehran_time.date() - tehran_now.date()).days
        
        if diff_days == 0:
            return "امروز"
        elif diff_days == -1:
            return "دیروز"
        elif diff_days == 1:
            return "فردا"
        else:
            return tehran_time.strftime("%Y/%m/%d")
    
    def extract_image_url(self, entry):
        if 'media_content' in entry:
            for media in entry.media_content:
                if media.get('medium') == 'image' or media.get('type', '').startswith('image'):
                    return media.get('url')
        
        if 'enclosures' in entry:
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image'):
                    return enc.get('href')
        
        if 'summary' in entry:
            img_pattern = r'<img[^>]+src="([^">]+)"'
            match = re.search(img_pattern, entry.summary)
            if match:
                return match.group(1)
        
        if 'description' in entry:
            img_pattern = r'<img[^>]+src="([^">]+)"'
            match = re.search(img_pattern, entry.description)
            if match:
                return match.group(1)
        
        return None
    
    def clean_text(self, text):
        if not text:
            return ""
        clean = re.sub(r'<[^>]+>', '', text)
        clean = re.sub(r'http\S+', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean
    
    def is_war_news(self, text):
        if not text:
            return False
        text_lower = text.lower()
        
        countries = ['ایران', 'iran', 'آمریکا', 'america', 'usa', 'اسرائیل', 'israel', 'تهران', 'تل آویو']
        has_country = any(c in text_lower for c in countries)
        
        if not has_country:
            return False
        
        return any(k.lower() in text_lower for k in WAR_KEYWORDS)
    
    def download_image(self, url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                image_data = response.read()
                return io.BytesIO(image_data)
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None
    
    def fetch_news(self, source_name, feed_url):
        try:
            feed = feedparser.parse(feed_url)
            news_items = []
            
            for entry in feed.entries[:25]:
                link = entry.get('link', '')
                if link in self.seen_links:
                    continue
                
                pub_date = entry.get('published', entry.get('pubDate', ''))
                parsed_date = self.parse_date(pub_date)
                
                if not self.is_today_tomorrow_yesterday(parsed_date):
                    continue
                
                title = entry.get('title', '')
                description = entry.get('description', entry.get('summary', ''))
                
                clean_title = self.clean_text(title)
                clean_description = self.clean_text(description)
                
                full_text = clean_title
                if clean_description and clean_description != clean_title:
                    full_text += "\n\n" + clean_description[:500]
                
                if not full_text:
                    full_text = clean_title
                
                # فیلتر اخبار جنگ
                if not self.is_war_news(full_text):
                    continue
                
                image_url = self.extract_image_url(entry)
                
                news_items.append({
                    'source': source_name,
                    'text': full_text[:1500],  # محدود کردن طول
                    'link': link,
                    'image_url': image_url,
                    'parsed_date': parsed_date,
                    'date_label': self.get_persian_date(parsed_date)
                })
            
            return news_items
        except Exception as e:
            logger.error(f"Error fetching {source_name}: {e}")
            return []
    
    def format_message(self, news_item):
        source_emojis = {
            "radio_farda": "🎙️",
            "bbc": "🇬🇧",
            "israel_hayom": "🇮🇱",
            "ynet": "🇮🇱",
            "times_of_israel": "🇮🇱",
        }
        
        source_names = {
            "radio_farda": "رادیو فردا",
            "bbc": "بی‌بی‌سی فارسی",
            "israel_hayom": "اسرائیل امروز",
            "ynet": "وای‌نت",
            "times_of_israel": "تایمز اسرائیل",
        }
        
        date_emojis = {
            "امروز": "🔥",
            "دیروز": "📆",
            "فردا": "🔮"
        }
        
        emoji = source_emojis.get(news_item['source'], "📰")
        name = source_names.get(news_item['source'], news_item['source'])
        date_emoji = date_emojis.get(news_item['date_label'], "📅")
        
        # ایمن کردن متن خبر
        safe_text = escape_markdown(news_item['text'])
        
        message = f"{emoji} *{name}*\n"
        message += f"{date_emoji} *{news_item['date_label']}*\n"
        message += f"\n{safe_text}"
        
        return message
    
    def create_inline_keyboard(self):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇰🇷 کانفیگ‌رایگان 🇰🇷", url=VPN_LINK)]
        ])
        return keyboard
    
    async def send_market_report(self):
        now = time.time()
        if now - self.last_market_time < 300:
            return
        self.last_market_time = now
        
        report = format_market_report()
        keyboard = self.create_inline_keyboard()
        try:
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=report,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            logger.info("📊 گزارش بازار ارسال شد")
        except Exception as e:
            logger.error(f"Market report error: {e}")
            # ارسال بدون مارکداون
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=report,
                reply_markup=keyboard
            )
    
    async def send_news_to_channel(self, news_item):
        try:
            message_text = self.format_message(news_item)
            keyboard = self.create_inline_keyboard()
            
            if news_item['image_url']:
                loop = asyncio.get_event_loop()
                image_file = await loop.run_in_executor(None, self.download_image, news_item['image_url'])
                
                if image_file:
                    try:
                        await self.bot.send_photo(
                            chat_id=self.channel_id,
                            photo=image_file,
                            caption=message_text,
                            parse_mode='Markdown',
                            reply_markup=keyboard
                        )
                        return True
                    except TelegramError as e:
                        # اگه مارکداون مشکل داشت، بدون مارکداون بفرست
                        logger.warning(f"Markdown failed, sending without: {e}")
                        await self.bot.send_photo(
                            chat_id=self.channel_id,
                            photo=image_file,
                            caption=news_item['text'],  # متن ساده بدون فرمت
                            reply_markup=keyboard
                        )
                        return True
                else:
                    await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=message_text,
                        parse_mode='Markdown',
                        reply_markup=keyboard
                    )
                    return True
            else:
                try:
                    await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=message_text,
                        parse_mode='Markdown',
                        reply_markup=keyboard
                    )
                    return True
                except TelegramError as e:
                    logger.warning(f"Markdown failed, sending without: {e}")
                    await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=news_item['text'],
                        reply_markup=keyboard
                    )
                    return True
                
        except TelegramError as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    async def run(self, interval_seconds=60):
        logger.info("🔥 ربات جنگ‌نیوز با قابلیت ارسال عکس روشن شد!")
        logger.info(f"📡 منابع فعال: {', '.join(RSS_FEEDS.keys())}")
        logger.info(f"🎯 فقط اخبار جنگ (ایران/آمریکا/اسرائیل) فیلتر میشه")
        logger.info(f"⏱ چک کردن هر {interval_seconds} ثانیه")
        logger.info(f"💰 گزارش رمز ارز و نرخ ارز هر 5 دقیقه")
        logger.info(f"🔘 دکمه شیشه‌ای کانفیگ رایگان")
        
        while True:
            start_time = time.time()
            logger.info("=" * 50)
            logger.info("🔍 چک کردن اخبار جدید...")
            
            # ارسال گزارش بازار
            await self.send_market_report()
            
            all_news = []
            
            for name, url in RSS_FEEDS.items():
                news = self.fetch_news(name, url)
                if news:
                    logger.info(f"✅ {name}: {len(news)} خبر")
                all_news.extend(news)
            
            all_news.sort(key=lambda x: x['parsed_date'] if x['parsed_date'] else datetime.min, reverse=True)
            
            sent_count = 0
            for news_item in all_news:
                success = await self.send_news_to_channel(news_item)
                
                if success:
                    self.seen_links.add(news_item['link'])
                    sent_count += 1
                    has_image = "📸" if news_item['image_url'] else "📝"
                    preview = news_item['text'][:50].replace('\n', ' ')
                    logger.info(f"{has_image} [{news_item['date_label']}] {preview}...")
                
                await asyncio.sleep(2)
            
            self.save_seen_links()
            
            elapsed = time.time() - start_time
            logger.info(f"📊 چرخه کامل شد. {sent_count} خبر جدید فرستاده شد.")
            
            wait_time = max(0, interval_seconds - elapsed)
            logger.info(f"⏳ منتظر {wait_time:.0f} ثانیه تا چک بعدی...")
            await asyncio.sleep(wait_time)

async def main():
    bot = WarNewsBot(BOT_TOKEN, CHANNEL_ID)
    await bot.run(interval_seconds=60)

if __name__ == "__main__":
    asyncio.run(main())
