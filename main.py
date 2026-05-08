import os
import json
import logging
import asyncio
import random
from datetime import datetime

import requests
from openai import AsyncOpenAI  # ← AsyncOpenAI para evitar conflito com asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)

# ════════════════════════════════════════════
#  CONFIGURAÇÕES — variáveis de ambiente
# ════════════════════════════════════════════
BOT_TOKEN  = os.environ.get("BOT_TOKEN", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
VIDEO_ID   = os.environ.get("VIDEO_ID", "")
CANAL_LINK = os.environ.get("CANAL_LINK", "https://t.me/clesstrade")
ADMIN_ID   = int(os.environ.get("ADMIN_ID", "0"))

# ════════════════════════════════════════════
#  LOGGING
# ════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════
#  OPENAI — cliente assíncrono
# ════════════════════════════════════════════
client = AsyncOpenAI(api_key=OPENAI_KEY)

# ════════════════════════════════════════════
#  BANCO DE DADOS LOCAL (users.json)
# ════════════════════════════════════════════
USERS_FILE = "users.json"

def load_users() -> dict:
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_users(users: dict) -> None:
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def register_user(user) -> None:
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
    else:
        users[uid]["messages"] = users[uid].get("messages", 0) + 1
    save_users(users)

# ════════════════════════════════════════════
#  ANTI-SPAM (rate limit)
# ════════════════════════════════════════════
last_message_time: dict[int, float] = {}
RATE_LIMIT_SECONDS = 3

def is_rate_limited(user_id: int) -> bool:
    now = datetime.now().timestamp()
    if now - last_message_time.get(user_id, 0) < RATE_LIMIT_SECONDS:
        return True
    last_message_time[user_id] = now
    return False

# ════════════════════════════════════════════
#  HISTÓRICO DE CONVERSAS
# ════════════════════════════════════════════
historico: dict[int, list] = {}

# ════════════════════════════════════════════
#  PREÇOS CRIPTO — CoinGecko (grátis)
# ════════════════════════════════════════════
def get_crypto_prices() -> dict | None:
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "bitcoin,ethereum,solana,binancecoin,ripple",
                "vs_currencies": "usd",
                "include_24hr_change": "true",
            },
            timeout=8,
        )
        return r.json()
    except Exception:
        return None

def format_price_message(data: dict | None) -> str:
    if not data:
        return "Preços indisponíveis no momento."
    coins = [
        ("bitcoin",     "₿  Bitcoin",  "BTC"),
        ("ethereum",    "Ξ  Ethereum",  "ETH"),
        ("solana",      "◎  Solana",    "SOL"),
        ("binancecoin", "⬡  BNB",       "BNB"),
        ("ripple",      "✦  XRP",       "XRP"),
    ]
    lines = []
    for cid, label, _ in coins:
        if cid in data:
            price  = data[cid]["usd"]
            change = data[cid].get("usd_24h_change", 0)
            arrow  = "🟢 ▲" if change >= 0 else "🔴 ▼"
            lines.append(f"{arrow} *{label}*\n   `${price:,.2f}`  ({change:+.2f}%)\n")
    now = datetime.now().strftime("%H:%M")
    return (
        f"📊 *PREÇOS AO VIVO — {now}*\n{'─'*30}\n"
        + "\n".join(lines)
        + f"{'─'*30}\n_Atualizado agora • Fonte: CoinGecko_"
    )

# ════════════════════════════════════════════
#  DICAS DE TRADE
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
    "📌 *RSI acima de 70?* Sobrecomprado. Abaixo de 30? Sobrevendido. Usa com cuidado.",
    "📌 *Diversifica, mas não demasiado.* Foco em poucos ativos que conheces bem.",
]

def get_dica() -> str:
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
#  TECLADOS
# ════════════════════════════════════════════
def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Preços Cripto", callback_data="preco"),
            InlineKeyboardButton("💡 Dica do Dia",   callback_data="dica"),
        ],
        [
            InlineKeyboardButton("🚀 Entrar no Canal", url=CANAL_LINK),
            InlineKeyboardButton("🤖 Falar com Max",   callback_data="falar"),
        ],
        [
            InlineKeyboardButton("❓ Sobre o Max", callback_data="sobre"),
        ],
    ])

def canal_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Acessar o Canal do Max", url=CANAL_LINK)],
        [InlineKeyboardButton("📋 Menu", callback_data="menu")],
    ])

# ════════════════════════════════════════════
#  /start
# ════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    nome = user.first_name
    register_user(user)
    historico[user.id] = []

    if VIDEO_ID:
        await update.message.reply_video(
            video=VIDEO_ID,
            caption=(
                f"*{nome}, voce chegou no lugar certo!* 🔥\n\n"
                "Assiste esse video ate o final antes de continuar. 👆\n\n"
                "O que voce vai ver aqui vai mudar tudo."
            ),
            parse_mode="Markdown",
        )

    await update.message.reply_text(
        f"👋 Ola, *{nome}!* Que bom ter voce aqui!\n\n"
        "Meu nome e *Max* 🧠 — mentor de financas, trade, cripto e negocios online.\n\n"
        "Voce acabou de entrar num dos lugares mais valiosos que vai encontrar. 🎯\n\n"
        "✅ Trade e analise de mercado\n"
        "✅ Bitcoin e criptomoedas\n"
        "✅ Investimentos inteligentes\n"
        "✅ Negocios online e renda passiva\n"
        "✅ Mentalidade financeira de alto nivel\n\n"
        "💡 *O que queres saber hoje? Usa o menu abaixo:*",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )

# ════════════════════════════════════════════
#  /menu
# ════════════════════════════════════════════
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📋 *Menu Principal — Max*\n\nEscolhe uma opcao:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )

# ════════════════════════════════════════════
#  /preco
# ════════════════════════════════════════════
async def preco(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ A buscar precos ao vivo...")
    msg = format_price_message(get_crypto_prices())
    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Atualizar", callback_data="preco"),
            InlineKeyboardButton("🚀 Canal",     url=CANAL_LINK),
        ]]),
    )

# ════════════════════════════════════════════
#  /dica
# ════════════════════════════════════════════
async def dica(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"{get_dica()}\n\n_— Max, mentor de trade_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💡 Outra dica", callback_data="dica"),
            InlineKeyboardButton("🚀 Canal",       url=CANAL_LINK),
        ]]),
    )

# ════════════════════════════════════════════
#  /ajuda
# ════════════════════════════════════════════
async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*Comandos disponíveis:*\n\n"
        "/start — Iniciar o bot\n"
        "/menu — Menu principal\n"
        "/preco — Preços cripto ao vivo\n"
        "/dica — Dica de trade do dia\n"
        "/ajuda — Ver esta mensagem\n\n"
        "Ou simplesmente *envia uma mensagem* e o Max responde! 🤖",
        parse_mode="Markdown",
    )

# ════════════════════════════════════════════
#  /stats — ADMIN ONLY
# ════════════════════════════════════════════
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    users = load_users()
    hoje  = datetime.now().strftime("%d/%m/%Y")
    novos = sum(1 for u in users.values() if u.get("joined", "").startswith(hoje))
    await update.message.reply_text(
        f"📊 *Estatísticas do Bot*\n\n"
        f"👥 Total de usuários: *{len(users)}*\n"
        f"🆕 Novos hoje: *{novos}*\n"
        f"📅 Data: {hoje}",
        parse_mode="Markdown",
    )

# ════════════════════════════════════════════
#  /broadcast — ADMIN ONLY
# ════════════════════════════════════════════
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Uso: /broadcast Mensagem aqui")
        return
    msg    = " ".join(context.args)
    users  = load_users()
    ok = fail = 0
    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=f"📢 *Mensagem do Max:*\n\n{msg}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🚀 Acessar Canal", url=CANAL_LINK)
                ]]),
            )
            ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    await update.message.reply_text(
        f"✅ Broadcast concluído\n📤 Enviados: {ok}\n❌ Falhas: {fail}"
    )

# ════════════════════════════════════════════
#  CALLBACK QUERY HANDLER
# ════════════════════════════════════════════
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data  = query.data

    if data == "preco":
        msg = format_price_message(get_crypto_prices())
        await query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Atualizar", callback_data="preco"),
                InlineKeyboardButton("🚀 Canal",     url=CANAL_LINK),
            ]]),
        )

    elif data == "dica":
        await query.edit_message_text(
            f"{get_dica()}\n\n_— Max, mentor de trade_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💡 Outra dica", callback_data="dica"),
                InlineKeyboardButton("🚀 Canal",       url=CANAL_LINK),
            ]]),
        )

    elif data == "falar":
        await query.edit_message_text(
            "💬 *Pode falar! Escreve a tua pergunta...*",
            parse_mode="Markdown",
        )

    elif data == "sobre":
        await query.edit_message_text(
            "*Quem é o Max?* 🧠\n\n"
            "Sou mentor especializado em trade, cripto, investimentos e negocios digitais.\n\n"
            "Ja ajudei milhares de pessoas a entenderem o mercado e construirem liberdade financeira.\n\n"
            "Podes me perguntar qualquer coisa — estou aqui 24h. 🔥",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚀 Entrar no Canal", url=CANAL_LINK),
                InlineKeyboardButton("🔙 Menu",            callback_data="menu"),
            ]]),
        )

    elif data == "menu":
        await query.edit_message_text(
            "📋 *Menu Principal — Max*\n\nEscolhe uma opcao:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

# ════════════════════════════════════════════
#  RESPOSTAS IA — GPT-4o-mini (async)
# ════════════════════════════════════════════
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user  = update.effective_user
    texto = update.message.text

    if is_rate_limited(user.id):
        return

    register_user(user)

    if user.id not in historico:
        historico[user.id] = []

    historico[user.id].append({"role": "user", "content": texto})

    # Mantém apenas as últimas 30 mensagens
    if len(historico[user.id]) > 30:
        historico[user.id] = historico[user.id][-30:]

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        resposta = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + historico[user.id],
            temperature=0.85,
            max_tokens=600,
        )
        texto_resposta = resposta.choices[0].message.content
    except Exception as e:
        logger.error("Erro OpenAI: %s", e)
        texto_resposta = "Desculpa, tive um problema técnico. Tenta de novo em instantes. 🔧"

    historico[user.id].append({"role": "assistant", "content": texto_resposta})

    await update.message.reply_text(
        texto_resposta,
        reply_markup=canal_menu_keyboard(),
    )

# ════════════════════════════════════════════
#  CAPTURAR file_id DE VÍDEO (setup)
# ════════════════════════════════════════════
async def get_video_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.video:
        fid = update.message.video.file_id
        await update.message.reply_text(f"file_id do video:\n`{fid}`", parse_mode="Markdown")
        logger.info("file_id: %s", fid)

# ════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════
def main() -> None:
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

    logger.info("Bot Max Pro a correr...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
