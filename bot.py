import os
import json
import random
import threading
import logging
import traceback
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ent-bot")
logging.getLogger("httpx").setLevel(logging.WARNING)

BOT_TOKEN = "8867637688:AAF4AlaQMF-W1lbDs5hJ8onb5RKi2OV3Ko8"
TW_URL = "https://agent.timeweb.cloud/api/v1/cloud-ai/agents/f9bce90f-820a-4a59-b16e-a789fc90eba9/v1"
TW_KEY = os.getenv("TIMEWEB_KEY", "")
MODEL = os.getenv("MODEL_NAME", "gpt-4o")
KASPI = "87775406834"
PRICE_BASE = 1990
PRICE_VIP = 2990
FREE_DAYS = 11
FREE_DAILY = 22
BASE_DAILY = 60

DB = {}

SUBJECTS = {
    "math": "📐 Математика", "physics": "⚡ Физика", "history": "🏛 История КЗ",
    "biology": "🧬 Биология", "chemistry": "🧪 Химия", "geography": "🌍 География",
    "russian": "📖 Русский", "kazakh": "🌾 Казақ тілі"
}

TOPICS = {
    "math": ["алгебра", "геометрия", "тригонометрия", "производные", "вероятность"],
    "physics": ["механика", "электричество", "оптика"],
    "history": ["казахские ханства", "советский период", "независимость РК"],
    "biology": ["клетка", "генетика", "экология"],
    "chemistry": ["реакции", "органика", "кислоты"],
    "geography": ["рельеф", "климат", "природные зоны"],
    "russian": ["орфография", "пунктуация", "синтаксис"],
    "kazakh": ["орфография", "грамматика", "синтаксис"]
}

PROMPTS = {
    "math": "математика ЕНТ", "physics": "физика ЕНТ", "history": "история Казахстана ЕНТ",
    "biology": "биология ЕНТ", "chemistry": "химия ЕНТ", "geography": "география ЕНТ",
    "russian": "русский язык ЕНТ", "kazakh": "казахский язык ЕНТ"
}


def get_user(uid):
    uid = str(uid)
    if uid not in DB:
        DB[uid] = {"id": uid, "plan": "free",
                   "plan_until": (datetime.now() + timedelta(days=FREE_DAYS)).isoformat(),
                   "qt": 0, "ld": datetime.now().strftime("%Y-%m-%d"),
                   "tc": 0, "tq": 0, "subj": "math", "cq": None, "pp": None}
    return DB[uid]


def get_limit(u):
    if datetime.fromisoformat(u["plan_until"]) < datetime.now():
        u["plan"] = "free"
    if u["plan"] == "vip": return 9999
    if u["plan"] == "base": return BASE_DAILY
    return FREE_DAILY


def reset_daily(u):
    t = datetime.now().strftime("%Y-%m-%d")
    if u["ld"] != t:
        u["qt"] = 0
        u["ld"] = t
    return u


def ask_ai(prompt, system="Ты репетитор ЕНТ Казахстан. Отвечай кратко по-русски."):
    log.info(f"ask_ai -> model={MODEL}")
    client = OpenAI(api_key=TW_KEY, base_url=TW_URL)
    try:
        r = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            max_tokens=600
        )
        return r.choices[0].message.content
    except Exception as e:
        log.error(f"ask_ai FAILED: {type(e).__name__}: {e}")
        log.error(traceback.format_exc())
        raise


def generate_question(subj, plan):
    topic = random.choice(TOPICS[subj])
    diffs = {"free": ["easy"], "base": ["easy", "medium"], "vip": ["easy", "medium", "hard"]}
    diff = random.choice(diffs.get(plan, ["easy"]))
    seed = random.randint(1, 99999)
    prompt = (f'Тема: {topic}, предмет: {PROMPTS[subj]}, seed={seed}\n'
              f'Сгенерируй вопрос ЕНТ. ТОЛЬКО JSON без markdown:\n'
              f'{{"q":"вопрос","opts":["а","б","в","г"],"ans":0,"diff":"{diff}","topic":"{topic}","explain":"объяснение"}}')
    text = ask_ai(prompt, "Отвечай ТОЛЬКО JSON без markdown.")
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


def subj_kb():
    items = list(SUBJECTS.items())
    rows = []
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(items[i][1], callback_data=f"s_{items[i][0]}")]
        if i + 1 < len(items):
            row.append(InlineKeyboardButton(items[i + 1][1], callback_data=f"s_{items[i + 1][0]}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def q_kb(answered=False):
    if answered:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("▶ Следующий", callback_data="nq")],
            [InlineKeyboardButton("📚 Теория", callback_data="th"),
             InlineKeyboardButton("🔄 Предмет", callback_data="cs")]])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("А", callback_data="a0"), InlineKeyboardButton("Б", callback_data="a1"),
         InlineKeyboardButton("В", callback_data="a2"), InlineKeyboardButton("Г", callback_data="a3")],
        [InlineKeyboardButton("💡 Подсказка", callback_data="ht"),
         InlineKeyboardButton("🔄 Предмет", callback_data="cs")]])


def pay_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💛 Обычный 1990тг", callback_data="pb")],
        [InlineKeyboardButton("💎 VIP 2990тг", callback_data="pv")],
        [InlineKeyboardButton("✅ Оплатил", callback_data="pd")]])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    days = max(0, (datetime.fromisoformat(user["plan_until"]) - datetime.now()).days + 1)
    plans = {"free": "🆓", "base": "💛", "vip": "💎"}
    await update.message.reply_text(
        f"🎓 *ЕНТ Репетитор*\n\nСәлем, {update.effective_user.first_name}!\n"
        f"Тариф: {plans.get(user['plan'])} | {days} дней\n\nВыбери предмет:",
        parse_mode="Markdown", reply_markup=subj_kb())


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    user = get_user(uid)
    user = reset_daily(user)
    d = q.data

    if d.startswith("s_"):
        user["subj"] = d[2:]
        left = max(0, get_limit(user) - user["qt"])
        await q.edit_message_text(
            f"✅ *{SUBJECTS[user['subj']]}*\nОсталось: {left}", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▶ Новый вопрос", callback_data="nq")]]))

    elif d == "nq":
        if user["qt"] >= get_limit(user):
            await q.edit_message_text("📵 Лимит! Оформи подписку.", reply_markup=pay_kb())
            return
        await q.edit_message_text("⏳ Генерирую вопрос...")
        try:
            qd = generate_question(user["subj"], user["plan"])
            user["cq"] = qd
            user["qt"] += 1
            user["tq"] += 1
            de =
