import asyncio
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import aiosqlite

API_TOKEN = os.getenv("API_TOKEN")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
DB_PATH = 'motivation.db'

# Начисляем баллы (не более 1 за действие в день)
@dp.message_handler(lambda msg: msg.text.startswith('+'))
async def handle_task(msg: types.Message):
    user_id = msg.from_user.id
    username = msg.from_user.username or msg.from_user.full_name
    task = msg.text[1:].strip().lower()
    today = datetime.now().date().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS logs (
            user_id INTEGER,
            task TEXT,
            date TEXT
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS prizes (
            name TEXT PRIMARY KEY,
            cost INTEGER
        )""")
        await db.execute("""INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)""", (user_id, username))
        # Проверка: начислялось ли сегодня
        async with db.execute("""SELECT 1 FROM logs WHERE user_id = ? AND task = ? AND date = ?""", (user_id, task, today)) as c:
            if await c.fetchone():
                return await msg.reply(f"Баллы за '{task}' уже начислены сегодня.")

        await db.execute("""INSERT INTO logs (user_id, task, date) VALUES (?, ?, ?)""", (user_id, task, today))
        await db.execute("""UPDATE users SET points = points + 1 WHERE user_id = ?""", (user_id,))
        await db.commit()
    await msg.reply(f"✅ За задачу '{task}' начислен 1 балл!")

@dp.message_handler(commands=['score'])
async def score(msg: types.Message):
    user_id = msg.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT points FROM users WHERE user_id = ?", (user_id,)) as c:
            row = await c.fetchone()
    if row:
        await msg.reply(f"У тебя {row[0]} баллов.")
    else:
        await msg.reply("У тебя пока нет баллов.")

@dp.message_handler(commands=['shop'])
async def shop(msg: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, cost FROM prizes") as c:
            rows = await c.fetchall()
    if rows:
        text = "\n".join([f"{name} — {cost} Б" for name, cost in rows])
        await msg.reply(f"🎁 Призы:\n{text}")
    else:
        await msg.reply("Магазин пуст.")

@dp.message_handler(commands=['buy'])
async def buy(msg: types.Message):
    user_id = msg.from_user.id
    item = msg.get_args().strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT cost FROM prizes WHERE name = ?", (item,)) as c:
            prize = await c.fetchone()
        if not prize:
            return await msg.reply("Такого приза нет.")
        cost = prize[0]
        async with db.execute("SELECT points FROM users WHERE user_id = ?", (user_id,)) as c:
            user = await c.fetchone()
        if not user or user[0] < cost:
            return await msg.reply("Недостаточно баллов.")
        await db.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (cost, user_id))
        await db.commit()
    await msg.reply(f"🎉 Ты обменял {cost} баллов на «{item}»!")

@dp.message_handler(commands=['top'])
async def top(msg: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT username, points FROM users ORDER BY points DESC LIMIT 10") as c:
            rows = await c.fetchall()
    if rows:
        leaderboard = "\n".join([f"{i+1}. {name}: {pts} Б" for i, (name, pts) in enumerate(rows)])
        await msg.reply("🏆 Топ участников:\n" + leaderboard)
    else:
        await msg.reply("Нет данных.")

async def main():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS prizes (
            name TEXT PRIMARY KEY,
            cost INTEGER
        )""")
        prizes = [
            ('лимонад из меню', 20), ('лапочка кола', 30), ('сок зуег', 35), ('пиво Б/А', 40),
            ('неликвидное вино россия', 120), ('неликвидное вино импорт', 260),
            ('бургер', 75), ('борщ', 65), ('шаньга', 65), ('яичница', 55),
            ('греча с уткой', 65), ('сет урал', 250),
            ('иммунитет к утренней смене', 40), ('выбор выходного', 60),
            ('иммунитет к аттестации', 250), ('нож сомелье', 240), ('футболка', 400)
        ]
        for name, cost in prizes:
            await db.execute("INSERT OR IGNORE INTO prizes (name, cost) VALUES (?, ?)", (name, cost))
        await db.commit()
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
