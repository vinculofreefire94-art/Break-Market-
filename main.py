import telebot
import ccxt
import time
import threading
import os
from datetime import datetime, timezone

# ==========================================
# 1. CONFIGURAÇÕES E VARIÁVEIS DE AMBIENTE
# ==========================================
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Chaves da Binance (Opcional para simulação, obrigatório para real)
API_KEY = os.getenv('BINANCE_API_KEY', '')
API_SECRET = os.getenv('BINANCE_SECRET', '')

if not TOKEN or not CHAT_ID:
    print("[ERRO] Variáveis TELEGRAM_BOT_TOKEN ou CHAT_ID não configuradas!")
    exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
bot.remove_webhook()
time.sleep(1)

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
})

# ==========================================
# 2. PARÂMETROS DO SMART GRID
# ==========================================
SYMBOL = 'BTC/USDT'
GRID_LEVELS = 5          # Número de ordens de compra e de venda
GRID_STEP_PERCENT = 0.5  # Distância entre as ordens (0.5%)
TRADE_SIZE_USD = 20      # Tamanho de cada ordem (Ex: $20)

# Memória virtual do bot
grid_state = {
    'ativo': False,
    'preco_base': 0,
    'ordens_compra': [],
    'ordens_venda': [],
    'lucro_simulado': 0,
    'trades_executados': 0
}

lock = threading.Lock()

# ==========================================
# 3. LÓGICA CORE DO BOT
# ==========================================
def get_current_price():
    try:
        ticker = exchange.fetch_ticker(SYMBOL)
        return ticker['last']
    except Exception as e:
        print(f"[ERRO] Falha ao buscar preço: {e}")
        return None

def calculate_grids(current_price):
    """Calcula os níveis de preço da grade"""
    buy_grids = []
    sell_grids = []
    
    for i in range(1, GRID_LEVELS + 1):
        buy_price = current_price * (1 - (GRID_STEP_PERCENT / 100) * i)
        sell_price = current_price * (1 + (GRID_STEP_PERCENT / 100) * i)
        
        buy_grids.append(buy_price)
        sell_grids.append(sell_price)
        
    return sorted(buy_grids, reverse=True), sorted(sell_grids)

def start_grid():
    """Inicia a grade com o preço atual"""
    with lock:
        price = get_current_price()
        if not price: return False
        
        buys, sells = calculate_grids(price)
        
        grid_state['ativo'] = True
        grid_state['preco_base'] = price
        grid_state['ordens_compra'] = buys
        grid_state['ordens_venda'] = sells
        
        # PARA OPERAR REAL: Aqui você faria um loop usando exchange.create_limit_buy_order()
        
        msg = (
            f"🕸️ <b>SMART GRID INICIADO</b>\n"
            f"Ativo: {SYMBOL}\n"
            f"Preço Base: ${price:,.2f}\n"
            f"Níveis: {GRID_LEVELS} acima / {GRID_LEVELS} abaixo\n"
            f"Espaçamento: {GRID_STEP_PERCENT}%\n"
            f"Capital por nível: ${TRADE_SIZE_USD}\n"
            f"<code>Bot operando em modo Virtual/Simulado</code>"
        )
        bot.send_message(CHAT_ID, msg)
        return True

def monitor_grid():
    """Roda em loop infinito monitorando se o preço bateu nas grades"""
    while True:
        if not grid_state['ativo']:
            time.sleep(5)
            continue
            
        current_price = get_current_price()
        if not current_price:
            time.sleep(5)
            continue
            
        with lock:
            # Verifica Ordens de Venda (Se preço subiu)
            for sell_price in grid_state['ordens_venda'][:]:
                if current_price >= sell_price:
                    lucro = TRADE_SIZE_USD * (GRID_STEP_PERCENT/100)
                    grid_state['lucro_simulado'] += lucro
                    grid_state['trades_executados'] += 1
                    grid_state['ordens_venda'].remove(sell_price)
                    
                    # Cria nova ordem de compra no nível de baixo
                    new_buy = sell_price * (1 - (GRID_STEP_PERCENT/100))
                    grid_state['ordens_compra'].append(new_buy)
                    grid_state['ordens_compra'].sort(reverse=True)
                    
                    msg = f"✅ <b>VENDA EXECUTADA (Take Profit)</b>\nPreço: ${sell_price:,.2f}\nLucro acumulado: ${grid_state['lucro_simulado']:.2f}"
                    bot.send_message(CHAT_ID, msg)

            # Verifica Ordens de Compra (Se preço caiu)
            for buy_price in grid_state['ordens_compra'][:]:
                if current_price <= buy_price:
                    grid_state['trades_executados'] += 1
                    grid_state['ordens_compra'].remove(buy_price)
                    
                    # Cria nova ordem de venda no nível de cima
                    new_sell = buy_price * (1 + (GRID_STEP_PERCENT/100))
                    grid_state['ordens_venda'].append(new_sell)
                    grid_state['ordens_venda'].sort()
                    
                    msg = f"📉 <b>COMPRA EXECUTADA (Aproveitando queda)</b>\nPreço: ${buy_price:,.2f}"
                    bot.send_message(CHAT_ID, msg)
                    
        time.sleep(3) # Checa a cada 3 segundos

# ==========================================
# 4. COMANDOS DO TELEGRAM
# ==========================================
@bot.message_handler(commands=['start', 'ajuda'])
def cmd_start(msg):
    texto = (
        "🤖 <b>SMART GRID BOT ONLINE</b>\n\n"
        "/ligar - Monta a grade a partir do preço atual\n"
        "/desligar - Para o monitoramento\n"
        "/status - Mostra lucro, ordens ativas e preço real"
    )
    bot.send_message(msg.chat.id, texto)

@bot.message_handler(commands=['ligar'])
def cmd_ligar(msg):
    if grid_state['ativo']:
        bot.send_message(msg.chat.id, "⚠️ A grade já está ligada!")
    else:
        start_grid()

@bot.message_handler(commands=['desligar'])
def cmd_desligar(msg):
    with lock:
        grid_state['ativo'] = False
        bot.send_message(msg.chat.id, "🛑 <b>Grid Bot Parado.</b>")

@bot.message_handler(commands=['status'])
def cmd_status(msg):
    price = get_current_price()
    st = grid_state
    
    if not st['ativo']:
        bot.send_message(msg.chat.id, f"😴 Bot desligado. Preço atual do BTC: ${price:,.2f}")
        return
        
    texto = (
        f"📊 <b>STATUS DO GRID BOT</b>\n"
        f"<code>======================</code>\n"
        f"💵 Preço Atual: <b>${price:,.2f}</b>\n"
        f"🔄 Trades Realizados: {st['trades_executados']}\n"
        f"💰 Lucro Virtual: <b>${st['lucro_simulado']:.2f}</b>\n"
        f"<code>======================</code>\n"
        f"<b>Próxima Venda:</b> ${st['ordens_venda'][0]:,.2f} se subir\n"
        f"<b>Próxima Compra:</b> ${st['ordens_compra'][0]:,.2f} se cair\n"
    )
    bot.send_message(msg.chat.id, texto)

# ==========================================
# 5. INICIALIZAÇÃO
# ==========================================
if __name__ == '__main__':
    print("🚀 Iniciando Smart Grid Bot...")
    bot.send_message(CHAT_ID, "🚀 <b>Smart Grid Bot Iniciado no Railway!</b>\nDigite /ligar para começar as operações.")
    
    # Inicia a thread que fica checando os preços 24/7
    threading.Thread(target=monitor_grid, daemon=True).start()
    
    # Inicia a thread que recebe os comandos do Telegram
    while True:
        try:
            bot.polling(non_stop=True, timeout=60)
        except Exception as e:
            print(f"Erro no polling: {e}")
            time.sleep(5)
