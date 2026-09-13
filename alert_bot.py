import time
import requests
import threading
from datetime import datetime

# Адреса
PZM_JETTON = "EQDROsytSxLtDp_2pRIEainUGqZPRBbXkwayVn7VAT7bHHWL"
PZM_POOL = "EQAa6k6QZCq87DyyrnIZQOZsP8xF7B3gOMKXvHD7r-pevSub"
USDT_JETTON = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
USDT_POOL = "EQA-X_yo3fzzbDbJ_0bzFWKqtRuZFIRa1sJsveZJ1YpViO3r"

# Кэш
last_lt = None
ton_usd_price = None
last_usd_update = 0


def get_ton_usd_price():
    """Получить курс TON в USD из пула TON-USDT"""
    global ton_usd_price, last_usd_update
    
    if time.time() - last_usd_update < 60:
        return ton_usd_price
    
    try:
        resp = requests.get("https://api.dedust.io/v2/pools", timeout=10)
        pools = resp.json()
        
        for p in pools:
            if p['address'] == USDT_POOL:
                reserves = p.get('reserves', [])
                assets = p.get('assets', [])
                if len(reserves) == 2 and len(assets) == 2:
                    # Определяем, какой индекс у TON, а какой у USDT
                    sym0 = (assets[0].get('metadata') or {}).get('symbol', '')
                    sym1 = (assets[1].get('metadata') or {}).get('symbol', '')
                    
                    if sym0 == 'TON' and sym1 == 'USDT':
                        ton_reserve = int(reserves[0]) / 1e9
                        usdt_reserve = int(reserves[1]) / 1e6
                    elif sym0 == 'USDT' and sym1 == 'TON':
                        ton_reserve = int(reserves[1]) / 1e9
                        usdt_reserve = int(reserves[0]) / 1e6
                    else:
                        continue
                    
                    if ton_reserve > 0:
                        ton_usd_price = usdt_reserve / ton_reserve
                        last_usd_update = time.time()
                        print(f"💵 Курс TON обновлён: ${ton_usd_price:.4f}")
                        return ton_usd_price
        print("⚠️ Не найден пул TON-USDT")
        return ton_usd_price
    except Exception as e:
        print(f"❌ Ошибка получения курса TON: {e}")
        return ton_usd_price


def get_pzm_course():
    """Получить курс PZM в TON из резервов пула TON-PZM"""
    try:
        resp = requests.get("https://api.dedust.io/v2/pools", timeout=10)
        pools = resp.json()
        
        for p in pools:
            if p['address'] == PZM_POOL:
                reserves = p.get('reserves', [])
                assets = p.get('assets', [])
                if len(reserves) == 2 and len(assets) == 2:
                    sym0 = (assets[0].get('metadata') or {}).get('symbol', '')
                    
                    if sym0 == 'TON':
                        ton_reserve = int(reserves[0]) / 1e9
                        pzm_reserve = int(reserves[1]) / 100
                    else:
                        ton_reserve = int(reserves[1]) / 1e9
                        pzm_reserve = int(reserves[0]) / 100
                    
                    if pzm_reserve > 0:
                        return ton_reserve / pzm_reserve
        return None
    except Exception as e:
        print(f"❌ Ошибка получения курса PZM: {e}")
        return None


def monitor_trades():
    """Поток-монитор: раз в 30 секунд забирает новые сделки"""
    global last_lt
    
    print("🚀 Монитор сделок запущен...")
    print(f"📍 Пул TON-PZM: {PZM_POOL}")
    
    # Получаем начальное значение lt
    try:
        resp = requests.get(f"https://api.dedust.io/v2/pools/{PZM_POOL}/trades?page_size=1", timeout=10)
        trades = resp.json()
        if trades:
            last_lt = int(trades[0]['lt'])
            print(f"📊 Начальная lt: {last_lt}")
            print(f"📅 Последняя сделка: {trades[0]['createdAt']}")
        else:
            print("⚠️ Нет сделок в истории")
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
    
    # Получаем курс TON в USD один раз при старте
    get_ton_usd_price()
    
    while True:
        try:
            url = f"https://api.dedust.io/v2/pools/{PZM_POOL}/trades?page_size=10"
            if last_lt:
                url += f"&after_lt={last_lt}"
            
            resp = requests.get(url, timeout=10)
            trades = resp.json()
            
            if trades:
                for trade in reversed(trades):
                    process_trade(trade)
                    last_lt = int(trade['lt'])
            
        except Exception as e:
            print(f"❌ Ошибка мониторинга: {e}")
        
        time.sleep(30)


def process_trade(trade):
    """Обработать одну сделку"""
    try:
        asset_in = trade['assetIn']
        asset_out = trade['assetOut']
        
        is_buy_pzm = asset_in.get('type') == 'native'  # TON → PZM = покупка
        
        if is_buy_pzm:
            amount_ton = int(trade['amountIn']) / 1e9
            amount_pzm = int(trade['amountOut']) / 100
        else:
            amount_ton = int(trade['amountOut']) / 1e9
            amount_pzm = int(trade['amountIn']) / 100
        
        pzm_in_ton = get_pzm_course()
        ton_usd = get_ton_usd_price()
        pzm_in_usd = pzm_in_ton * ton_usd if (pzm_in_ton and ton_usd) else None
        
        created = datetime.fromisoformat(trade['createdAt'].replace('Z', '+00:00'))
        time_str = created.strftime("%d.%m %H:%M:%S")
        
        direction = "🟢 Покупка" if is_buy_pzm else "🔴 Продажа"
        
        print(f"\n{'='*50}")
        print(f"{direction} PZM на DeDust")
        print(f"💰 {amount_pzm:,.2f} PZM за {amount_ton:.4f} TON")
        if pzm_in_ton:
            print(f"💵 Курс PZM: {pzm_in_ton:.6f} TON")
        if pzm_in_usd:
            print(f"💵 Курс PZM в USD: ${pzm_in_usd:.6f}")
        print(f"🕒 {time_str}")
        
    except Exception as e:
        print(f"❌ Ошибка обработки сделки: {e}")


if __name__ == "__main__":
    print("🚀 Prizm Alert Bot Monitor")
    print("=" * 50)
    
    monitor_thread = threading.Thread(target=monitor_trades, daemon=True)
    monitor_thread.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Монитор остановлен")