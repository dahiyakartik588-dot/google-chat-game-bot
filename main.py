from flask import Flask, request, jsonify
import random
import json

app = Flask(__name__)

# ─── In-memory game state ───────────────────────────────────────────────
games = {}  # { space_id: { game, players, state } }

# ─── Card Utilities ─────────────────────────────────────────────────────
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
RANK_VALUES = {"A": 11, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
               "7": 7, "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10}

def new_deck():
    deck = [f"{r}{s}" for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck

def card_value(card):
    return RANK_VALUES[card[:-1]] if len(card) > 2 else RANK_VALUES[card[0]]

def hand_total(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c[0] == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def fmt_hand(hand):
    return " ".join(hand)

# ─── Help Message ────────────────────────────────────────────────────────
HELP_TEXT = """🎮 *Card & Dice Game Bot* — Commands:

🃏 *Blackjack*
  `/blackjack` — Start a game
  `/hit` — Draw a card
  `/stand` — Hold your hand

🎲 *Dice Duel*
  `/dice` — Roll dice (highest wins!)
  `/dice 3` — Roll 3 dice

🎴 *Higher or Lower*
  `/hol` — Start Higher or Lower
  `/higher` or `/lower` — Make your guess

ℹ️ `/help` — Show this menu"""

# ─── Command Handler ─────────────────────────────────────────────────────
def handle_command(space_id, user, text):
    cmd = text.strip().lower().split()
    if not cmd:
        return HELP_TEXT

    command = cmd[0]

    # ── HELP ──
    if command == "/help":
        return HELP_TEXT

    # ── BLACKJACK ──
    elif command == "/blackjack":
        deck = new_deck()
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]
        games[space_id] = {
            "game": "blackjack",
            "player": user,
            "player_hand": player_hand,
            "dealer_hand": dealer_hand,
            "deck": deck,
        }
        total = hand_total(player_hand)
        msg = (f"🃏 *Blackjack Started!* — Player: {user}\n\n"
               f"Your hand: {fmt_hand(player_hand)} (Total: {total})\n"
               f"Dealer shows: {dealer_hand[0]} 🂠\n\n"
               f"Type `/hit` to draw or `/stand` to hold.")
        if total == 21:
            msg += "\n\n🎉 *Blackjack! You win instantly!*"
            del games[space_id]
        return msg

    elif command == "/hit":
        g = games.get(space_id)
        if not g or g["game"] != "blackjack":
            return "❌ No active Blackjack game. Type `/blackjack` to start."
        card = g["deck"].pop()
        g["player_hand"].append(card)
        total = hand_total(g["player_hand"])
        msg = (f"🃏 You drew: *{card}*\n"
               f"Your hand: {fmt_hand(g['player_hand'])} (Total: {total})\n")
        if total > 21:
            msg += "\n💥 *Bust! You lose.* Game over."
            del games[space_id]
        elif total == 21:
            msg += "\n🎉 *21! Perfect hand — auto stand!*\n"
            msg += dealer_reveal(g, space_id)
        else:
            msg += "Type `/hit` to draw or `/stand` to hold."
        return msg

    elif command == "/stand":
        g = games.get(space_id)
        if not g or g["game"] != "blackjack":
            return "❌ No active Blackjack game. Type `/blackjack` to start."
        return dealer_reveal(g, space_id)

    # ── DICE DUEL ──
    elif command == "/dice":
        num = int(cmd[1]) if len(cmd) > 1 and cmd[1].isdigit() else 1
        num = min(num, 6)
        player_rolls = [random.randint(1, 6) for _ in range(num)]
        bot_rolls = [random.randint(1, 6) for _ in range(num)]
        p_total = sum(player_rolls)
        b_total = sum(bot_rolls)
        dice_faces = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        p_display = " ".join(dice_faces[r] for r in player_rolls)
        b_display = " ".join(dice_faces[r] for r in bot_rolls)
        result = "🏆 *You win!*" if p_total > b_total else ("🤝 *It's a tie!*" if p_total == b_total else "🤖 *Bot wins!*")
        return (f"🎲 *Dice Duel!*\n\n"
                f"{user}: {p_display} = *{p_total}*\n"
                f"🤖 Bot: {b_display} = *{b_total}*\n\n"
                f"{result}")

    # ── HIGHER OR LOWER ──
    elif command == "/hol":
        deck = new_deck()
        current = deck.pop()
        games[space_id] = {
            "game": "hol",
            "player": user,
            "current": current,
            "deck": deck,
            "score": 0,
        }
        return (f"🎴 *Higher or Lower* — Player: {user}\n\n"
                f"Current card: *{current}* (Value: {card_value(current)})\n\n"
                f"Will the next card be `/higher` or `/lower`?")

    elif command in ("/higher", "/lower"):
        g = games.get(space_id)
        if not g or g["game"] != "hol":
            return "❌ No active Higher or Lower game. Type `/hol` to start."
        if not g["deck"]:
            score = g["score"]
            del games[space_id]
            return f"🎴 Deck exhausted! Final score: *{score}* correct guesses. 🏆"
        current = g["current"]
        next_card = g["deck"].pop()
        current_val = card_value(current)
        next_val = card_value(next_card)
        correct = (command == "/higher" and next_val >= current_val) or \
                  (command == "/lower" and next_val <= current_val)
        g["current"] = next_card
        if correct:
            g["score"] += 1
            result = f"✅ *Correct!* Score: {g['score']}"
        else:
            score = g["score"]
            del games[space_id]
            result = f"❌ *Wrong!* Game over. Final score: *{score}*"
        return (f"🎴 Previous: *{current}* → Next: *{next_card}*\n\n"
                f"{result}\n\n"
                + (f"Current card: *{next_card}* (Value: {next_val})\nGuess: `/higher` or `/lower`?"
                   if correct else ""))

    else:
        return f"❓ Unknown command `{text}`. Type `/help` for all commands."


def dealer_reveal(g, space_id):
    dealer = g["dealer_hand"]
    deck = g["deck"]
    while hand_total(dealer) < 17:
        dealer.append(deck.pop())
    d_total = hand_total(dealer)
    p_total = hand_total(g["player_hand"])
    msg = (f"🃏 Dealer reveals: {fmt_hand(dealer)} (Total: {d_total})\n"
           f"Your hand: {fmt_hand(g['player_hand'])} (Total: {p_total})\n\n")
    if d_total > 21:
        msg += "💥 Dealer busts! 🏆 *You win!*"
    elif p_total > d_total:
        msg += "🏆 *You win!*"
    elif p_total == d_total:
        msg += "🤝 *Push — it's a tie!*"
    else:
        msg += "🤖 *Dealer wins!*"
    del games[space_id]
    return msg


# ─── Google Chat Webhook Endpoint ────────────────────────────────────────
@app.route("/", methods=["POST"])
def chat_webhook():
    event = request.get_json()

    # Only handle MESSAGE events
    if event.get("type") != "MESSAGE":
        return jsonify({"text": "👋 Hi! Type `/help` to see available games."})

    space_id = event["space"]["name"]
    user = event["user"].get("displayName", "Player")
    text = event["message"].get("text", "").strip()

    response_text = handle_command(space_id, user, text)
    return jsonify({"text": response_text})


# ─── Run ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🎮 Game Bot running on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
