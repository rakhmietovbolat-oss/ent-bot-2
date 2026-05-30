import os
import json
import random
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8867637688:AAF4AlaQMF-W1lbDs5hJ8onb5RKi2OV3Ko8"
TW_URL = "https://agent.timeweb.cloud/api/v1/cloud-ai/agents/f9bce90f-820a-4a59-b16e-a789fc90eba9/v1"
TW_KEY = os.getenv("TIMEWEB_KEY", "")
KASPI = "87775406834"
PRICE_BASE = 1990
PRICE_VIP = 2990
FREE_DAYS = 11
FREE_DAILY = 22
BASE_DAILY = 60

DB = {}

SUBJECTS = {
    "math": "📐 Математика",
    "physics": "⚡ Физика",
    "history": "🏛 История КЗ",
    "biology": "🧬 Биология",
    "chemistry": "🧪 Химия",
    "geography": "🌍 География",
    "russian": "📖 Русский",
    "kazakh": "🌾 Казақ тілі"
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
    "math": "математика ЕНТ",
    "physics": "физика ЕНТ",
    "history": "история Казахстана ЕНТ",
    "biology": "биология ЕНТ",
    "chemistry": "химия ЕНТ",
    "geography": "география ЕНТ",
    "russian": "русский язык ЕНТ",
    "kazakh": "казахский язык ЕНТ"
}


def get_user(uid):
    uid = str(uid)
    if uid not in DB:
        DB[uid] = {
            "id": uid,
            "plan": "free",
            "plan_until": (datetime.now() + timedelta(days=FREE_DAYS)).isoformat(),
            "qt": 0,
            "ld": datetime.now().strftime("%Y-%m-%d"),
            "tc": 0,
            "tq": 0,
            "subj": "math",
            "cq": None,
            "pp": None
        }
    return DB[uid]


def get_limit(u):
    if datetime.fromisoformat(u["plan_until"]) < datetime.now():
        u["plan"] = "free"
    if u["plan"] == "vip":
        return 9999
    if u["plan"] == "base":
        return BASE_DAILY
    return FREE_DAILY


def reset_daily(u):
    t = datetime.now().strftime("%Y-%m-%d")
    if u["ld"] != t:
        u["qt"] = 0
        u["ld"] = t
    return u


def ask_ai(prompt, system="Ты репетитор ЕНТ Казахстан. Отвечай кратко по-русски."):
    client = OpenAI(api_key=TW_KEY, base_url=TW_URL)
    r = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-V3",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_tokens=600
    )
    return r.choices[0].message.content


def generate_question(subj, plan):
    topic = random.choice(TOPICS[subj])
    diffs = {"free": ["easy"], "base": ["easy", "medium"], "vip": ["easy", "medium", "hard"]}
    diff = random.choice(diffs.get(plan, ["easy"]))
    seed = random.randint(1, 99999)
    prompt = (
        f'Тема: {topic}, предмет: {PROMPTS[subj]}, seed={seed}\n'
        f'Сгенерируй вопрос ЕНТ. ТОЛЬКО JSON без markdown:\n'
        f'{{"q":"вопрос","opts":["а","б","в","г"],"ans":0,"diff":"{diff}","topic":"{topic}","explain":"объяснение"}}'
    )
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
             InlineKeyboardButton("🔄 Предмет", callback_data="cs")]
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("А", callback_data="a0"),
         InlineKeyboardButton("Б", callback_data="a1"),
         InlineKeyboardButton("В", callback_data="a2"),
         InlineKeyboardButton("Г", callback_data="a3")],
        [InlineKeyboardButton("💡 Подсказка", callback_data="ht"),
         InlineKeyboardButton("🔄 Предмет", callback_data="cs")]
    ])


def pay_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💛 Обычный 1990тг", callback_data="pb")],
        [InlineKeyboardButton("💎 VIP 2990тг", callback_data="pv")],
        [InlineKeyboardButton("✅ Оплатил", callback_data="pd")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    days = max(0, (datetime.fromisoformat(user["plan_until"]) - datetime.now()).days + 1)
    plans = {"free": "🆓", "base": "💛", "vip": "💎"}
    await update.message.reply_text(
        f"🎓 *ЕНТ Репетитор*\n\nСәлем, {update.effective_user.first_name}!\n"
        f"Тариф: {plans.get(user['plan'])} | {days} дней\n\nВыбери предмет:",
        parse_mode="Markdown",
        reply_markup=subj_kb()
    )


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
            f"✅ *{SUBJECTS[user['subj']]}*\nОсталось: {left}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▶ Новый вопрос", callback_data="nq")]])
        )

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
            de = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(qd.get("diff", "easy"), "🟢")
            text = (
                f"{de} *{SUBJECTS[user['subj']]}* · {qd.get('topic', '')}\n\n"
                f"❓ *{qd['q']}*\n\n"
                f"А) {qd['opts'][0]}\n"
                f"Б) {qd['opts'][1]}\n"
                f"В) {qd['opts'][2]}\n"
                f"Г) {qd['opts'][3]}\n\n"
                f"{user['qt']}/{get_limit(user)}"
            )
            await q.edit_message_text(text, parse_mode="Markdown", reply_markup=q_kb())
        except Exception as e:
            await q.edit_message_text(
                "❌ Ошибка. Попробуй снова.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄", callback_data="nq")]])
            )

    elif d.startswith("a"):
        if not user.get("cq"):
            return
        qd = user["cq"]
        chosen = int(d[1:])
        correct = qd["ans"]
        keys = ["А", "Б", "В", "Г"]
        if chosen == correct:
            user["tc"] += 1
            result = "✅ *Правильно!*"
        else:
            result = f"❌ *Неверно.* Правильный: *{keys[correct]}*"
        pct = round(user["tc"] / user["tq"] * 100) if user["tq"] else 0
        explain = f"\n\n💡 {qd.get('explain', '')}" if user["plan"] in ["base", "vip"] else "\n\n💡 Объяснения в тарифе Обычный/VIP"
        await q.edit_message_text(
            f"{result}{explain}\n\n📊 {user['tc']}/{user['tq']} ({pct}%)",
            parse_mode="Markdown",
            reply_markup=q_kb(True)
        )

    elif d == "ht":
        if not user.get("cq"):
            await q.answer("Загрузи вопрос!", show_alert=True)
            return
        if user["plan"] == "free":
            await q.answer("Подсказки в тарифе Обычный/VIP", show_alert=True)
            return
        hint = ask_ai(f"Вопрос ЕНТ: {user['cq']['q']}\nПодсказка без ответа.")
        await q.answer(hint[:200], show_alert=True)

    elif d == "th":
        if not user.get("cq"):
            return
        if user["plan"] == "free":
            await q.answer("Теория в тарифе Обычный/VIP", show_alert=True)
            return
        theory = ask_ai(f"Теория по теме {user['cq'].get('topic', '')} для ЕНТ. 3 предложения.")
        await q.edit_message_text(
            f"📚 {theory}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▶ Следующий", callback_data="nq")]])
        )

    elif d == "cs":
        await q.edit_message_text("Выбери предмет:", reply_markup=subj_kb())

    elif d in ["pb", "pv"]:
        plan = "vip" if d == "pv" else "base"
        price = PRICE_VIP if plan == "vip" else PRICE_BASE
        name = "VIP" if plan == "vip" else "Обычный"
        user["pp"] = plan
        await q.edit_message_text(
            f"💳 *{name} — {price} тг*\n\nKaspi: {KASPI}\nСумма: *{price} тг*\n\nПосле оплаты нажми ✅",
            parse_mode="Markdown",
            reply_markup=pay_kb()
        )

    elif d == "pd":
        await q.edit_message_text("✅ Пришли скриншот — активирую!")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if user.get("pp") and update.message.photo:
        plan = user["pp"]
        name = "VIP" if plan == "vip" else "Обычный"
        user["plan"] = plan
        user["plan_until"] = (datetime.now() + timedelta(days=30)).isoformat()
        user["pp"] = None
        await update.message.reply_text(
            f"✅ *{name} активирован!* Удачи на ЕНТ! 🎓",
            parse_mode="Markdown",
            reply_markup=subj_kb()
        )
        return
    if user["plan"] in ["base", "vip"]:
        ctx = f"Предмет: {SUBJECTS[user['subj']]}"
        if user.get("cq"):
            ctx += f"\nВопрос: {user['cq']['q']}"
        resp = ask_ai(ctx + "\n" + update.message.text)
        await update.message.reply_text(f"🤖 {resp}")
    else:
        await update.message.reply_text("💬 Чат в тарифах Обычный/VIP\n\n/subscribe")


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💳 *Тарифы*\n\n"
        "🆓 *Бесплатно 11 дней:* 22 вопроса\n"
        "💛 *Обычный 1990тг:* 60 вопросов + объяснения\n"
        "💎 *VIP 2990тг:* безлимит + чат + теория",
        parse_mode="Markdown",
        reply_markup=pay_kb()
    )


class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *args):
        pass


def run_web():
    HTTPServer(("0.0.0.0", 8080), WebHandler).serve_forever()


def main():
    threading.Thread(target=run_web, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.ALL, message_handler))
    print("Bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()
