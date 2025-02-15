import os
import time
import asyncio
import nest_asyncio
import aiohttp
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    ChatJoinRequestHandler,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    filters,
)

# ---------------- Global Variables ----------------

# For the welcome message, we use the invite links that require admin approval.
invite_links = {}  # Mapping: chat_id -> (admin_approval_invite_url, chat_title)

# For the admin /grp command, we use invite links that do NOT require admin approval.
admin_invite_links = {}  # Mapping: chat_id -> (non_admin_invite_url, chat_title)

# Mapping of user id to the datetime of their first interaction.
tracked_users = {}

# Admin ID (only this user can use admin commands)
ADMIN_ID = 001000

# Record the first development date (bot start time)
first_dev_date = datetime.now()

# Bot token
BOT_TOKEN = "bot-token"

# File path and URL for the welcome video (our "GIF")
GIF_FILE_PATH = "welcome_video.mp4"
GIF_DOWNLOAD_URL = (
    "gif-download-link"
)

# ---------------- Helper Functions ----------------

async def download_gif():
    """Download the video file once and save it locally."""
    if not os.path.exists(GIF_FILE_PATH):
        print("Downloading GIF file...")
        async with aiohttp.ClientSession() as session:
            async with session.get(GIF_DOWNLOAD_URL) as response:
                if response.status == 200:
                    content = await response.read()
                    with open(GIF_FILE_PATH, "wb") as f:
                        f.write(content)
                    print("GIF downloaded and saved.")
                else:
                    print("Failed to download GIF, status:", response.status)
    else:
        print("GIF file already exists. Skipping download.")

async def send_welcome_message(context: CallbackContext, user, chat):
    """
    Create (or retrieve) two invite links for the chat:
      - An admin approval invite link (creates_join_request=True) used in the welcome message.
      - A non-admin approval invite link (creates_join_request=False) stored for admin /grp command.
    Then send a welcome video with an inline button.
    """
    # Create or retrieve the admin approval invite link (for welcome message)
    if chat.id not in invite_links:
        try:
            admin_invite_link_obj = await context.bot.create_chat_invite_link(
                chat.id,
                creates_join_request=True,  # Link requires admin approval
                expire_date=None,
                member_limit=0
            )
            invite_links[chat.id] = (admin_invite_link_obj.invite_link, chat.title)
            print(f"Created admin approval invite link for chat {chat.id}: {admin_invite_link_obj.invite_link}")
        except TelegramError as e:
            print(f"Error creating admin approval invite link: {e}")
            return

    # Create or retrieve the non-admin approval invite link (for admin /grp command)
    if chat.id not in admin_invite_links:
        try:
            non_admin_invite_link_obj = await context.bot.create_chat_invite_link(
                chat.id,
                creates_join_request=False,  # Instant join, no admin approval required
                expire_date=None,
                member_limit=0
            )
            admin_invite_links[chat.id] = (non_admin_invite_link_obj.invite_link, chat.title)
            print(f"Created non-admin approval invite link for chat {chat.id}: {non_admin_invite_link_obj.invite_link}")
        except TelegramError as e:
            print(f"Error creating non-admin approval invite link: {e}")
            return

    # Use the admin approval link for the welcome message.
    admin_approval_invite_url, _ = invite_links[chat.id]

    caption = (
        f"Hello <b><a href='tg://user?id={user.id}'>{user.first_name}</a></b>!\n"
        f"Welcome To <b><a href='{admin_approval_invite_url}'>{chat.title}</a></b>\n\n"
        "👇More Spicy Content 🥵🔥\n"
        "<b>@HotError</b>\n"
        "<b>@HotError</b>\n"
        "<b>@HotError</b>"
    )

    inline_button = InlineKeyboardMarkup([
        [InlineKeyboardButton(chat.title, url=admin_approval_invite_url)]
    ])

    with open(GIF_FILE_PATH, "rb") as video_file:
        await context.bot.send_video(
            chat_id=user.id,
            video=video_file,
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=inline_button
        )

def track_user(user, timestamp: datetime):
    """Record the user if not already tracked."""
    if user and user.id not in tracked_users:
        tracked_users[user.id] = timestamp

# ---------------- Handlers ----------------

async def approve(update: Update, context: CallbackContext):
    """
    Approve join requests and send a welcome message.
    First, approve the join request, then send the welcome video as a background task.
    Also record the user interaction.
    """
    chat = update.chat_join_request.chat
    user = update.chat_join_request.from_user
    track_user(user, datetime.now())
    try:
        # Approve join request immediately.
        await context.bot.approve_chat_join_request(chat.id, user.id)
    except TelegramError as e:
        print(f"Error approving join request: {e}")
        return

    # Send welcome message in the background without delaying the approval.
    asyncio.create_task(send_welcome_message(context, user, chat))

async def start(update: Update, context: CallbackContext):
    """Send a start message with inline buttons for group/channel installation."""
    track_user(update.effective_user, datetime.now())
    text = (
        "Hi, I'm a group/channel join request accepter bot!\n\n"
        "Just add me to your group or channel, and I'll accept any join requests instantly.\n"
        "I'll process your group/channel join requests in just 0.1 second!"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "Add to Group",
                url="https://t.me/HotErrorJoinBot?startgroup&admin=change_info+delete_messages+invite_users+restrict_members+pin_messages+promote_members+manage_voice_chats+manage_video_chats"
            ),
            InlineKeyboardButton(
                "Add to Channel",
                url="https://t.me/HotErrorJoinBot?startchannel&admin=change_info+post_messages+edit_messages+delete_messages+invite_users+restrict_members+pin_messages+promote_members+manage_voice_chats+manage_video_chats+manage_live_stream+manage_stories"
            )
        ]
    ])
    await update.message.reply_text(text, reply_markup=keyboard)

async def more_spicy(update: Update, context: CallbackContext):
    """Reply to any non-command text message with a spicy fun message."""
    track_user(update.effective_user, datetime.now())
    text = "Get More Spicy Fun Here😍🌶️👇"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Spicy Links", url="https://t.me/hoterrorlinks")]
    ])
    await update.message.reply_text(text, reply_markup=keyboard)

async def admin_users(update: Update, context: CallbackContext):
    """Show user statistics (admin-only)."""
    if update.effective_user.id != ADMIN_ID:
        return  # Ignore non-admin requests.
    
    track_user(update.effective_user, datetime.now())
    now = datetime.now()
    total_users = len(tracked_users)
    today_users = sum(1 for ts in tracked_users.values() if ts.date() == now.date())
    last_week_users = sum(1 for ts in tracked_users.values() if ts >= now - timedelta(days=7))
    last_month_users = sum(1 for ts in tracked_users.values() if ts >= now - timedelta(days=30))
    first_dev = first_dev_date.strftime("%Y-%m-%d %H:%M:%S")

    stats = (
        f"Total User: {total_users}\n"
        f"Today User: {today_users}\n"
        f"Last Weekly: {last_week_users}\n"
        f"Last Month: {last_month_users}\n"
        f"First Development Date: {first_dev}"
    )
    await update.message.reply_text(stats)

async def admin_grp(update: Update, context: CallbackContext):
    """Send a numbered list of groups/channels with non-admin approval invite links (admin-only)."""
    if update.effective_user.id != ADMIN_ID:
        return  # Ignore non-admin requests.

    track_user(update.effective_user, datetime.now())
    if not admin_invite_links:
        await update.message.reply_text("No groups or channels available yet.")
        return

    lines = []
    for i, (chat_id, (invite_url, chat_title)) in enumerate(admin_invite_links.items(), start=1):
        lines.append(f"({i}) {chat_title} - {invite_url}")
    message_text = "\n".join(lines)

    MAX_LENGTH = 4000
    if len(message_text) <= MAX_LENGTH:
        await update.message.reply_text(message_text)
    else:
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > MAX_LENGTH:
                await update.message.reply_text(chunk)
                chunk = line + "\n"
            else:
                chunk += line + "\n"
        if chunk:
            await update.message.reply_text(chunk)

async def track_user_handler(update: Update, context: CallbackContext):
    """
    A global pre-processor to record every user's first interaction.
    This runs on every update.
    """
    if update.effective_user:
        track_user(update.effective_user, datetime.now())

# ---------- Forward Private Chat Messages ----------

async def forward_private_message(update: Update, context: CallbackContext):
    """
    For messages sent in private chat:
      - Forward the message to channel -1002399068205,
      - But ignore pure command messages (e.g. "/start" with no extra text).
    """
    msg = update.effective_message
    if not msg or update.effective_chat.type != "private":
        return

    if msg.text:
        text = msg.text.strip()
        if text.startswith("/") and (" " not in text):
            return

    try:
        await context.bot.forward_message(
            chat_id=-1002399068205,
            from_chat_id=msg.chat.id,
            message_id=msg.message_id
        )
    except Exception as e:
        print(f"Error forwarding user message: {e}")


# ---------- Broadcast Channel Messages to All Users with Summary ----------

async def broadcast_channel_message(update: Update, context: CallbackContext):
    """
    When a new message is posted in channel -1002374713796,
    copy that message (including any inline URL buttons if present) to every tracked user.
    After broadcasting, send a summary to the admin.
    """
    msg = update.effective_message
    if not msg or update.effective_chat.id != -1002374713796:
        return

    # If the message has an inline keyboard, pass it along.
    reply_markup = msg.reply_markup if msg.reply_markup else None

    start_time = time.perf_counter()
    tasks = []
    for user_id in tracked_users.keys():
        tasks.append(
            context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=msg.chat.id,
                message_id=msg.message_id,
                reply_markup=reply_markup
            )
        )
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.perf_counter()
        duration = end_time - start_time

        successful = sum(1 for result in results if not isinstance(result, Exception))
        unsuccessful = sum(1 for result in results if isinstance(result, Exception))
        total_users = len(tracked_users)

        summary = (
            f"Broadcast Summary:\n"
            f"Total Users: {total_users}\n"
            f"Successful: {successful}\n"
            f"Unsuccessful: {unsuccessful}\n"
            f"Total Time: {duration:.2f} seconds"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=summary)
        except Exception as e:
            print(f"Error sending broadcast summary: {e}")

# ---------------- Main Function ----------------

async def main():
    nest_asyncio.apply()
    await download_gif()

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    # Global tracker for all updates (runs first)
    app.add_handler(MessageHandler(filters.ALL, track_user_handler), group=-1)

    # Join request handling in groups/supergroups.
    app.add_handler(ChatJoinRequestHandler(approve))

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", admin_users))
    app.add_handler(CommandHandler("grp", admin_grp))

    # For non-command text messages in private chat, reply with spicy fun.
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, more_spicy)
    )

    # Copy user messages in private chat to channel -1002399068205.
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE, forward_private_message), group=1)

    # Broadcast: Copy messages (with inline buttons if present) from channel -1002374713796 to all tracked users.
    app.add_handler(MessageHandler(
        filters.Chat(-1002374713796), broadcast_channel_message), group=2)

    print("Bot is polling for updates...")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
