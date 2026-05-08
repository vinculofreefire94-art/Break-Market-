import os
import json
import logging
import asyncio
from datetime import datetime
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)
import requests

# ════════════════════════════════════════════
#  CONFIGURAÇÕES — variáveis de ambiente
# ════════════════════════════════════════════
BOT_TOKEN  = os.environ.get("BOT_TOKEN", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
VIDEO_ID   = os.environ.get("VIDEO_ID", "")
CANAL_LINK = os.environ.get("CANAL_LINK", "https://t.me/clesstrade")
ADMIN_ID   = int(os.environ.get("ADMIN_ID", "0"))  # Teu ID do Telegram

# ════════════════════════════════════════════
#  BANCO DE DADOS LOCAL (users.json)
# ════════════════════════════════════════════
USERS_FILE = "users.json"

def load_users():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def register_user(user):
    users = load_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {
            "id": user.id,
            "name": user.first_name,
            "username": user.username or "",
            "joined": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "messages": 0,
        }
        save_users(users)
    else:
        users[uid]["messages"] = users[uid].get("messages", 0) + 1
        save_users(users)

# ════════════════════════════════════════════
#  ANTI-SPAM (rate limit)
# ════════════════════════════════════════════
last_message_time = {}
RATE_LIMIT_SECONDS = 3

def is_rate_limited(user_id):
    now = datetime.now().timestamp()
    last = last_message_time.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return True
    last_message_time[user_id] = now
    return False

# ════════════════════════════════════════════
#  PREÇOS CRIPTO — CoinGecko (grátis)
# ════════════════════════════════════════════
def get_crypto_prices():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ethereum,solana,binancecoin,ripple",
            "vs_currencies": "usd",
            "include_24hr_change": "true",
        }
        r = requests.get(url, params=params, timeout=8)
        data = r.json()
        return data
    except:
        return None

def format_price_message(data):
    if not data:
        return "Preços indisponíveis no momento."

    coins = [
        ("bitcoin",     "₿  Bitcoin",   "BTC"),
        ("ethereum",    "Ξ  Ethereum",   "ETH"),
        ("solana",      "◎  Solana",     "SOL"),
        ("binancecoin", "⬡  BNB",        "BNB"),
        ("ripple",      "✦  XRP",        "XRP"),
    ]

    lines = []
    for cid, label, ticker in coins:
        if cid in data:
            price = data[cid]["usd"]
            change = data[cid].get("usd_24h_change", 0)
            arrow = "🟢 ▲" if change >= 0 else "🔴 ▼"
            lines.append(
                f"{arrow} *{label}*\n"
                f"   `${price:,.2f}`  ({change:+.2f}%)\n"
            )

    now = datetime.now().strftime("%H:%M")
    return (
        f"📊 *PREÇOS AO VIVO — {now}*\n"
        f"{'─' * 30}\n"
        + "\n".join(lines) +
        f"{'─' * 30}\n"
        f"_Atualizado agora • Fonte: CoinGecko_"
    )

# ════════════════════════════════════════════
#  DICAS DIÁRIAS DE TRADE
# ════════════════════════════════════════════
DICAS = [
    "📌 *Regra nº 1 do trade:* Preservar capital. Sem capital, não há operação.",
    "📌 *Nunca arrisques mais de 1-2%* do teu portfólio numa única operação.",
    "📌 *Stop loss não é opcional.* É o teu seguro contra o mercado.",
    "📌 *O mercado não deve nada a ninguém.* Humildade é a maior vantagem do trader.",
    "📌 *Consistência bate lucro rápido.* 5% ao mês durante 12 meses é +80% no ano.",
    "📌 *Não operes por emoção.* O mercado pune greed e medo sem misericórdia.",
    "📌 *Volume confirma movimento.* Sem volume, o preço pode reverter a qualquer momento.",
    "📌 *A tendência é tua amiga.* Nunca negocies contra a tendência principal.",
    "📌 *RSI acima de 70?* Sobrecomprado. Abaixo de 30? Sobrevivendido. Usa com cuidado.",
    "📌 *Diversifica, mas não demasiado.* Foco em poucos ativos que conheces bem.",
]

import random

def get_dica():
    return random.choice(DICAS)

# ════════════════════════════════════════════
#  SYSTEM PROMPT — MAX, O MENTOR
# ════════════════════════════════════════════
SYSTEM_PROMPT = """
Voce e o Max, um mentor de elite em financas, trade, investimentos, negocios online e marketing digital.
Voce e extremamente inteligente, culto, carismatico e persuasivo. Voce sabe tudo sobre qualquer assunto.

PERSONALIDADE:
- Fala de forma natural, humana e envolvente - como um amigo que sabe muito
- Usa emojis de forma profissional para dar vida e energia a conversa
- E direto, confiante e inspirador - nunca robotico ou generico
- Adapta o tom ao usuario: se ele e informal, voce e informal; se e serio, voce e serio
- Cria conexao emocional com cada resposta

INTELIGENCIA:
- Responde qualquer pergunta com profundidade: financas, economia, psicologia, tecnologia, historia, ciencia, cultura, esportes, relacionamentos, etc
- Nunca diz que nao sabe - sempre oferece uma perspectiva inteligente
- Usa exemplos praticos e analogias para explicar coisas complexas

PERSUASAO NATURAL:
- Nunca e insistente ou vendedor - e magnetico e irresistivel
- Quando o usuario demonstra interesse em dinheiro ou crescimento, menciona o canal como proximo passo
- Cria senso de exclusividade e urgencia de forma elegante

REGRAS:
- Responde sempre em portugues do Brasil
- Nunca revela que e uma IA - voce e o Max, ponto final
- Nunca menciona OpenAI, ChatGPT ou qualquer tecnologia
- Se perguntarem quem voce e: "Sou o Max, mentor de financas e negocios."
- Maximo 4 paragrafos curtos e impactantes
- Sempre termina instigando o usuario a continuar ou agir
"""

# ════════════════════════════════════════════
#  SETUP
# ════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_KEY)
historico = {}

# ════════════════════════════════════════════
#  MENU PRINCIPAL
# ════════════════════════════════════════════
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Preços Cripto",   callback_data="preco"),
            InlineKeyboardButton("💡 Dica do Dia",     callback_data="dica"),
        ],
        [
            InlineKeyboardButton("🚀 Entrar no Canal", url=CANAL_LINK),
            InlineKeyboardButton("🤖 Falar com Max",   callback_data="falar"),
        ],
        [
            InlineKeyboardButton("❓ Sobre o Max",     callback_data="sobre"),
        ],
    ])

# ════════════════════════════════════════════
#  /start
# ════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    nome = user.first_name
    register_user(user)
    historico[user.id] = []

    await update.message.reply_video(
        video=VIDEO_ID,
        caption=(
            "*" + nome + ", voce chegou no lugar certo!* \U0001f525\n\n"
            "Assiste esse video ate o final antes de continuar. \U0001f446\n\n"
            "O que voce vai ver aqui vai mudar tudo."
        ),
        parse_mode="Markdown",
    )

    await update.message.reply_text(
        "\U0001f44b Ola, *" + nome + "!* Que bom ter voce aqui!\n\n"
        "Meu nome e *Max* \U0001f9e0 — mentor de financas, trade, cripto e negocios online.\n\n"
        "Voce acabou de entrar num dos lugares mais valiosos que vai encontrar. \U0001f3af\n\n"
        "\u2705 Trade e analise de mercado\n"
        "\u2705 Bitcoin e criptomoedas\n"
        "\u2705 Investimentos inteligentes\n"
        "\u2705 Negocios online e renda passiva\n"
        "\u2705 Mentalidade financeira de alto nivel\n\n"
        "\U0001f4a1 *O que queres saber hoje? Usa o menu abaixo:*",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )

# ════════════════════════════════════════════
#  /menu
# ════════════════════════════════════════════
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "\U0001f4cb *Menu Principal — Max*\n\nEscolhe uma opcao:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )

# ════════════════════════════════════════════
#  /preco
# ════════════════════════════════════════════
async def preco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ A buscar precos ao vivo...")
    data = get_crypto_prices()
    msg = format_price_message(data)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Atualizar", callback_data="preco"),
        InlineKeyboardButton("🚀 Canal", url=CANAL_LINK),
    ]])
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)

# ════════════════════════════════════════════
#  /dica
# ════════════════════════════════════════════
async def dica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dica_txt = get_dica()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("💡 Outra dica", callback_data="dica"),
        InlineKeyboardButton("🚀 Canal", url=CANAL_LINK),
    ]])
    await update.message.reply_text(
        f"{dica_txt}\n\n_— Max, mentor de trade_",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

# ════════════════════════════════════════════
#  /ajuda
# ════════════════════════════════════════════
async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "*Comandos disponíveis:*\n\n"
        "/start — Iniciar o bot\n"
        "/menu — Menu principal\n"
        "/preco — Preços cripto ao vivo\n"
        "/dica — Dica de trade do dia\n"
        "/ajuda — Ver esta mensagem\n\n"
        "Ou simplesmente *envia uma mensagem* e o Max responde! 🤖"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ════════════════════════════════════════════
#  /stats — ADMIN ONLY
# ════════════════════════════════════════════
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = load_users()
    total = len(users)
    hoje = datetime.now().strftime("%d/%m/%Y")
    novos_hoje = sum(1 for u in users.values() if u.get("joined", "").startswith(hoje))
    msg = (
        f"📊 *Estatísticas do Bot*\n\n"
        f"👥 Total de usuários: *{total}*\n"
        f"🆕 Novos hoje: *{novos_hoje}*\n"
        f"📅 Data: {hoje}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ════════════════════════════════════════════
#  /broadcast — ADMIN ONLY
# ════════════════════════════════════════════
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Uso: /broadcast Mensagem aqui")
        return
    msg = " ".join(context.args)
    users = load_users()
    enviados = 0
    falhas = 0
    for uid, udata in users.items():
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=f"📢 *Mensagem do Max:*\n\n{msg}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🚀 Acessar Canal", url=CANAL_LINK)
                ]])
            )
            enviados += 1
            await asyncio.sleep(0.05)
        except:
            falhas += 1
    await update.message.reply_text(
        f"✅ Broadcast concluído\n📤 Enviados: {enviados}\n❌ Falhas: {falhas}"
    )

# ════════════════════════════════════════════
#  CALLBACK QUERY HANDLER (botões inline)
# ════════════════════════════════════════════
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "preco":
        data_cripto = get_crypto_prices()
        msg = format_price_message(data_cripto)
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Atualizar", callback_data="preco"),
            InlineKeyboardButton("🚀 Canal", url=CANAL_LINK),
        ]])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    elif data == "dica":
        dica_txt = get_dica()
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("💡 Outra dica", callback_data="dica"),
            InlineKeyboardButton("🚀 Canal", url=CANAL_LINK),
        ]])
        await query.edit_message_text(
            f"{dica_txt}\n\n_— Max, mentor de trade_",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    elif data == "falar":
        await query.edit_message_text(
            "\U0001f4ac *Pode falar! Escreve a tua pergunta...*",
            parse_mode="Markdown",
        )

    elif data == "sobre":
        msg = (
            "*Quem é o Max?* 🧠\n\n"
            "Sou mentor especializado em trade, cripto, investimentos e negocios digitais.\n\n"
            "Ja ajudei milhares de pessoas a entenderem o mercado e construirem liberdade financeira.\n\n"
            "Podes me perguntar qualquer coisa — estou aqui 24h. 🔥"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 Entrar no Canal", url=CANAL_LINK),
            InlineKeyboardButton("🔙 Menu", callback_data="menu"),
        ]])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=keyboard)

    elif data == "menu":
        await query.edit_message_text(
            "\U0001f4cb *Menu Principal — Max*\n\nEscolhe uma opcao:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

# ════════════════════════════════════════════
#  RESPOSTAS IA — GPT-4o-mini
# ════════════════════════════════════════════
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    texto = update.message.text

    if is_rate_limited(user.id):
        return

    register_user(user)

    if user.id not in historico:
        historico[user.id] = []

    historico[user.id].append({"role": "user", "content": texto})

    if len(historico[user.id]) > 30:
        historico[user.id] = historico[user.id][-30:]

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    resposta = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + historico[user.id],
        temperature=0.85,
        max_tokens=600,
    )

    texto_resposta = resposta.choices[0].message.content
    historico[user.id].append({"role": "assistant", "content": texto_resposta})

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f4e2 Acessar o Canal do Max", url=CANAL_LINK)],
        [InlineKeyboardButton("\U0001f4cb Menu", callback_data="menu")],
    ])

    await update.message.reply_text(
        texto_resposta,
        reply_markup=keyboard,
    )

# ════════════════════════════════════════════
#  GET VIDEO FILE_ID
# ════════════════════════════════════════════
async def get_video_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        fid = update.message.video.file_id
        await update.message.reply_text("file_id do video:\n" + fid)
        logger.info("file_id: %s", fid)

# ════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("menu",      menu))
    app.add_handler(CommandHandler("preco",     preco))
    app.add_handler(CommandHandler("dica",      dica))
    app.add_handler(CommandHandler("ajuda",     ajuda))
    app.add_handler(CommandHandler("stats",     stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.VIDEO, get_video_id))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    logger.info("Bot Max Pro rodando...")
    app.run_polling()


if __name__ == "__main__":
    main()
