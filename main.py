# """
AURUM AI v3.0 — Bot Trading XAUUSD

Commandes Telegram:
/start    - Démarrer
/status   - État du marché maintenant
/analyse  - Détail des conditions setup
/prix     - Prix actuel XAU/USD
/signaux  - Historique des signaux
/help     - Aide
"""

import requests
import time
import schedule
import threading
from datetime import datetime

# ============================================================

# ⚙️  CONFIGURATION

# ============================================================

TELEGRAM_TOKEN  = "8303225616:AAEMehY3iBh07uHpjvaJaXVjN0yjZp3MPl0"
CHAT_ID         = "5954932933"
TWELVE_DATA_KEY = "2e83e0f661d94cba9c3b6ac467bc8ca4"

SYMBOL   = "XAU/USD"
INTERVAL = "1h"
MAX_SL   = 200
MIN_RR   = 2.0
MIN_PROB = 70

last_signal_time = None
signal_history   = []
last_update_id   = 0

# ============================================================

# 📡 DONNÉES MARCHÉ

# ============================================================

def get_market_data():
    try:
        url = (
            f"https://api.twelvedata.com/time_series"
            f"?symbol={SYMBOL}&interval={INTERVAL}&outputsize=50"
            f"&apikey={TWELVE_DATA_KEY}"
        )
        r = requests.get(url, timeout=10)
        data = r.json()
        if "values" not in data:
            print(f"[API] Erreur: {data.get('message','?')}")
            return None
        candles = data["values"]
        closes = [float(c["close"]) for c in reversed(candles)]
        highs  = [float(c["high"])  for c in reversed(candles)]
        lows   = [float(c["low"])   for c in reversed(candles)]
        opens  = [float(c["open"])  for c in reversed(candles)]
        return {"close": closes, "high": highs, "low": lows, "open": opens}
    except Exception as e:
        print(f"[ERREUR] get_market_data: {e}")
        return None

# ============================================================

# 🔬 INDICATEURS

# ============================================================

def calc_ema(prices, period):
    k = 2 / (period + 1)
    ema = [prices[0]]
    for p in prices[1:]:
        ema.append(p * k + ema[-1] * (1 - k))
    return ema

def calc_rsi(closes, period=14):
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    if len(gains) < period:
        return 50.0
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calc_macd(closes):
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    macd_line   = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
    signal_line = calc_ema(macd_line, 9)
    histogram   = [m - s for m, s in zip(macd_line, signal_line)]
    return macd_line, signal_line, histogram

def calc_atr(highs, lows, closes, period=14):
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        trs.append(tr)
    if len(trs) < period:
        return 15.0
    return round(sum(trs[-period:]) / period, 2)

def detect_candle_pattern(opens, closes, highs, lows):
    if len(opens) < 3:
        return "Aucun", 0
    o1, c1       = opens[-3], closes[-3]
    o2, c2, h2, l2 = opens[-2], closes[-2], highs[-2], lows[-2]
    body2 = abs(c2 - o2)

    if c1 < o1 and c2 > o2 and c2 > o1 and o2 < c1:
        return "Englobante Haussiere", 1
    if c1 > o1 and c2 < o2 and c2 < o1 and o2 > c1:
        return "Englobante Baissiere", -1
    if c2 > o2 and body2 > 0:
        if (o2 - l2) > body2 * 2 and (h2 - c2) < body2 * 0.5:
            return "Marteau", 1
    if c2 < o2 and body2 > 0:
        if (h2 - o2) > body2 * 2 and (c2 - l2) < body2 * 0.5:
            return "Etoile Filante", -1
    if body2 < (h2 - l2) * 0.1:
        return "Doji", 0
    return "Aucun", 0

# ============================================================

# 🎯 ANALYSE COMPLÈTE

# ============================================================

def get_full_analysis():
    data = get_market_data()
    if not data:
        return None, None

    closes = data["close"]
    highs  = data["high"]
    lows   = data["low"]
    opens  = data["open"]

    rsi               = calc_rsi(closes)
    macd, sig_line, hist = calc_macd(closes)
    ema20             = calc_ema(closes, 20)
    ema50             = calc_ema(closes, 50)
    atr               = calc_atr(highs, lows, closes)
    pattern, pat_dir  = detect_candle_pattern(opens, closes, highs, lows)

    price     = closes[-1]
    ema20_now = ema20[-1]
    ema50_now = ema50[-1]
    macd_now  = macd[-1]
    hist_now  = hist[-1]
    hist_prev = hist[-2] if len(hist) > 1 else 0
    sig_now   = sig_line[-1]
    proximity = abs(price - ema20_now) / atr if atr > 0 else 99

    buy_checks = [
        (price > ema20_now > ema50_now,
         "Tendance haussiere Prix > EMA20 > EMA50",
         f"Prix={price:.2f} EMA20={ema20_now:.2f} EMA50={ema50_now:.2f}"),
        (45 <= rsi <= 65,
         "RSI entre 45-65 (momentum sain)",
         f"RSI = {rsi}"),
        (macd_now > sig_now and hist_now > hist_prev,
         "MACD croisement haussier",
         f"MACD={macd_now:.3f} Hist={hist_now:.3f}"),
        (proximity < 0.8,
         "Prix proche EMA 20 (rebond)",
         f"Distance = {proximity:.2f}x ATR"),
        (pat_dir == 1,
         f"Pattern haussier detecte",
         f"Pattern = {pattern}"),
    ]

    sell_checks = [
        (price < ema20_now and ema20_now < ema50_now,
         "Tendance baissiere Prix < EMA20 < EMA50",
         f"Prix={price:.2f} EMA20={ema20_now:.2f} EMA50={ema50_now:.2f}"),
        (55 <= rsi <= 75,
         "RSI entre 55-75 (momentum baissier)",
         f"RSI = {rsi}"),
        (macd_now < sig_now and hist_now < hist_prev,
         "MACD croisement baissier",
         f"MACD={macd_now:.3f} Hist={hist_now:.3f}"),
        (proximity < 0.8 and price < ema20_now,
         "Prix proche EMA 20 (rejet)",
         f"Distance = {proximity:.2f}x ATR"),
        (pat_dir == -1,
         f"Pattern baissier detecte",
         f"Pattern = {pattern}"),
    ]

    buy_score  = sum(1 for c in buy_checks  if c[0])
    sell_score = sum(1 for c in sell_checks if c[0])

    analysis = {
        "price": price, "ema20": ema20_now, "ema50": ema50_now,
        "rsi": rsi, "macd": macd_now, "atr": atr, "pattern": pattern,
        "pat_dir": pat_dir, "buy_checks": buy_checks,
        "sell_checks": sell_checks, "buy_score": buy_score,
        "sell_score": sell_score,
    }

    signal = None
    for direction, score, checks in [("BUY", buy_score, buy_checks), ("SELL", sell_score, sell_checks)]:
        if score >= 3:
            prob = min(score * 19 + 5, 95)
            if prob >= MIN_PROB:
                sl_dist = atr * 1.5
                tp_dist = sl_dist * MIN_RR
                if direction == "BUY":
                    sl = round(price - sl_dist, 2)
                    tp = round(price + tp_dist, 2)
                else:
                    sl = round(price + sl_dist, 2)
                    tp = round(price - tp_dist, 2)
                signal = {
                    "direction": direction,
                    "entry": round(price, 2),
                    "stop_loss": sl, "take_profit": tp,
                    "sl_pips": round(sl_dist, 1),
                    "tp_pips": round(tp_dist, 1),
                    "rr": MIN_RR, "probability": prob,
                    "rsi": rsi, "macd": round(macd_now, 3),
                    "pattern": pattern,
                    "reasons": [c[1] for c in checks if c[0]],
                    "time": datetime.utcnow().strftime("%H:%M:%S GMT"),
                }
                break

    return analysis, signal

# ============================================================

# 📱 TELEGRAM

# ============================================================

def send_telegram(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"[TG ERR] {e}")

def get_updates():
    global last_update_id
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"offset": last_update_id + 1, "timeout": 5},
            timeout=10
        )
        data = r.json()
        if data.get("ok"):
            return data.get("result", [])
    except:
        pass
    return []

# ============================================================

# 💬 COMMANDES

# ============================================================
def cmd_help(chat_id):
    send_telegram(chat_id, """
<b>AURUM AI v3.0 - Commandes</b>

/status   - Etat du marche maintenant
/analyse  - Detail conditions setup
/prix     - Prix actuel XAU/USD
/signaux  - Derniers signaux
/help     - Cette liste

Le bot surveille automatiquement et envoie une alerte des qu un setup BUY ou SELL est confirme!
""".strip())

def cmd_prix(chat_id):
    data = get_market_data()
    if not data:
        send_telegram(chat_id, "Erreur recuperation prix.")
        return
    price = data["close"][-1]
    prev  = data["close"][-2]
    diff  = round(price - prev, 2)
    arrow = "UP" if diff >= 0 else "DOWN"
    sign  = "+" if diff >= 0 else ""
    send_telegram(chat_id, f"""
<b>XAU/USD - Prix temps reel</b>

Prix actuel : <b>{price:.2f}</b>
Variation   : {sign}{diff} ({sign}{round(diff/prev*100,2)}%)
Direction   : {arrow}
Heure       : {datetime.utcnow().strftime("%H:%M:%S GMT")}
""".strip())

def cmd_status(chat_id):
    send_telegram(chat_id, "Analyse en cours…")
    analysis, signal = get_full_analysis()
    if not analysis:
        send_telegram(chat_id, "Erreur recuperation donnees.")
        return

    buy  = analysis["buy_score"]
    sell = analysis["sell_score"]

    if signal:
        etat = f"SETUP {signal['direction']} ACTIF - Signal envoye!"
    elif buy >= 2:
        etat = f"Setup BUY en formation ({buy}/5) - Presque pret!"
    elif sell >= 2:
        etat = f"Setup SELL en formation ({sell}/5) - Presque pret!"
    else:
        etat = "Marche calme - Pas de setup en vue"

    send_telegram(chat_id, f"""
<b>STATUS MARCHE - XAU/USD</b>
Heure : {datetime.utcnow().strftime("%H:%M GMT")}

Prix   : <b>{analysis['price']:.2f}</b>
RSI    : {analysis['rsi']}
MACD   : {analysis['macd']:.3f}
EMA20  : {analysis['ema20']:.2f}
EMA50  : {analysis['ema50']:.2f}
Bougie : {analysis['pattern']}

Score BUY  : {buy}/5
Score SELL : {sell}/5

{etat}

Tape /analyse pour le detail complet
""".strip())

def cmd_analyse(chat_id):
    send_telegram(chat_id, "Analyse detaillee en cours… 5 secondes")
    analysis, signal = get_full_analysis()
    if not analysis:
        send_telegram(chat_id, "Erreur recuperation donnees.")
        return

    buy  = analysis["buy_score"]
    sell = analysis["sell_score"]

    if buy >= sell:
        checks    = analysis["buy_checks"]
        direction = "BUY"
        score     = buy
    else:
        checks    = analysis["sell_checks"]
        direction = "SELL"
        score     = sell

    lines = []
    for ok, label, detail in checks:
        icon = "OK" if ok else "NON"
        lines.append(f"{icon} - {label}\n     {detail}")

    manque = 3 - score
    if signal:
        conclusion = f"SETUP {direction} CONFIRME! Signal envoye sur Telegram!"
    elif manque <= 0:
        conclusion = "Setup presque pret - en attente confirmation bougie"
    else:
        conclusion = f"Il manque encore {manque} condition(s) sur 5"

    send_telegram(chat_id, f"""
<b>ANALYSE COMPLETE - {direction}</b>
Heure : {datetime.utcnow().strftime("%H:%M GMT")}

Prix  : {analysis['price']:.2f}
ATR   : {analysis['atr']}

<b>Conditions ({score}/5) :</b>

{chr(10).join(lines)}

{conclusion}
""".strip())

def cmd_signaux(chat_id):
    if not signal_history:
        send_telegram(chat_id, "Aucun signal envoye pour l instant.\n\nLe bot surveille - tu recevras une alerte des qu un setup est detecte!")
        return
    msg = "<b>Derniers signaux :</b>\n\n"
    for s in signal_history[-5:]:
        msg += f"{s['direction']} - {s['time']}\n"
        msg += f"Entree: {s['entry']} | SL: {s['stop_loss']} | TP: {s['take_profit']}\n"
        msg += f"R/R: 1:{s['rr']} | Prob: {s['probability']}%\n\n"
    send_telegram(chat_id, msg.strip())

# ============================================================

# 🔄 COMMANDES LOOP

# ============================================================
def process_commands():
    global last_update_id
    updates = get_updates()
    for update in updates:
        last_update_id = update["update_id"]
        if "message" not in update:
            continue
        msg  = update["message"]
        text = msg.get("text", "").strip().lower()
        chat = str(msg["chat"]["id"])
        print(f"[CMD] '{text}' de {chat}")
        if   text in ["/start", "/help"]: cmd_help(chat)
        elif text == "/prix":             cmd_prix(chat)
        elif text == "/status":           cmd_status(chat)
        elif text == "/analyse":          cmd_analyse(chat)
        elif text == "/signaux":          cmd_signaux(chat)
        else:
            send_telegram(chat, "Commande inconnue. Tape /help")

# ============================================================

# 🎯 ANALYSE AUTO (toutes les 5 min)

# ============================================================
def run_analysis():
    global last_signal_time
    now = datetime.utcnow().strftime("%H:%M:%S")
    print(f"\n[{{now}}] Analyse XAUUSD…")

    analysis, signal = get_full_analysis()
    if not analysis:
        print(f"[{{now}}] Donnees indisponibles")
        return

    print(f"[{{now}}] BUY:{{analysis['buy_score']}}/5 SELL:{{analysis['sell_score']}}/5 RSI:{{analysis['rsi']}} Prix:{{analysis['price']:.2f}}")

    if signal:
        current_time = time.time()
        if last_signal_time and (current_time - last_signal_time) < 3600:
            print(f"[{{now}}] Doublon ignore")
            return

        arrow   = "UP" if signal["direction"] == "BUY" else "DOWN"
        color   = "ACHAT" if signal["direction"] == "BUY" else "VENTE"
        reasons = "\n".join([f"OK - {{r}}" for r in signal["reasons"]])

        message = f"""
AURUM AI - SIGNAL {{signal['direction']}} {{arrow}}

Paire : XAU/USD (Or)
Heure : {{signal['time']}}

ENTREE      : <b>{{signal['entry']}}</b>
STOP LOSS   : {{signal['stop_loss']}}  (-{{signal['sl_pips']}} pips)
TAKE PROFIT : {{signal['take_profit']}}  (+{{signal['tp_pips']}} pips)

Risk/Reward : 1:{{signal['rr']}}
Probabilite : {{signal['probability']}}%

Pourquoi ce signal :
{{reasons}}

Signal informatif - Gerez votre risque. AURUM AI v3.0
""".strip()

        send_telegram(CHAT_ID, message)
        signal_history.append(signal)
        last_signal_time = current_time
        print(f"[{{now}}] Signal {{signal['direction']}} envoye!")
    else:
        print(f"[{{now}}] Pas de setup. Prochaine analyse dans 5 min.")

# ============================================================

# ▶️  MAIN

# ============================================================

if __name__ == "__main__":
    print("=" * 45)
    print("  AURUM AI v3.0 - Bot Trading XAUUSD")
    print("=" * 45)

    send_telegram(CHAT_ID, """
AURUM AI v3.0 demarre!

Surveillance XAUUSD active 24h/24
Analyse automatique toutes les 5 min
Seuil : probabilite 70% minimum

Commandes disponibles :
/status   - Etat du marche
/analyse  - Detail conditions
/prix     - Prix actuel
/signaux  - Historique
/help     - Aide

Tu recevras une alerte des qu un setup est confirme!
""".strip())

    run_analysis()
    schedule.every(5).minutes.do(run_analysis)

    print("[BOT] Surveillance active + commandes Telegram")

    while True:
        schedule.run_pending()
        process_commands()
        time.sleep(2)