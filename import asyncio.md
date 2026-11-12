import asyncio  
import os  
import sqlite3  
from aiogram import Bot, Dispatcher, Router  
from aiogram.client.default import DefaultBotProperties  
from aiogram.enums import ParseMode  
from aiogram.filters import CommandStart  
from aiogram.fsm.context import FSMContext  
from aiogram.fsm.storage.memory import MemoryStorage  
from aiogram.types import Message  
  
DATA_DIR = os.getenv('DATA_DIR', '/app/data')  
if not os.path.exists(DATA_DIR):  
    os.makedirs(DATA_DIR, exist_ok=True)  
  
DB_PATH = os.path.join(DATA_DIR, "marketflows.db")  
BOT_TOKEN = "9111963048:AAFY6qDOnzl3X8qlos6tTXydxbARFhcgQkA"  
  
def db_init():  
    conn = sqlite3.connect(DB_PATH)  
    c = conn.cursor()  
    c.execute("""CREATE TABLE IF NOT EXISTS deals (  
        id INTEGER PRIMARY KEY AUTOINCREMENT,  
        code TEXT UNIQUE,  
        creator_id INTEGER,  
        creator_username TEXT,  
        deal_type TEXT DEFAULT 'gift',  
        gift_link TEXT,  
        amount REAL DEFAULT 0.0,  
        currency TEXT DEFAULT 'stars',  
        status TEXT DEFAULT 'pending',  
        created_at TEXT  
    )""")  
    c.execute("""CREATE TABLE IF NOT EXISTS settings (  
        key TEXT PRIMARY KEY,  
        value TEXT  
    )""")  
    conn.commit()  
    conn.close()  
  
router = Router()  
  
@router.message(CommandStart())  
async def cmd_start(msg: Message, state: FSMContext):  
    await msg.answer("🏦 <b>Market Reduo</b> успешно запущен и работает!", parse_mode="HTML")  
  
async def main():  
    db_init()  
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))  
    dp = Dispatcher(storage=MemoryStorage())  
    dp.include_router(router)  
    print("Market Reduo bot started successfully.")  
    await dp.start_polling(bot)  
  
if __name__ == "__main__":  
    try:  
        asyncio.run(main())  
    except KeyboardInterrupt:  
        pass  
