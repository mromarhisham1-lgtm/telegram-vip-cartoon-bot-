import os
import json
import re
import requests
import asyncio
import difflib
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, Message,
    MenuButtonWebApp, WebAppInfo
)

# ---------- إعدادات البوت من البيئة ----------
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_USERNAME = "@mmyy869"
LANG_PREF = {}
ADMIN_IDS = [7822658568, 7462343463]

app = Client("search_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ---------- تحميل البيانات ----------
def load_data():
    with open("data.json", "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()

# ---------- دالة التطبيع ----------
def normalize_text(text):
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\d+', '', text)
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'[ة]', 'ه', text)
    text = re.sub(r'[ؤ]', 'و', text)
    text = re.sub(r'[ئء]', 'ي', text)
    text = re.sub(r'[ج]', 'غ', text)
    text = re.sub(r'\bال', '', text)

    ignore_words = ['كرتون', 'مسلسل', 'انمي', 'مانجا', 'فيلم',
                    'cartoon', 'series', 'anime', 'manga', 'movie',
                    'the', 'of', 'and', '&']
    for word in ignore_words:
        text = re.sub(r'\b{}\b'.format(re.escape(word)), '', text, flags=re.IGNORECASE)

    text = text.lower()
    text = ' '.join(text.split())
    return text.strip()

# ---------- دالة المطابقة ----------
def is_match(query, target):
    norm_query = normalize_text(query)
    norm_target = normalize_text(target)

    if norm_query == norm_target:
        return True
    if norm_query.replace(' ', '') == norm_target.replace(' ', ''):
        return True

    query_words = set(norm_query.split())
    target_words = set(norm_target.split())
    if query_words.issubset(target_words):
        return True

    seq = difflib.SequenceMatcher(None, norm_query, norm_target)
    return seq.ratio() >= 0.8

# ---------- تحقق من الاشتراك ----------
def is_user_subscribed(user_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
    params = {"chat_id": CHANNEL_USERNAME, "user_id": user_id}
    response = requests.get(url, params=params).json()
    try:
        status = response["result"]["status"]
        return status in ["member", "administrator", "creator"]
    except:
        return False

# ---------- حذف الرسائل التلقائي ----------
async def auto_delete_message(msg: Message, delay: int = 1800):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception as e:
        print(f"خطأ في حذف الرسالة: {e}")

# ---------- دالة التحقق من الاشتراك وإظهار زر الاشتراك ----------
async def verify_subscription(user_id: int, message=None, callback_query=None):
    if not is_user_subscribed(user_id):
        buttons = [
            [InlineKeyboardButton("🔔 اشترك في القناة", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}")],
            [InlineKeyboardButton("✅ تأكيد الاشتراك", callback_data="check_sub")]
        ]
        if message:
            await message.reply("📢 يجب الاشتراك في القناة أولاً", reply_markup=InlineKeyboardMarkup(buttons))
        elif callback_query:
            await callback_query.answer("❗ يجب الاشتراك أولاً", show_alert=True)
            await callback_query.message.reply("📢 يجب الاشتراك في القناة أولاً", reply_markup=InlineKeyboardMarkup(buttons))
        return False
    return True

# ---------- عند بدء البوت ----------
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    user_id = message.from_user.id
    if not await verify_subscription(user_id, message=message):
        return
    await send_language_selection(message)

@app.on_callback_query(filters.regex("check_sub"))
async def check_subscription(client, callback_query):
    if is_user_subscribed(callback_query.from_user.id):
        await callback_query.message.delete()
        await send_language_selection(callback_query.message)
    else:
        await callback_query.answer("❌ تأكد من الاشتراك أولاً", show_alert=True)

async def send_language_selection(message: Message):
    LANG_PREF[message.from_user.id] = None
    await message.reply(
        "اختر لغة البحث أولاً:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 العربية", callback_data="lang_ar")],
            [InlineKeyboardButton("🔍 الإنجليزية", callback_data="lang_en")],
            [InlineKeyboardButton("🌐 كلاهما", callback_data="lang_both")]
        ])
    )

@app.on_callback_query(filters.regex(r"lang_(ar|en|both)"))
async def set_language(client, callback_query):
    lang = callback_query.data.split("_")[1]
    LANG_PREF[callback_query.from_user.id] = lang
    await callback_query.answer(f"تم اختيار لغة البحث: {lang.upper()}", show_alert=True)
    lang_name = "العربية" if lang == "ar" else "الإنجليزية" if lang == "en" else "كلاهما"
    await callback_query.message.reply(
        f"✅ تم اختيار اللغة: {lang_name}\n✏️ اكتب ما تود البحث عنه أو اختر من الأزرار التالية:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📺 المسلسلات", callback_data="send_series")],
            [InlineKeyboardButton("🎬 الأفلام", callback_data="send_movies")]
        ])
    )

@app.on_callback_query(filters.regex("send_series"))
async def send_series(client, callback_query):
    if not await verify_subscription(callback_query.from_user.id, callback_query=callback_query):
        return
    lang = LANG_PREF.get(callback_query.from_user.id)
    if not lang:
        return await callback_query.answer("❗ اختر لغة البحث أولاً", show_alert=True)

    result_list = []
    for item in data:
        if not item["name_en"].strip().startswith("•"):
            name = item["name_ar"] if lang == "ar" else item["name_en"] if lang == "en" else f'{item["name_ar"]} | {item["name_en"]}'
            result_list.append(f"• [{name}]({item['link']})")

    if not result_list:
        return await callback_query.message.reply("❌ لا توجد مسلسلات.", disable_web_page_preview=True)

    batch_size = 99
    for i in range(0, len(result_list), batch_size):
        batch = result_list[i:i + batch_size]
        text = "\n".join(batch)
        sent_msg = await callback_query.message.reply(text, disable_web_page_preview=True, protect_content=True)
        asyncio.create_task(auto_delete_message(sent_msg))

@app.on_callback_query(filters.regex("send_movies"))
async def send_movies(client, callback_query):
    if not await verify_subscription(callback_query.from_user.id, callback_query=callback_query):
        return
    lang = LANG_PREF.get(callback_query.from_user.id)
    if not lang:
        return await callback_query.answer("❗ اختر لغة البحث أولاً", show_alert=True)

    result = ""
    for item in data:
        if item["name_en"].strip().startswith("•"):
            name = item["name_ar"] if lang == "ar" else item["name_en"] if lang == "en" else f'{item["name_ar"]} | {item["name_en"]}'
            result += f"• [{name}]({item['link']})\n"

    sent_msg = await callback_query.message.reply(result or "لا توجد أفلام.", disable_web_page_preview=True, protect_content=True)
    asyncio.create_task(auto_delete_message(sent_msg))

@app.on_message(filters.text & filters.private)
async def search(client, message):
    user_id = message.from_user.id
    if not await verify_subscription(user_id, message=message):
        return

    lang = LANG_PREF.get(user_id)
    if not lang:
        return await message.reply("❗ يجب اختيار لغة البحث أولاً باستخدام الأزرار.")

    query = message.text
    result = ""
    for item in data:
        names = []
        if lang in ("both", "ar"):
            names.append(item["name_ar"])
        if lang in ("both", "en"):
            names.append(item["name_en"])

        for name in names:
            if is_match(query, name):
                display_name = item["name_ar"] if lang == "ar" else item["name_en"] if lang == "en" else f'{item["name_ar"]} | {item["name_en"]}'
                result += f"• [{display_name}]({item['link']})\n"
                break

    await message.reply(result or "❌ لم يتم العثور على نتائج.", disable_web_page_preview=True, protect_content=True)

    if not result:
        for admin_id in ADMIN_IDS:
            try:
                await client.send_message(
                    admin_id,
                    f"📩 استفسار جديد من المستخدم:\n\n"
                    f"👤 الاسم: {message.from_user.first_name}\n"
                    f"💬 الرسالة: {message.text}"
                )
            except Exception as e:
                print(f"خطأ أثناء إرسال الرسالة للمشرف {admin_id}: {e}")

app.run()
