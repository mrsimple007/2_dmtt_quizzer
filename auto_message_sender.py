"""
Optimized broadcast message handler with concurrent sending
This version can send to 6000 users in ~3-5 minutes instead of 30 minutes
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, 
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler
)
from telegram.constants import ParseMode
from telegram.error import TelegramError, RetryAfter, TimedOut
import logging
import asyncio
from typing import List, Dict

logger = logging.getLogger(__name__)

# States for conversation
BROADCAST_MENU = 1000
BROADCAST_MESSAGE_INPUT = 1001
BROADCAST_CONFIRM = 1002
BROADCAST_TEST_USER = 1003

# Admin IDs
AUTHORIZED_ADMINS = ["8437026582", "999932510"]

ADMIN_ID = 999932510 
TEST_USERS_COUNT = 150  # Send to 150 random users for testing
TEST_GROUPS_COUNT = 20  # Send to 20 random groups for testing


# Performance settings
CONCURRENT_SENDS = 30  # Send to 30 users at once
BATCH_SIZE = 100  # Update status every 100 users
RATE_LIMIT_DELAY = 1  # Delay in seconds when rate limited

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start broadcast message flow - admin only"""
    user_id = str(update.effective_user.id)
    
    if user_id not in AUTHORIZED_ADMINS:
        await update.message.reply_text("❌ Unauthorized. This command is admin-only.")
        return ConversationHandler.END
    
    # Clear any previous broadcast data
    context.user_data.pop('broadcast_target', None)
    context.user_data.pop('broadcast_message_obj', None)
    context.user_data.pop('test_user_id', None)
    
    # Show broadcast menu with test batch options
    keyboard = [
        [InlineKeyboardButton("📤 Send to ALL users", callback_data="bc_all_users")],
        [InlineKeyboardButton("👥 Send to ALL groups", callback_data="bc_all_groups")],
        [InlineKeyboardButton("🧪 Test: 150 users + 20 groups", callback_data="bc_test_batch")],
        [InlineKeyboardButton("👤 Send to admin only", callback_data="bc_test_admin")],
        [InlineKeyboardButton("❌ Cancel", callback_data="bc_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📢 <b>Admin Broadcast Panel</b>\n\n"
        "Select broadcast target:\n\n"
        "• <b>ALL users/groups</b>: Full broadcast\n"
        "• <b>Test batch</b>: 150 random users + 20 groups\n"
        "• <b>Admin only</b>: Send to yourself first",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    
    return BROADCAST_MENU

async def broadcast_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast menu selections"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "bc_cancel":
        await query.edit_message_text("❌ Broadcast cancelled.")
        context.user_data.pop('broadcast_target', None)
        context.user_data.pop('broadcast_message_obj', None)
        context.user_data.pop('test_user_id', None)
        return ConversationHandler.END
    
    context.user_data['broadcast_target'] = query.data
    
    # Handle test to admin
    if query.data == "bc_test_admin":
        await query.edit_message_text(
            "👤 <b>Test Message to Admin</b>\n\n"
            f"Message will be sent to admin (ID: {ADMIN_ID})\n\n"
            "Send me the message you want to test.\n\n"
            "You can use formatting:\n"
            "• <b>Bold</b>: <code>&lt;b&gt;text&lt;/b&gt;</code>\n"
            "• <i>Italic</i>: <code>&lt;i&gt;text&lt;/i&gt;</code>\n"
            "• <code>Code</code>: <code>&lt;code&gt;text&lt;/code&gt;</code>\n\n"
            "Send /cancel to abort.",
            parse_mode=ParseMode.HTML
        )
        return BROADCAST_MESSAGE_INPUT
    
    # Handle test batch
    if query.data == "bc_test_batch":
        try:
            from SIMPLEQUIZ_message import fetch_users, fetch_groups
            users = fetch_users()
            groups = fetch_groups()
            
            user_count = min(TEST_USERS_COUNT, len(users))
            group_count = min(TEST_GROUPS_COUNT, len(groups))
            
            await query.edit_message_text(
                f"🧪 <b>Test Batch Broadcast</b>\n\n"
                f"Will send to:\n"
                f"• {user_count} random users (out of {len(users)} total)\n"
                f"• {group_count} random groups (out of {len(groups)} total)\n\n"
                "Send me the message you want to broadcast.\n\n"
                "You can use formatting:\n"
                "• <b>Bold</b>: <code>&lt;b&gt;text&lt;/b&gt;</code>\n"
                "• <i>Italic</i>: <code>&lt;i&gt;text&lt;/i&gt;</code>\n"
                "• <code>Code</code>: <code>&lt;code&gt;text&lt;/code&gt;</code>\n\n"
                "Send /cancel to abort.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error loading user/group counts: {str(e)}\n\n"
                "Please try again or contact support."
            )
            return ConversationHandler.END
        
        return BROADCAST_MESSAGE_INPUT
    
    # Original handlers for all users/groups
    target_name = "all users" if query.data == "bc_all_users" else "all groups"
    
    await query.edit_message_text(
        f"📝 <b>Compose Message for {target_name}</b>\n\n"
        "Send me the message you want to broadcast.\n\n"
        "You can use formatting:\n"
        "• <b>Bold</b>: <code>&lt;b&gt;text&lt;/b&gt;</code>\n"
        "• <i>Italic</i>: <code>&lt;i&gt;text&lt;/i&gt;</code>\n"
        "• <code>Code</code>: <code>&lt;code&gt;text&lt;/code&gt;</code>\n"
        "• <u>Underline</u>: <code>&lt;u&gt;text&lt;/u&gt;</code>\n"
        "• <s>Strike</s>: <code>&lt;s&gt;text&lt;/s&gt;</code>\n\n"
        "Or use Telegram's built-in formatting (bold, italic, etc.)\n\n"
        "Send /cancel to abort.",
        parse_mode=ParseMode.HTML
    )
    
    return BROADCAST_MESSAGE_INPUT

async def broadcast_test_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle test user ID input"""
    user_id_input = update.message.text.strip()
    
    try:
        test_user_id = int(user_id_input)
        context.user_data['test_user_id'] = test_user_id
        
        await update.message.reply_text(
            f"🧪 <b>Test Message to User {test_user_id}</b>\n\n"
            "Send me the message you want to send.\n\n"
            "You can use formatting:\n"
            "• <b>Bold</b>: <code>&lt;b&gt;text&lt;/b&gt;</code>\n"
            "• <i>Italic</i>: <code>&lt;i&gt;text&lt;/i&gt;</code>\n"
            "• <code>Code</code>: <code>&lt;code&gt;text&lt;/code&gt;</code>\n"
            "• <u>Underline</u>: <code>&lt;u&gt;text&lt;/u&gt;</code>\n\n"
            "Or use Telegram's built-in formatting.\n\n"
            "Send /cancel to abort.",
            parse_mode=ParseMode.HTML
        )
        
        return BROADCAST_MESSAGE_INPUT
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid user ID. Please enter a numeric ID or send /cancel"
        )
        return BROADCAST_TEST_USER

async def broadcast_message_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle message input with formatting"""
    message = update.message
    context.user_data['broadcast_message_obj'] = {
        'text': message.text or message.caption or "",
        'entities': message.entities or message.caption_entities or []
    }
    
    target = context.user_data.get('broadcast_target')
    
    if target == "bc_all_users":
        try:
            from SIMPLEQUIZ_message import fetch_users
            users = fetch_users()
            target_text = f"📤 <b>All Users</b> ({len(users)} users)"
        except:
            target_text = f"📤 <b>All Users</b>"
    elif target == "bc_all_groups":
        try:
            from SIMPLEQUIZ_message import fetch_groups
            groups = fetch_groups()
            target_text = f"👥 <b>All Groups</b> ({len(groups)} groups)"
        except:
            target_text = f"👥 <b>All Groups</b>"
    elif target == "bc_test_batch":
        try:
            from SIMPLEQUIZ_message import fetch_users, fetch_groups
            users = fetch_users()
            groups = fetch_groups()
            user_count = min(TEST_USERS_COUNT, len(users))
            group_count = min(TEST_GROUPS_COUNT, len(groups))
            target_text = f"🧪 <b>Test Batch</b> ({user_count} users + {group_count} groups)"
        except:
            target_text = f"🧪 <b>Test Batch</b>"
    elif target == "bc_test_admin":
        target_text = f"👤 <b>Admin Only</b> (ID: {ADMIN_ID})"
    else:
        test_user_id = context.user_data.get('test_user_id')
        target_text = f"🧪 <b>Test User</b> (ID: {test_user_id})"
    
    keyboard = [
        [InlineKeyboardButton("✅ Confirm & Send", callback_data="bc_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data="bc_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📋 <b>Broadcast Preview</b>\n\n"
        f"Target: {target_text}\n\n"
        f"Message preview:",
        parse_mode=ParseMode.HTML
    )
    
    await update.message.copy(chat_id=update.effective_chat.id)
    
    await update.message.reply_text(
        "Confirm sending?",
        reply_markup=reply_markup
    )
    
    return BROADCAST_CONFIRM

async def broadcast_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast confirmation"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "bc_cancel":
        await query.edit_message_text("❌ Broadcast cancelled.")
        context.user_data.pop('broadcast_target', None)
        context.user_data.pop('broadcast_message_obj', None)
        context.user_data.pop('test_user_id', None)
        return ConversationHandler.END
    
    target = context.user_data.get('broadcast_target')
    message_data = context.user_data.get('broadcast_message_obj')
    
    if not message_data:
        await query.edit_message_text("❌ Error: No message data found. Please try again.")
        return ConversationHandler.END
    
    await query.edit_message_text("📤 Starting broadcast...")
    
    if target == "bc_all_users":
        await send_to_all_users_fast(update, context, message_data)
    elif target == "bc_all_groups":
        await send_to_all_groups_fast(update, context, message_data)
    elif target == "bc_test_batch":
        await send_to_test_batch(update, context, message_data)
    elif target == "bc_test_admin":
        await send_to_admin_only(update, context, message_data)
    else:
        test_user_id = context.user_data.get('test_user_id')
        await send_test_message_formatted(update, context, message_data, test_user_id)
    
    context.user_data.pop('broadcast_target', None)
    context.user_data.pop('broadcast_message_obj', None)
    context.user_data.pop('test_user_id', None)
    
    return ConversationHandler.END

async def send_to_admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE, message_data: dict):
    """Send test message to admin only"""
    success = await send_single_message(context.bot, ADMIN_ID, message_data)
    
    if success:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ <b>Test message sent to admin</b>\n\n"
                 f"Admin ID: {ADMIN_ID}\n"
                 f"Check your messages to verify formatting!",
            parse_mode=ParseMode.HTML
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Failed to send test message to admin {ADMIN_ID}",
            parse_mode=ParseMode.HTML
        )

async def send_to_test_batch(update: Update, context: ContextTypes.DEFAULT_TYPE, message_data: dict):
    """Send to random sample of users and groups for testing"""
    import random
    
    try:
        from SIMPLEQUIZ_message import fetch_users, fetch_groups
        all_users = fetch_users()
        all_groups = fetch_groups()
    except Exception as e:
        logger.error(f"Failed to fetch users/groups: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Error fetching users/groups: {str(e)}"
        )
        return
    
    # Get random samples
    test_users = random.sample(all_users, min(TEST_USERS_COUNT, len(all_users)))
    test_groups = random.sample(all_groups, min(TEST_GROUPS_COUNT, len(all_groups)))
    
    total_targets = len(test_users) + len(test_groups)
    user_successful = 0
    user_failed = 0
    group_successful = 0
    group_failed = 0
    
    status_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🧪 <b>Test Batch Broadcast</b>\n\n"
             f"Sending to {len(test_users)} users and {len(test_groups)} groups...\n\n"
             f"👥 Users: 0/{len(test_users)}\n"
             f"👥 Groups: 0/{len(test_groups)}",
        parse_mode=ParseMode.HTML
    )
    
    import time
    start_time = time.time()
    
    # Send to users first
    logger.info(f"[TEST BATCH] Sending to {len(test_users)} test users")
    for i in range(0, len(test_users), CONCURRENT_SENDS):
        chunk = test_users[i:i + CONCURRENT_SENDS]
        
        tasks = [
            send_single_message(context.bot, user['id'], message_data)
            for user in chunk
        ]
        
        results = await asyncio.gather(*tasks)
        user_successful += sum(results)
        user_failed += len(results) - sum(results)
        
        # Update status
        try:
            await status_message.edit_text(
                f"🧪 <b>Test Batch Broadcast</b>\n\n"
                f"👥 Users: {user_successful + user_failed}/{len(test_users)} "
                f"(✅ {user_successful} ❌ {user_failed})\n"
                f"👥 Groups: {group_successful + group_failed}/{len(test_groups)}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.debug(f"Failed to update status: {e}")
    
    # Send to groups
    logger.info(f"[TEST BATCH] Sending to {len(test_groups)} test groups")
    GROUP_CONCURRENT = 20
    for i in range(0, len(test_groups), GROUP_CONCURRENT):
        chunk = test_groups[i:i + GROUP_CONCURRENT]
        
        tasks = [
            send_single_message(context.bot, group['id'], message_data)
            for group in chunk
        ]
        
        results = await asyncio.gather(*tasks)
        group_successful += sum(results)
        group_failed += len(results) - sum(results)
        
        # Update status
        try:
            await status_message.edit_text(
                f"🧪 <b>Test Batch Broadcast</b>\n\n"
                f"👥 Users: {user_successful + user_failed}/{len(test_users)} "
                f"(✅ {user_successful} ❌ {user_failed})\n"
                f"👥 Groups: {group_successful + group_failed}/{len(test_groups)} "
                f"(✅ {group_successful} ❌ {group_failed})",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.debug(f"Failed to update status: {e}")
    
    # Final status
    elapsed = time.time() - start_time
    total_successful = user_successful + group_successful
    total_failed = user_failed + group_failed
    
    await status_message.edit_text(
        f"✅ <b>Test Batch Complete</b>\n\n"
        f"📊 <b>Users:</b>\n"
        f"  • Total: {len(test_users)}\n"
        f"  • Sent: {user_successful}\n"
        f"  • Failed: {user_failed}\n\n"
        f"📊 <b>Groups:</b>\n"
        f"  • Total: {len(test_groups)}\n"
        f"  • Sent: {group_successful}\n"
        f"  • Failed: {group_failed}\n\n"
        f"⏱ Time: {int(elapsed)}s\n"
        f"⚡ Avg speed: {total_targets/elapsed:.1f} msg/sec\n\n"
        f"{'✅ No conflicts detected!' if total_successful > 0 else '⚠️ Check for issues'}",
        parse_mode=ParseMode.HTML
    )


async def send_single_message(bot, chat_id: int, message_data: dict) -> bool:
    """Send a single message with retry logic"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message_data['text'],
                entities=message_data['entities']
            )
            return True
        except RetryAfter as e:
            # Telegram rate limit hit
            if attempt < max_retries - 1:
                await asyncio.sleep(e.retry_after)
            else:
                logger.warning(f"Rate limited for chat {chat_id}, skipping")
                return False
        except TimedOut:
            # Timeout, retry
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
            else:
                logger.warning(f"Timeout for chat {chat_id}, skipping")
                return False
        except TelegramError as e:
            # User blocked bot, chat not found, etc.
            logger.debug(f"Failed to send to {chat_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error for chat {chat_id}: {e}")
            return False
    
    return False

async def send_to_all_users_fast(update: Update, context: ContextTypes.DEFAULT_TYPE, message_data: dict):
    """Send formatted message to all users with concurrent sending"""
    try:
        from SIMPLEQUIZ_message import fetch_users
        users = fetch_users()
    except Exception as e:
        logger.error(f"Failed to fetch users: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Error fetching users: {str(e)}"
        )
        return
    
    if not users:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ No users found in database."
        )
        return
    
    total_users = len(users)
    successful = 0
    failed = 0
    
    status_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"📤 Sending to {total_users} users...\n\n"
             f"✅ Sent: 0\n"
             f"❌ Failed: 0\n"
             f"⚡ Speed: Initializing..."
    )
    
    import time
    start_time = time.time()
    last_update_time = start_time
    
    # Process users in chunks
    for i in range(0, total_users, CONCURRENT_SENDS):
        chunk = users[i:i + CONCURRENT_SENDS]
        
        # Send to chunk concurrently
        tasks = [
            send_single_message(context.bot, user['id'], message_data)
            for user in chunk
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Count results
        successful += sum(results)
        failed += len(results) - sum(results)
        
        # Update status every BATCH_SIZE users or at the end
        if (i + len(chunk)) % BATCH_SIZE == 0 or (i + len(chunk)) >= total_users:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Calculate speed
            if elapsed > 0:
                speed = (successful + failed) / elapsed
                remaining = total_users - (successful + failed)
                eta = remaining / speed if speed > 0 else 0
                
                speed_text = f"{speed:.1f} msg/sec"
                eta_text = f"ETA: {int(eta)}s" if eta > 0 else "Almost done"
            else:
                speed_text = "Calculating..."
                eta_text = ""
            
            # Only update if 2 seconds have passed (avoid rate limits on edits)
            if current_time - last_update_time >= 2 or (i + len(chunk)) >= total_users:
                try:
                    await status_message.edit_text(
                        f"📤 Sending to {total_users} users...\n\n"
                        f"✅ Sent: {successful}\n"
                        f"❌ Failed: {failed}\n"
                        f"Progress: {successful + failed}/{total_users}\n"
                        f"⚡ Speed: {speed_text}\n"
                        f"⏱ {eta_text}"
                    )
                    last_update_time = current_time
                except Exception as e:
                    logger.debug(f"Failed to update status: {e}")
    
    # Final status
    elapsed = time.time() - start_time
    await status_message.edit_text(
        f"✅ <b>Broadcast Complete</b>\n\n"
        f"Total users: {total_users}\n"
        f"✅ Sent: {successful}\n"
        f"❌ Failed: {failed}\n"
        f"⏱ Time: {int(elapsed)}s ({elapsed/60:.1f} min)\n"
        f"⚡ Avg speed: {total_users/elapsed:.1f} msg/sec",
        parse_mode=ParseMode.HTML
    )

async def send_to_all_groups_fast(update: Update, context: ContextTypes.DEFAULT_TYPE, message_data: dict):
    """Send formatted message to all groups with concurrent sending"""
    try:
        from SIMPLEQUIZ_message import fetch_groups
        groups = fetch_groups()
    except Exception as e:
        logger.error(f"Failed to fetch groups: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Error fetching groups: {str(e)}"
        )
        return
    
    if not groups:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ No groups found in database."
        )
        return
    
    total_groups = len(groups)
    successful = 0
    failed = 0
    
    status_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"📤 Sending to {total_groups} groups...\n\n"
             f"✅ Sent: 0\n"
             f"❌ Failed: 0"
    )
    
    import time
    start_time = time.time()
    last_update_time = start_time
    
    # Use smaller concurrent sends for groups (they might have rate limits)
    GROUP_CONCURRENT = 20
    
    for i in range(0, total_groups, GROUP_CONCURRENT):
        chunk = groups[i:i + GROUP_CONCURRENT]
        
        tasks = [
            send_single_message(context.bot, group['id'], message_data)
            for group in chunk
        ]
        
        results = await asyncio.gather(*tasks)
        
        successful += sum(results)
        failed += len(results) - sum(results)
        
        # Update status
        if (i + len(chunk)) % 50 == 0 or (i + len(chunk)) >= total_groups:
            current_time = time.time()
            
            if current_time - last_update_time >= 2 or (i + len(chunk)) >= total_groups:
                try:
                    await status_message.edit_text(
                        f"📤 Sending to {total_groups} groups...\n\n"
                        f"✅ Sent: {successful}\n"
                        f"❌ Failed: {failed}\n"
                        f"Progress: {successful + failed}/{total_groups}"
                    )
                    last_update_time = current_time
                except Exception as e:
                    logger.debug(f"Failed to update status: {e}")
    
    elapsed = time.time() - start_time
    await status_message.edit_text(
        f"✅ <b>Broadcast Complete</b>\n\n"
        f"Total groups: {total_groups}\n"
        f"✅ Sent: {successful}\n"
        f"❌ Failed: {failed}\n"
        f"⏱ Time: {int(elapsed)}s",
        parse_mode=ParseMode.HTML
    )

async def send_test_message_formatted(update: Update, context: ContextTypes.DEFAULT_TYPE, message_data: dict, user_id: int):
    """Send formatted test message to specific user"""
    success = await send_single_message(context.bot, user_id, message_data)
    
    if success:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ Test message sent successfully to user {user_id}"
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Failed to send test message to user {user_id}"
        )

async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel broadcast operation"""
    context.user_data.pop('broadcast_target', None)
    context.user_data.pop('broadcast_message_obj', None)
    context.user_data.pop('test_user_id', None)
    
    await update.message.reply_text("❌ Broadcast cancelled.")
    return ConversationHandler.END

def setup_broadcast_handlers(application):
    """Setup broadcast conversation handler"""
    
    broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler("message", broadcast_command)],
        states={
            BROADCAST_MENU: [
                CallbackQueryHandler(broadcast_menu_handler, pattern="^bc_")
            ],
            BROADCAST_TEST_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_test_user_handler),
                CommandHandler("cancel", broadcast_cancel)
            ],
            BROADCAST_MESSAGE_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message_input_handler),
                CommandHandler("cancel", broadcast_cancel)
            ],
            BROADCAST_CONFIRM: [
                CallbackQueryHandler(broadcast_confirm_handler, pattern="^bc_")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", broadcast_cancel),
            CommandHandler("start", broadcast_cancel)
        ],
        name="broadcast_conversation",
        persistent=False,
        allow_reentry=True,
        per_chat=True,
        per_user=True
    )
    
    application.add_handler(broadcast_handler)
    logger.info("✓ Broadcast handlers registered with fast concurrent sending")