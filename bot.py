import asyncio
import random
import json
import openai
from telethon import TelegramClient, events, functions, types

# --- Load from config.json ---
try:
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
except Exception as e:
    print(f"Config load error: {e}")
    raise

openai.api_key = config['OPENAI_API_KEY']
api_id = config['API_ID']
api_hash = config['API_HASH']
admin_id = config['ADMIN_ID']
GROUP_ID = config['GROUP_ID']

session_name = "userbot"
client = TelegramClient(session_name, api_id, api_hash)

# --- MEMORY ---
user_context = {}
user_confirm_pending = {}
user_selected_product = {}
ai_active = False

# --- SYSTEM PROMPT ---
system_prompt = """
Tum ek professional aur friendly OTT, Adult, Games subscription seller ho...
(baaki prompt wahi rehne do)
"""

confirm_words = ['haa', 'han', 'ha', 'krde', 'karde', 'kar de', 'done', 'paid', 'payment ho gaya', 'payment done', 'payment hogaya']
greetings_words = ['hi', 'hello', 'hey', 'good morning', 'good evening', 'good night', 'hola', 'namaste']
thanks_words = ['thanks', 'thank you', 'thnx', 'ok', 'okay', 'cool', 'great', 'nice']

reaction_map = {
    'greetings': ['😊', '👍', '👋', '🙂'],
    'thanks': ['✅', '🙌', '🎉', '😎']
}

async def send_typing(event):
    try:
        await event.client(functions.messages.SetTypingRequest(
            peer=event.chat_id,
            action=types.SendMessageTypingAction()
        ))
        await asyncio.sleep(random.uniform(1.0, 2.0))
    except Exception as e:
        print(f"Typing error: {e}")

async def add_reaction(event, reaction_type):
    try:
        emoji = random.choice(reaction_map[reaction_type])
        await event.client(functions.messages.SetMessageReactionRequest(
            peer=event.chat_id,
            msg_id=event.id,
            reaction=[types.ReactionEmoji(emoticon=emoji)]
        ))
    except Exception as e:
        print(f"Reaction error: {e}")

async def keep_online():
    while True:
        try:
            await client(functions.account.UpdateStatusRequest(offline=False))
        except Exception as e:
            print(f"Online error: {e}")
        await asyncio.sleep(60)

@client.on(events.NewMessage())
async def handler(event):
    global ai_active

    sender = await event.get_sender()
    sender_id = sender.id if sender else None
    user_message = event.raw_text.strip().lower() if event.raw_text else ""

    if sender_id == admin_id:
        if user_message == '/stopai':
            ai_active = False
            await event.delete()
            await client.send_message(sender_id, "✅ AI replies stopped.", reply_to=event.id)
            return
        if user_message == '/startai':
            ai_active = True
            await event.delete()
            await client.send_message(sender_id, "✅ AI replies resumed.", reply_to=event.id)
            return

    if not ai_active and not event.out:
        return

    if not event.out:
        await send_typing(event)

        if any(word in user_message for word in greetings_words):
            await add_reaction(event, 'greetings')
        elif any(word in user_message for word in thanks_words):
            await add_reaction(event, 'thanks')

        if sender_id not in user_context:
            user_context[sender_id] = []

        user_context[sender_id].append({"role": "user", "content": user_message})
        if len(user_context[sender_id]) > 10:
            user_context[sender_id] = user_context[sender_id][-10:]

        try:
            if any(word in user_message for word in confirm_words):
                if sender_id in user_confirm_pending:
                    plan = user_confirm_pending[sender_id]
                    user_link = f'<a href="tg://user?id={sender_id}">{sender.first_name}</a>'
                    post_text = f"""✅ New Payment Confirmation!\n👤 User: {user_link}\n🎯 Subscription: {plan['product']}\n💰 Amount: {plan['price']}\n⏳ Validity: {plan['validity']}"""
                    await client.send_message(GROUP_ID, post_text, parse_mode='html')
                    await event.respond("✅ Payment Confirmed! QR code generate ho raha hai 📲")
                    del user_confirm_pending[sender_id]
                    return

            products = ["netflix", "prime", "hotstar", "sony", "zee5", "voot", "mx player", "ullu", "hoichoi", "eros", "jio", "discovery", "shemaroo", "alt", "sun", "aha", "youtube", "telegram", "chatgpt", "adult", "hack", "bgmi", "falcone", "vision", "lethal", "titan", "shoot360", "win", "ioszero"]
            matched = [p for p in user_message.split() if p in products]

            if matched and sender_id not in user_confirm_pending:
                selected_product = matched[0].capitalize()
                user_selected_product[sender_id] = selected_product
                await event.respond(f"✅ {selected_product} ke liye kitni validity chahiye bhai? 6 months ya 1 year?")
                return

            if "6 month" in user_message or "6 months" in user_message:
                if sender_id in user_selected_product:
                    product = user_selected_product[sender_id]
                    price = "₹350" if product.lower() in ["netflix", "prime", "hotstar", "sony", "zee5", "youtube", "telegram"] else "₹300"
                    user_confirm_pending[sender_id] = {
                        "product": product,
                        "validity": "6 Months",
                        "price": price
                    }
                    await event.respond("✅ 6 Months selected bhai! Confirm karo (haa/ok/krde).")
                    return

            if "1 year" in user_message or "12 months" in user_message:
                if sender_id in user_selected_product:
                    product = user_selected_product[sender_id]
                    price = "₹500"
                    user_confirm_pending[sender_id] = {
                        "product": product,
                        "validity": "1 Year",
                        "price": price
                    }
                    await event.respond("✅ 1 Year selected bhai! Confirm karo (haa/ok/krde).")
                    return

            messages_for_gpt = [{"role": "system", "content": system_prompt}] + user_context[sender_id]

            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=messages_for_gpt,
                temperature=0.5,
            )
            bot_reply = response.choices[0].message['content']
            user_context[sender_id].append({"role": "assistant", "content": bot_reply})
            await event.respond(bot_reply)

        except Exception as e:
            print(f"Error: {e}")
            await event.respond("Bhai thoda error aagaya 😔 Try later.")

# --- Start Client ---
client.start()
client.loop.create_task(keep_online())
client.run_until_disconnected()
