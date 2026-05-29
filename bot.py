import os
import json
import random
import threading
from datetime import datetime, timedelta
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ===== FLASK WEB SERVER =====
from flask import Flask
app = Flask(__name__)

@app.route('/')
def index():
    return 'ENT Bot is running!'

def run_bot():

# ===== CONFIG =====
BOT_TOKEN = "8867637688:AAF4AlaQMF-W1lbDs5hJ8onb5RKi2OV3Ko8"
TIMEWEB_URL = "https://agent.timeweb.cloud/api/v1/cloud-ai/agents/f9bce90f-820a-4a59-b16e-a789fc90eba9/v1"
TIMEWEB_KEY = os.getenv("TIMEWEB_KEY", "")
KASPI_PHONE = "87775406834"
PRICE_BASE = 1990
PRICE_VIP = 2990
FREE_DAYS = 11
FREE_DAILY = 22
BASE_DAILY = 60

# ===== DB =====
DB_FILE = "users.json"

def load_db():
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def get_user(uid):
    db = load_db()
    uid = str(uid)
    if uid not in db:
        db[uid] = {
            "id": uid, "plan": "free",
            "plan_until": (datetime.now() + timedelta(days=FREE_DAYS)).isoformat(),
            "questions_today": 0, "last_date": datetime.now().strftime("%Y-%m-%d"),
            "total_correct": 0, "total_questions": 0,
            "subject": "math", "current_q": None, "pending_payment": None
        }
        save_db(db)
    return db[uid]

def save_user(user):
    db = load_db()
    db[str(user["id"])] = user
    save_db(db)

def reset_daily(user):
    today = datetime.now().strftime("%Y-%m-%d")
    if user["last_date"] != today:
        user["questions_today"] = 0
        user["last_date"] = today
    return user

def get_limit(user):
    until = datetime.fromisoformat(user["plan_until"])
    if until < datetime.now():
        user["plan"] = "free"
        save_user(user)
    if user["plan"] == "vip": return 9999
    if user["plan"] == "base": return BASE_DAILY
    return FREE_DAILY

# ===== SUBJECTS =====
SUBJECTS = {
    "math":"📐 Математика","physics":"⚡ Физика","history":"🏛 История КЗ",
    "biology":"🧬 Биология","chemistry":"🧪 Химия","geography":"🌍 География",
    "russian":"📖 Русский язык","kazakh":"🌾 Қазақ тілі"
}
TOPICS = {
    "math":["алгебра","геометрия","тригонометрия","логарифмы","производные","вероятность"],
    "physics":["механика","термодинамика","электричество","магнетизм","оптика"],
    "history":["казахские ханства","джунгарские войны","советский период","независимость РК","народные восстания"],
    "biology":["клетка","генетика","эволюция","экология","ботаника","зоология","анатомия"],
    "chemistry":["периодическая таблица","реакции","органика","кислоты"],
    "geography":["рельеф","климат","реки и озёра","природные зоны"],
    "russian":["орфография","пунктуация","морфология","синтаксис"],
    "kazakh":["орфография","грамматика","морфология","синтаксис"]
}
PROMPTS = {
    "math":"математика ЕНТ: алгебра, геометрия, тригонометрия, логарифмы, производные, вероятность",
    "physics":"физика ЕНТ: механика, термодинамика, электричество, магнетизм, оптика",
    "history":"история Казахстана ЕНТ: казахские ханства, джунгарские войны, советский период, независимость РК",
    "biology":"биология ЕНТ: клетка, генетика, эволюция, экология, ботаника, зоология, анатомия",
    "chemistry":"химия ЕНТ: периодическая таблица, реакции, органика, кислоты",
    "geography":"география ЕНТ: рельеф, климат, реки Казахстана, природные зоны",
    "russian":"русский язык ЕНТ: орфография, пунктуация, морфология, синтаксис",
    "kazakh":"қазақ тілі ЕНТ: орфография, грамматика, морфология, синтаксис"
}

# ===== AI =====
def ask_ai(prompt, system="Ты репетитор ЕНТ Казахстан. Отвечай кратко по-русски."):
    client = OpenAI(api_key=TIMEWEB_KEY, base_url=TIMEWEB_URL)
    r = client.chat.completions.create(
        model="claude-haiku-4-5-20251001",
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        max_tokens=600
    )
    return r.choices[0].message.content

def generate_question(subject, plan):
    topic = random.choice(TOPICS[subject])
    diffs = {"free":["easy"],"base":["easy","medium"],"vip":["easy","medium","hard"]}
    diff = random.choice(diffs.get(plan,["easy"]))
    seed = random.randint(1,99999)
    prompt = f'Предмет: {PROMPTS[subject]}. Тема: {topic}. seed={seed}\nСгенерируй 1 уникальный вопрос ЕНТ по теме "{topic}". Сложность: {diff}.\nОтветь ТОЛЬКО JSON без markdown:\n{{"q":"вопрос","opts":["вар1","вар2","вар3","вар4"],"ans":0,"diff":"{diff}","topic":"{topic}","explain":"объяснение 2-3 предложения"}}\nans=индекс 0-3'
    text = ask_ai(prompt,"Отвечай ТОЛЬКО валидным JSON без markdown.")
    return json.loads(text.replace("```json","").replace("```","").strip())

# ===== KEYBOARDS =====
def subj_kb():
    items = list(SUBJECTS.items())
    rows = []
    for i in range(0,len(items),2):
        row = [InlineKeyboardButton(items[i][1],callback_data=f"subj_{items[i][0]}")]
        if i+1<len(items): row.append(InlineKeyboardButton(items[i+1][1],callback_data=f"subj_{items[i+1][0]}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)

def q_kb(answered=False):
    if answered:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("▶ Следующий вопрос",callback_data="next_q")],
            [InlineKeyboardButton("📚 Теория",callback_data="theory"),InlineKeyboardButton("🔄 Сменить предмет",callback_data="change_subj")]
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("А",callback_data="ans_0"),InlineKeyboardButton("Б",callback_data="ans_1"),
         InlineKeyboardButton("В",callback_data="ans_2"),InlineKeyboardButton("Г",callback_data="ans_3")],
        [InlineKeyboardButton("💡 Подсказка",callback_data="hint"),InlineKeyboardButton("🔄 Сменить предмет",callback_data="change_subj")]
    ])

def pay_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💛 Обычный — 1990 тг",callback_data="pay_base")],
        [InlineKeyboardButton("💎 VIP — 2990 тг",callback_data="pay_vip")],
        [InlineKeyboardButton("✅ Я оплатил",callback_data="paid")]
    ])

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    days_left = max(0,(datetime.fromisoformat(user["plan_until"])-datetime.now()).days+1)
    plans = {"free":"🆓 Бесплатный","base":"💛 Обычный","vip":"💎 VIP"}
    await update.message.reply_text(
        f"🎓 *ЕНТ Репетитор* — AI подготовка\n\nСәлем, {update.effective_user.first_name}! 👋\n\n"
        f"Тариф: {plans.get(user['plan'])}\nАктивен ещё: {days_left} дней\n\n"
        f"📚 8 предметов ЕНТ\n🤖 AI объяснения\n📊 Статистика\n\nВыбери предмет:",
        parse_mode="Markdown",reply_markup=subj_kb()
    )

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    user = get_user(uid)
    user = reset_daily(user)
    d = q.data

    if d.startswith("subj_"):
        user["subject"] = d.replace("subj_","")
        save_user(user)
        left = max(0,get_limit(user)-user["questions_today"])
        await q.edit_message_text(f"✅ *{SUBJECTS[user['subject']]}*\n\nВопросов сегодня: *{left}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▶ Новый вопрос",callback_data="next_q")]]))

    elif d=="next_q":
        if user["questions_today"]>=get_limit(user):
            await q.edit_message_text("📵 Лимит исчерпан. Оформи подписку!",reply_markup=pay_kb()); return
        await q.edit_message_text("⏳ Генерирую вопрос...")
        try:
            question = generate_question(user["subject"],user["plan"])
            user["current_q"]=question; user["questions_today"]+=1; user["total_questions"]+=1
            save_user(user)
            de={"easy":"🟢","medium":"🟡","hard":"🔴"}.get(question.get("diff","easy"),"🟢")
            dn={"easy":"Лёгкий","medium":"Средний","hard":"Сложный"}.get(question.get("diff","easy"),"Лёгкий")
            text=(f"{de} *{SUBJECTS[user['subject']]}* · {dn}\n📌 {question.get('topic','')}\n\n"
                  f"❓ *{question['q']}*\n\nА) {question['opts'][0]}\nБ) {question['opts'][1]}\n"
                  f"В) {question['opts'][2]}\nГ) {question['opts'][3]}\n\n📝 {user['questions_today']}/{get_limit(user)}")
            await q.edit_message_text(text,parse_mode="Markdown",reply_markup=q_kb())
        except:
            await q.edit_message_text("❌ Ошибка. Попробуй снова.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Попробовать",callback_data="next_q")]]))

    elif d.startswith("ans_"):
        if not user.get("current_q"): return
        question=user["current_q"]; chosen=int(d.replace("ans_","")); correct=question["ans"]
        keys=["А","Б","В","Г"]
        if chosen==correct: user["total_correct"]+=1; result="✅ *Правильно!*"
        else: result=f"❌ *Неверно.* Правильный: *{keys[correct]}) {question['opts'][correct]}*"
        save_user(user)
        pct=round(user["total_correct"]/user["total_questions"]*100) if user["total_questions"] else 0
        explain=f"\n\n💡 {question.get('explain','')}" if user["plan"] in ["base","vip"] else "\n\n💡 Объяснения — в тарифе Обычный и VIP"
        await q.edit_message_text(f"{result}{explain}\n\n📊 {user['total_correct']}/{user['total_questions']} ({pct}%)",
            parse_mode="Markdown",reply_markup=q_kb(answered=True))

    elif d=="hint":
        if not user.get("current_q"): await q.answer("Сначала загрузи вопрос!",show_alert=True); return
        if user["plan"]=="free": await q.answer("💡 Подсказки — в тарифе Обычный и VIP",show_alert=True); return
        hint=ask_ai(f"Вопрос ЕНТ: {user['current_q']['q']}\nДай подсказку не раскрывая ответ. 1-2 предложения.")
        await q.answer(hint[:200],show_alert=True)

    elif d=="theory":
        if not user.get("current_q"): return
        if user["plan"]=="free": await q.answer("📚 Теория — в тарифе Обычный и VIP",show_alert=True); return
        question=user["current_q"]
        theory=ask_ai(f"Объясни теорию по теме '{question.get('topic','')}' для ЕНТ. 3-4 предложения.")
        await q.edit_message_text(f"📚 *{question.get('topic','')}*\n\n{theory}",parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▶ Следующий вопрос",callback_data="next_q")]]))

    elif d=="change_subj":
        await q.edit_message_text("Выбери предмет:",reply_markup=subj_kb())

    elif d.startswith("pay_"):
        plan="vip" if d=="pay_vip" else "base"
        price=PRICE_VIP if plan=="vip" else PRICE_BASE
        emoji="💎" if plan=="vip" else "💛"; name="VIP" if plan=="vip" else "Обычный"
        user["pending_payment"]=plan; save_user(user)
        await q.edit_message_text(
            f"{emoji} *Тариф {name} — {price} тг/месяц*\n\n💳 Оплата через Kaspi:\n📱 Номер: `{KASPI_PHONE}`\n💰 Сумма: *{price} тенге*\n\nПосле оплаты нажми ✅ Я оплатил и пришли скриншот",
            parse_mode="Markdown",reply_markup=pay_kb())

    elif d=="paid":
        await q.edit_message_text("✅ Пришли скриншот оплаты — активирую в течение часа!")

async def msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if user.get("pending_payment") and update.message.photo:
        plan=user["pending_payment"]; name="VIP" if plan=="vip" else "Обычный"
        user["plan"]=plan; user["plan_until"]=(datetime.now()+timedelta(days=30)).isoformat()
        user["pending_payment"]=None; save_user(user)
        await update.message.reply_text(f"✅ *Тариф {name} активирован!*\n\nУдачи на ЕНТ! 🎓",
            parse_mode="Markdown",reply_markup=subj_kb()); return
    if user["plan"] in ["base","vip"]:
        ctx=f"Предмет: {SUBJECTS[user['subject']]}"
        if user.get("current_q"): ctx+=f"\nВопрос: {user['current_q']['q']}"
        resp=ask_ai(ctx+f"\nВопрос ученика: {update.message.text}")
        await update.message.reply_text(f"🤖 {resp}")
    else:
        await update.message.reply_text("💬 Чат доступен в тарифах Обычный и VIP\n\n/subscribe")

async def subscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💳 *Тарифы ЕНТ Репетитор*\n\n"
        "🆓 *Бесплатно (11 дней):*\n• 22 вопроса/день\n• Лёгкие вопросы\n\n"
        "💛 *Обычный — 1990 тг/мес:*\n• 60 вопросов/день\n• Объяснения\n• Все 8 предметов\n\n"
        "💎 *VIP — 2990 тг/мес:*\n• Безлимит\n• Все уровни сложности\n• ИИ-чат\n• Теория",
        parse_mode="Markdown",reply_markup=pay_kb())

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=get_user(update.effective_user.id)
    pct=round(user["total_correct"]/user["total_questions"]*100) if user["total_questions"] else 0
    days_left=max(0,(datetime.fromisoformat(user["plan_until"])-datetime.now()).days+1)
    plans={"free":"🆓 Бесплатный","base":"💛 Обычный","vip":"💎 VIP"}
    await update.message.reply_text(
        f"📊 *Статистика*\n\nТариф: {plans.get(user['plan'])}\nАктивен ещё: {days_left} дней\n\n"
        f"✅ Правильных: {user['total_correct']}\n📝 Всего: {user['total_questions']}\n"
        f"🎯 Точность: {pct}%\n🏆 Прогноз ЕНТ: {round(pct/100*140)}/140",
        parse_mode="Markdown")

def main_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("subscribe",subscribe_cmd))
    app.add_handler(CommandHandler("stats",stats_cmd))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.ALL,msg_handler))
    print("🤖 ЕНТ Репетитор запущен!")
    app.run_polling()

if __name__=="__main__":
    import threading
    threading.Thread(target=main_bot, daemon=True).start()
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
