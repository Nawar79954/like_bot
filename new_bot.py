import logging
import sqlite3
import asyncio
import sys
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup # type: ignore
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes # type: ignore

# Bot token
BOT_TOKEN = os.getenv('BOT_TOKEN', "8248883880:AAGAVE3svXivHMk_E1ZHAzSBJbDnLJC64kw")

# Admin list
ADMIN_LIST = [7653131217]

# Fix event loop issue on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class TelecomBot:
    def __init__(self, token):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.maintenance_mode = False  # Maintenance mode flag
        self.init_database()
        self.load_admins()
        self.setup_handlers()
        
    def init_database(self):
        """Initialize database"""
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        
        # Admin table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Texts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_texts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Images table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT UNIQUE NOT NULL,
                file_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Router files table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS router_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                router_name TEXT NOT NULL,
                file_id TEXT NOT NULL,
                description TEXT,
                file_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # FAQ table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faq (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Packages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price TEXT,
                speed TEXT,
                features TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User statistics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                usage_count INTEGER DEFAULT 1,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default texts
        default_texts = [
            ('welcome', '🎉 **مرحباً بك في بوت الخدمات!**\n\nاختر الخدمة التي تريدها من القائمة:'),
            ('router_settings', '📡 **اختر نوع الاتصال:**\n• 📶 ADSL: للخطوط الهاتفية\n• 🌐 FTTH: للألياف الضوئية'),
            ('contact', '📞 **أرقام التواصل:**\n📱 الهاتف: 0123456789\n📧 البريد: support@company.com')
        ]
        
        for text_type, content in default_texts:
            cursor.execute('INSERT OR IGNORE INTO bot_texts (type, content) VALUES (?, ?)', (text_type, content))
        
        # Insert default admin
        cursor.execute("SELECT COUNT(*) FROM admins")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO admins (user_id, username) VALUES (?, ?)", (7653131217, "المالك"))
        
        conn.commit()
        conn.close()
    
    def load_admins(self):
        """Load admin list from database"""
        global ADMIN_LIST
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins")
        admins = cursor.fetchall()
        ADMIN_LIST = [admin[0] for admin in admins]
        conn.close()
    
    def is_admin(self, user_id):
        """Check admin permissions"""
        return user_id in ADMIN_LIST

    def update_user_stats(self, user_id, username, first_name, last_name):
        """Update user statistics"""
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO user_stats 
            (user_id, username, first_name, last_name, usage_count, last_seen)
            VALUES (?, ?, ?, ?, 
                COALESCE((SELECT usage_count + 1 FROM user_stats WHERE user_id = ?), 1),
                CURRENT_TIMESTAMP)
        ''', (user_id, username, first_name, last_name, user_id))
        
        conn.commit()
        conn.close()

    def setup_handlers(self):
        """Setup command handlers"""
        handlers = [
            CommandHandler("start", self.start),
            CommandHandler("admin", self.admin_panel),
            CommandHandler("settings", self.router_settings),
            CommandHandler("prices", self.show_prices),
            CommandHandler("faq", self.show_faq),
            CommandHandler("contact", self.show_contact),
            CommandHandler("myid", self.get_my_id),
            CommandHandler("share", self.share_bot),
            CommandHandler("maintenance", self.maintenance_control),  # New maintenance command
            CommandHandler("broadcast", self.broadcast_message),  # New broadcast command
            CallbackQueryHandler(self.button_handler),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message),
            MessageHandler(filters.Document.ALL, self.handle_document),
            MessageHandler(filters.PHOTO, self.handle_photo)
        ]
        
        for handler in handlers:
            self.application.add_handler(handler)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start bot and show main menu"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.effective_user.id):
            await update.message.reply_text(" **البوت تحت الصيانة**")
            return
            
        user = update.effective_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        keyboard = [
            [InlineKeyboardButton("⚙️ إعدادات الراوتر", callback_data="router_settings")],
            [InlineKeyboardButton("💰 الأسعار والعروض", callback_data="prices_offers")],
            [InlineKeyboardButton("❓ الأسئلة الشائعة", callback_data="faq")],
            [InlineKeyboardButton("📞 اتصل بنا", callback_data="contact")],
            [InlineKeyboardButton("🔗 مشاركة البوت", callback_data="share_bot")]
        ]
        
        if self.is_admin(user.id):
            keyboard.append([InlineKeyboardButton("🛠️ لوحة الأدمن", callback_data="admin_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        welcome_text = self.get_bot_text('welcome')
        
        welcome_image = self.get_bot_image('welcome')
        if welcome_image:
            await update.message.reply_photo(
                photo=welcome_image,
                caption=welcome_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def maintenance_control(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Control maintenance mode"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذا الأمر.")
            return

        if not context.args:
            status = "🟢 **نشط**" if not self.maintenance_mode else "🔴 **وضع الصيانة**"
            await update.message.reply_text(
                f"🔧 **تحكم في الصيانة**\n\nالحالة الحالية: {status}\n\n"
                "الاستخدام:\n/maintenance on - تفعيل وضع الصيانة\n/maintenance off - إلغاء وضع الصيانة"
            )
            return

        action = context.args[0].lower()
        if action == 'on':
            self.maintenance_mode = True
            await update.message.reply_text("🔴 **تم تفعيل وضع الصيانة**\n\nفقط الأدمن يمكنهم استخدام البوت الآن.")
        elif action == 'off':
            self.maintenance_mode = False
            await update.message.reply_text("🟢 **تم إلغاء وضع الصيانة**\n\nالبوت متاح الآن لجميع المستخدمين.")
        else:
            await update.message.reply_text("❌ أمر غير صالح. استخدم /maintenance on أو /maintenance off")

    async def broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Broadcast message to all users"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذا الأمر.")
            return

        if not context.args:
            await update.message.reply_text(
                "📢 **بث رسالة**\n\n"
                "الاستخدام: /broadcast رسالتك هنا\n\n"
                "هذا سيرسل رسالتك إلى جميع المستخدمين الذين تفاعلوا مع البوت."
            )
            return

        message_text = ' '.join(context.args)
        users = self.get_all_users()
        
        if not users:
            await update.message.reply_text("📭 لم يتم العثور على مستخدمين في قاعدة البيانات.")
            return

        await update.message.reply_text(f"📤 بدء البث إلى {len(users)} مستخدم...")
        
        success_count = 0
        fail_count = 0
        
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    parse_mode='Markdown'
                )
                success_count += 1
                await asyncio.sleep(0.1)  # Rate limiting
            except Exception as e:
                fail_count += 1
                continue

        await update.message.reply_text(
            f"📊 **اكتمل البث**\n\n"
            f"✅ ناجح: {success_count}\n"
            f"❌ فاشل: {fail_count}\n"
            f"📝 الإجمالي: {len(users)}"
        )

    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin control panel"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذه الصفحة.")
            return

        keyboard = [
            [InlineKeyboardButton("📝 إدارة النصوص", callback_data="admin_texts")],
            [InlineKeyboardButton("🖼️ إدارة الصور", callback_data="admin_images")],
            [InlineKeyboardButton("📁 إدارة الملفات", callback_data="admin_router_files")],
            [InlineKeyboardButton("💰 إدارة الباقات", callback_data="admin_packages")],
            [InlineKeyboardButton("❓ إدارة الأسئلة", callback_data="admin_faq")],
            [InlineKeyboardButton("👥 إدارة الأدمن", callback_data="admin_management")],
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
            [InlineKeyboardButton("🔧 الصيانة", callback_data="admin_maintenance")],  # New maintenance button
            [InlineKeyboardButton("📢 البث", callback_data="admin_broadcast")],  # New broadcast button
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text("🛠️ **لوحة تحكم الأدمن**\n\nاختر القسم الذي تريد إدارته:", reply_markup=reply_markup, parse_mode='Markdown')

    async def router_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show connection types"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.effective_user.id):
            await update.message.reply_text(" **البوت تحت الصيانة**")
            return
            
        user = update.effective_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        keyboard = [
            [InlineKeyboardButton("📶 ADSL", callback_data="router_adsl")],
            [InlineKeyboardButton("🌐 FTTH", callback_data="router_ftth")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = self.get_bot_text('router_settings')
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_prices(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show packages"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.effective_user.id):
            await update.message.reply_text(" **البوت تحت الصيانة**")
            return
            
        user = update.effective_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        packages = self.get_packages_from_db()
        if not packages:
            await update.message.reply_text("📭 لا توجد باقات متاحة حالياً")
            return
        
        packages_image = self.get_bot_image('packages')
        if packages_image:
            await update.message.reply_photo(photo=packages_image, caption="💰 **باقاتنا المتاحة**", parse_mode='Markdown')
        else:
            await update.message.reply_text("💰 **باقاتنا المتاحة**", parse_mode='Markdown')
        
        for package in packages:
            features_text = '\n'.join([f'• {feature}' for feature in package['features']])
            package_text = f"**{package['name']}**\n💰 السعر: {package['price']}\n⚡ السرعة: {package['speed']}\n\n✨ المميزات:\n{features_text}"
            await update.message.reply_text(package_text, parse_mode='Markdown')
        
        keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]]
        await update.message.reply_text("اختر الخطوة التالية:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def show_faq(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show FAQ"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.effective_user.id):
            await update.message.reply_text(" **البوت تحت الصيانة**")
            return
            
        user = update.effective_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        faqs = self.get_faq_from_db()
        if not faqs:
            await update.message.reply_text("📭 لا توجد أسئلة شائعة حالياً")
            return
        
        faq_image = self.get_bot_image('faq')
        if faq_image:
            await update.message.reply_photo(photo=faq_image, caption="❓ **الأسئلة الشائعة**", parse_mode='Markdown')
        else:
            await update.message.reply_text("❓ **الأسئلة الشائعة**", parse_mode='Markdown')
        
        for faq in faqs:
            await update.message.reply_text(f"❓ **{faq['question']}**\n\n✅ {faq['answer']}", parse_mode='Markdown')
        
        keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]]
        await update.message.reply_text("اختر الخطوة التالية:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def show_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show contact information"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.effective_user.id):
            await update.message.reply_text(" **البوت تحت الصيانة**")
            return
            
        user = update.effective_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        contact_info = self.get_bot_text('contact')
        keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(contact_info, parse_mode='Markdown', reply_markup=reply_markup)

    async def share_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Share bot link"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.effective_user.id):
            await update.message.reply_text(" **البوت تحت الصيانة**")
            return
            
        user = update.effective_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        share_text = f"🤖 **بوت الخدمات المتكامل**\n\n🔗 رابط البوت: https://t.me/{bot_username}\n\n✅ خدماتنا:\n• ⚙️ إعدادات الراوتر\n• 💰 باقات الإنترنت\n• ❓ دعم فني\n• 📞 خدمة عملاء"
        
        keyboard = [
            [InlineKeyboardButton("🔗 مشاركة الرابط", url=f"https://t.me/share/url?url=https://t.me/{bot_username}")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(share_text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.callback_query.edit_message_text(share_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def get_my_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user ID"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.effective_user.id):
            await update.message.reply_text(" **البوت تحت الصيانة**")
            return
            
        user = update.effective_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        user_id = user.id
        is_admin = self.is_admin(user_id)
        admin_status = "🔧 أنت أدمن ✅" if is_admin else "👤 مستخدم عادي"
        message = f"🔑 **معلومات حسابك:**\n\n**المعرف:** `{user_id}`\n**الحالة:** {admin_status}"
        
        if not is_admin:
            message += "\n\nلإضافتك كأدمن، أرسل هذا الرقم للمطور."
        else:
            message += "\n\nيمكنك الوصول إلى لوحة الأدمن باستخدام الأمر /admin"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all buttons"""
        query = update.callback_query
        await query.answer()
        data = query.data
        user = query.from_user
        
        # Check maintenance mode for non-admin users
        if self.maintenance_mode and not self.is_admin(user.id):
            await query.edit_message_text(" **البوت تحت الصيانة**")
            return
        
        # Update user statistics
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)

        print(f"🔘 زر مضغوط: {data}")

        # Check permissions for admin buttons
        if data.startswith('admin_') and not self.is_admin(user.id):
            await query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        handler_map = {
            "main_menu": self.start_from_query,
            "router_settings": self.router_settings_from_query,
            "prices_offers": self.show_prices_from_query,
            "faq": self.show_faq_from_query,
            "contact": self.show_contact_from_query,
            "share_bot": self.share_bot_from_query,
            "admin_main": self.admin_panel_from_query,
            "admin_texts": self.admin_texts,
            "admin_images": self.admin_images,
            "admin_router_files": self.admin_router_files,
            "admin_packages": self.admin_packages,
            "admin_faq": self.admin_faq,
            "admin_management": self.admin_management,
            "admin_stats": self.admin_stats,
            "admin_maintenance": self.admin_maintenance,  # New maintenance handler
            "admin_broadcast": self.admin_broadcast,  # New broadcast handler
            "edit_welcome_text": self.edit_welcome_text,
            "edit_settings_text": self.edit_settings_text,
            "edit_contact_text": self.edit_contact_text,
            "change_welcome_image": self.change_welcome_image,
            "change_packages_image": self.change_packages_image,
            "change_faq_image": self.change_faq_image,
            "delete_welcome_image": self.delete_welcome_image,
            "delete_packages_image": self.delete_packages_image,
            "delete_faq_image": self.delete_faq_image,
            "add_router_file": self.add_router_file,
            "list_router_files": self.list_router_files,
            "delete_router_file": self.delete_router_file,
            "add_package": self.add_package,
            "list_packages": self.list_packages,
            "delete_package": self.delete_package,
            "add_faq": self.add_faq,
            "list_faq": self.list_faq,
            "delete_faq": self.delete_faq,
            "list_admins": self.list_admins,
            "add_admin": self.add_admin,
            "remove_admin": self.remove_admin,
            "router_adsl": lambda u, c: self.show_router_files(u, c, 'adsl'),
            "router_ftth": lambda u, c: self.show_router_files(u, c, 'ftth'),
            "enable_maintenance": self.enable_maintenance,  # Enable maintenance
            "disable_maintenance": self.disable_maintenance,  # Disable maintenance
            "send_broadcast": self.send_broadcast,  # Send broadcast
        }
        
        if data.startswith('delete_file_'):
            file_id = int(data.split('_')[2])
            await self.confirm_delete_file(update, context, file_id)
        elif data.startswith('delete_package_'):
            package_id = int(data.split('_')[2])
            await self.confirm_delete_package(update, context, package_id)
        elif data.startswith('delete_faq_'):
            faq_id = int(data.split('_')[2])
            await self.confirm_delete_faq(update, context, faq_id)
        elif data.startswith('delete_admin_'):
            admin_id = int(data.split('_')[2])
            await self.confirm_delete_admin(update, context, admin_id)
        elif data.startswith('confirm_delete_'):
            parts = data.split('_')
            action = parts[2]
            item_id = int(parts[3])
            await self.execute_delete(update, context, action, item_id)
        elif data.startswith('cancel_delete_'):
            await self.cancel_delete(update, context, data.split('_')[2])
        elif data in handler_map:
            await handler_map[data](update, context)
        else:
            await query.edit_message_text("⚠️ هذا الزر غير مدعوم حالياً")

    # Admin functions
    async def admin_maintenance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maintenance control panel"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        status = "🟢 **نشط**" if not self.maintenance_mode else "🔴 **وضع الصيانة**"
        keyboard = [
            [InlineKeyboardButton("🔴 تفعيل الصيانة", callback_data="enable_maintenance")],
            [InlineKeyboardButton("🟢 إلغاء الصيانة", callback_data="disable_maintenance")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_main")]
        ]
        
        message = f"🔧 **تحكم في الصيانة**\n\nالحالة الحالية: {status}\n\n"
        message += "• في وضع الصيانة، فقط الأدمن يمكنهم استخدام البوت\n"
        message += "• المستخدمين العاديين سيرون رسالة الصيانة"
        
        await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def enable_maintenance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enable maintenance mode"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        self.maintenance_mode = True
        await update.callback_query.edit_message_text("🔴 **تم تفعيل وضع الصيانة**\n\nفقط الأدمن يمكنهم استخدام البوت الآن.")
        await self.admin_maintenance(update, context)

    async def disable_maintenance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Disable maintenance mode"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        self.maintenance_mode = False
        await update.callback_query.edit_message_text("🟢 **تم إلغاء وضع الصيانة**\n\nالبوت متاح الآن لجميع المستخدمين.")
        await self.admin_maintenance(update, context)

    async def admin_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Broadcast message panel"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        users_count = len(self.get_all_users())
        keyboard = [
            [InlineKeyboardButton("📢 إرسال بث", callback_data="send_broadcast")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_main")]
        ]
        
        message = f"📢 **بث الرسائل**\n\n"
        message += f"إجمالي المستخدمين: {users_count}\n\n"
        message += "يمكنك إرسال رسالة إلى جميع المستخدمين باستخدام:\n"
        message += "• هذه اللوحة\n• أمر /broadcast\n\n"
        message += "ملاحظة: قد يستغرق هذا بعض الوقت لقاعدة المستخدمين الكبيرة."
        
        await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def send_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send broadcast from panel"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        context.user_data['awaiting_input'] = 'send_broadcast'
        keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="admin_broadcast")]]
        await update.callback_query.edit_message_text("📢 **إرسال بث**\n\nأرسل الرسالة التي تريد بثها إلى جميع المستخدمين:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def admin_texts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manage texts"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton("✏️ نص البداية", callback_data="edit_welcome_text")],
            [InlineKeyboardButton("✏️ نص الإعدادات", callback_data="edit_settings_text")],
            [InlineKeyboardButton("✏️ نص الاتصال", callback_data="edit_contact_text")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_main")]
        ]
        await update.callback_query.edit_message_text("📝 **إدارة النصوص**\n\nاختر النص الذي تريد تعديله:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def edit_welcome_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Edit welcome text"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        context.user_data['awaiting_input'] = 'edit_welcome_text'
        current_text = self.get_bot_text('welcome')
        keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="admin_texts")]]
        await update.callback_query.edit_message_text(f"✏️ **تعديل نص البداية**\n\nالنص الحالي:\n{current_text}\n\nأرسل النص الجديد:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def edit_settings_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Edit settings text"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        context.user_data['awaiting_input'] = 'edit_settings_text'
        current_text = self.get_bot_text('router_settings')
        keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="admin_texts")]]
        await update.callback_query.edit_message_text(f"✏️ **تعديل نص الإعدادات**\n\nالنص الحالي:\n{current_text}\n\nأرسل النص الجديد:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def edit_contact_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Edit contact text"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        context.user_data['awaiting_input'] = 'edit_contact_text'
        current_text = self.get_bot_text('contact')
        keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="admin_texts")]]
        await update.callback_query.edit_message_text(f"✏️ **تعديل نص الاتصال**\n\nالنص الحالي:\n{current_text}\n\nأرسل النص الجديد:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def admin_images(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manage images"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton("🖼️ صورة البداية", callback_data="change_welcome_image")],
            [InlineKeyboardButton("🗑️ حذف صورة البداية", callback_data="delete_welcome_image")],
            [InlineKeyboardButton("📸 صورة الباقات", callback_data="change_packages_image")],
            [InlineKeyboardButton("🗑️ حذف صورة الباقات", callback_data="delete_packages_image")],
            [InlineKeyboardButton("🖼️ صورة الأسئلة", callback_data="change_faq_image")],
            [InlineKeyboardButton("🗑️ حذف صورة الأسئلة", callback_data="delete_faq_image")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_main")]
        ]
        await update.callback_query.edit_message_text("🖼️ **إدارة الصور**\n\nاختر الصورة التي تريد إدارتها:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def change_welcome_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Change welcome image"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        context.user_data['awaiting_input'] = 'change_welcome_image'
        keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="admin_images")]]
        await update.callback_query.edit_message_text("🖼️ **تغيير صورة البداية**\n\nأرسل الصورة الجديدة:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def change_packages_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Change packages image"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        context.user_data['awaiting_input'] = 'change_packages_image'
        keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="admin_images")]]
        await update.callback_query.edit_message_text("📸 **تغيير صورة الباقات**\n\nأرسل الصورة الجديدة:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def change_faq_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Change FAQ image"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        context.user_data['awaiting_input'] = 'change_faq_image'
        keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="admin_images")]]
        await update.callback_query.edit_message_text("🖼️ **تغيير صورة الأسئلة**\n\nأرسل الصورة الجديدة:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def delete_welcome_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete welcome image"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        self.delete_bot_image('welcome')
        await update.callback_query.edit_message_text("✅ تم حذف صورة البداية بنجاح!")
        await self.admin_images(update, context)

    async def delete_packages_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete packages image"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        self.delete_bot_image('packages')
        await update.callback_query.edit_message_text("✅ تم حذف صورة الباقات بنجاح!")
        await self.admin_images(update, context)

    async def delete_faq_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete FAQ image"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        self.delete_bot_image('faq')
        await update.callback_query.edit_message_text("✅ تم حذف صورة الأسئلة بنجاح!")
        await self.admin_images(update, context)

    async def admin_router_files(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manage router files"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton("➕ إضافة ملف", callback_data="add_router_file")],
            [InlineKeyboardButton("📋 عرض الملفات", callback_data="list_router_files")],
            [InlineKeyboardButton("🗑️ حذف ملف", callback_data="delete_router_file")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_main")]
        ]
        await update.callback_query.edit_message_text("📁 **إدارة ملفات الراوتر**\n\nاختر العملية:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def add_router_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add router file"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        context.user_data['awaiting_input'] = 'add_router_file'
        keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="admin_router_files")]]
        instructions = "📥 **إضافة ملف راوتر**\n\nأرسل البيانات بالتنسيق:\nنوع_الاتصال (adsl/ftth)\nاسم الراوتر\nوصف الملف"
        await update.callback_query.edit_message_text(instructions, reply_markup=InlineKeyboardMarkup(keyboard))

    async def list_router_files(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List router files"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        files = self.get_all_router_files()
        if not files:
            await update.callback_query.edit_message_text("📭 لا توجد ملفات")
            return
        
        message = "📁 **ملفات الراوتر:**\n\n"
        for file in files:
            message += f"• {file['type'].upper()}: {file['router_name']}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_router_files")]]
        await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def delete_router_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete router file"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        files = self.get_all_router_files()
        if not files:
            await update.callback_query.edit_message_text("📭 لا توجد ملفات")
            return
        
        keyboard = []
        for file in files:
            keyboard.append([InlineKeyboardButton(f"🗑️ {file['type']} - {file['router_name']}", callback_data=f"delete_file_{file['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_router_files")])
        await update.callback_query.edit_message_text("🗑️ **حذف ملف راوتر**\n\nاختر الملف الذي تريد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def admin_packages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manage packages"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton("➕ إضافة باقة", callback_data="add_package")],
            [InlineKeyboardButton("📋 عرض الباقات", callback_data="list_packages")],
            [InlineKeyboardButton("🗑️ حذف باقة", callback_data="delete_package")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_main")]
        ]
        await update.callback_query.edit_message_text("💰 **إدارة الباقات**\n\nاختر العملية:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def add_package(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add new package"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        context.user_data['awaiting_input'] = 'add_package'
        keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="admin_packages")]]
        instructions = "💰 **إضافة باقة جديدة**\n\nأرسل البيانات بالتنسيق:\nاسم الباقة\nالسعر\nالسرعة\nالمميزات (مفصولة بفاصلة)"
        await update.callback_query.edit_message_text(instructions, reply_markup=InlineKeyboardMarkup(keyboard))

    async def list_packages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List packages"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        packages = self.get_packages_from_db()
        if not packages:
            await update.callback_query.edit_message_text("📭 لا توجد باقات")
            return
        
        message = "💰 **الباقات المتاحة:**\n\n"
        for pkg in packages:
            message += f"• {pkg['name']} - {pkg['price']}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_packages")]]
        await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def delete_package(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete package"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        packages = self.get_packages_from_db()
        if not packages:
            await update.callback_query.edit_message_text("📭 لا توجد باقات")
            return
        
        keyboard = []
        for pkg in packages:
            keyboard.append([InlineKeyboardButton(f"🗑️ {pkg['name']}", callback_data=f"delete_package_{pkg['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_packages")])
        await update.callback_query.edit_message_text("🗑️ **حذف باقة**\n\nاختر الباقة التي تريد حذفها:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def admin_faq(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manage FAQ"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton("➕ إضافة سؤال", callback_data="add_faq")],
            [InlineKeyboardButton("📋 عرض الأسئلة", callback_data="list_faq")],
            [InlineKeyboardButton("🗑️ حذف سؤال", callback_data="delete_faq")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_main")]
        ]
        await update.callback_query.edit_message_text("❓ **إدارة الأسئلة الشائعة**\n\nاختر العملية:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def add_faq(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add new FAQ"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        context.user_data['awaiting_input'] = 'add_faq'
        keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="admin_faq")]]
        instructions = "❓ **إضافة سؤال شائع**\n\nأرسل البيانات بالتنسيق:\nالسؤال\nالجواب"
        await update.callback_query.edit_message_text(instructions, reply_markup=InlineKeyboardMarkup(keyboard))

    async def list_faq(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List FAQ"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        faqs = self.get_faq_from_db()
        if not faqs:
            await update.callback_query.edit_message_text("📭 لا توجد أسئلة")
            return
        
        message = "❓ **الأسئلة الشائعة:**\n\n"
        for faq in faqs:
            message += f"• {faq['question']}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_faq")]]
        await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def delete_faq(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete FAQ"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        faqs = self.get_faq_from_db()
        if not faqs:
            await update.callback_query.edit_message_text("📭 لا توجد أسئلة")
            return
        
        keyboard = []
        for faq in faqs:
            keyboard.append([InlineKeyboardButton(f"🗑️ {faq['question'][:30]}...", callback_data=f"delete_faq_{faq['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_faq")])
        await update.callback_query.edit_message_text("🗑️ **حذف سؤال**\n\nاختر السؤال الذي تريد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def admin_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manage admins"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton("👥 عرض الأدمن", callback_data="list_admins")],
            [InlineKeyboardButton("➕ إضافة أدمن", callback_data="add_admin")],
            [InlineKeyboardButton("🗑️ حذف أدمن", callback_data="remove_admin")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_main")]
        ]
        await update.callback_query.edit_message_text("👥 **إدارة الأدمن**\n\nاختر العملية:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def list_admins(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List admins"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        admins = self.get_admins_from_db()
        message = "👥 **قائمة الأدمن:**\n\n"
        for admin in admins:
            message += f"• `{admin['user_id']}` - {admin['username'] or 'بدون معرف'}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_management")]]
        await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def add_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add new admin"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        context.user_data['awaiting_input'] = 'add_admin'
        keyboard = [[InlineKeyboardButton("🔙 إلغاء", callback_data="admin_management")]]
        await update.callback_query.edit_message_text("➕ **إضافة أدمن جديد**\n\nأرسل معرف المستخدم الرقمي:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def remove_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove admin"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        admins = self.get_admins_from_db()
        if len(admins) <= 1:
            await update.callback_query.edit_message_text("⚠️ لا يمكن حذف آخر أدمن")
            return
        
        keyboard = []
        for admin in admins:
            if admin['user_id'] != update.callback_query.from_user.id:
                keyboard.append([InlineKeyboardButton(f"🗑️ {admin['user_id']}", callback_data=f"delete_admin_{admin['user_id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_management")])
        await update.callback_query.edit_message_text("🗑️ **حذف أدمن**\n\nاختر الأدمن الذي تريد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show statistics"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        stats = self.get_bot_stats()
        user_stats = self.get_user_stats()
        
        stats_text = f"""
📊 **إحصائيات البوت**

👥 **المستخدمين:**
   • المستخدمين الفريدين: {user_stats['total_users']}
   • إجمالي مرات الاستخدام: {user_stats['total_usage']}
   • متوسط الاستخدام لكل مستخدم: {user_stats['avg_usage']}

📁 **الملفات والمحتوى:**
   • ملفات ADSL: {stats['adsl_files']}
   • ملفات FTTH: {stats['ftth_files']}
   • إجمالي الملفات: {stats['total_files']}
   • الباقات: {stats['total_packages']}
   • الأسئلة: {stats['total_faq']}

⚙️ **الإعدادات:**
   • الأدمن: {stats['total_admins']}
   • الصور: {stats['total_images']}
   • النصوص: {stats['total_texts']}
"""
        keyboard = [
            [InlineKeyboardButton("🔄 تحديث", callback_data="admin_stats")],
            [InlineKeyboardButton("📈 تفاصيل المستخدمين", callback_data="user_details")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_main")]
        ]
        await update.callback_query.edit_message_text(stats_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def user_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user details"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        users = self.get_all_users()
        if not users:
            await update.callback_query.edit_message_text("📭 لا توجد بيانات مستخدمين")
            return
        
        message = "👥 **تفاصيل المستخدمين:**\n\n"
        for i, user in enumerate(users[:10], 1):  # عرض أول 10 مستخدمين فقط
            message += f"{i}. {user['first_name'] or 'بدون اسم'} ({user['user_id']})\n"
            message += f"   الاستخدام: {user['usage_count']} مرة\n"
            message += f"   أول استخدام: {user['first_seen'][:16]}\n"
            message += f"   آخر استخدام: {user['last_seen'][:16]}\n\n"
        
        if len(users) > 10:
            message += f"📝 وإجمالي {len(users)} مستخدم"
        
        keyboard = [
            [InlineKeyboardButton("🔙 رجوع للإحصائيات", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 لوحة الأدمن", callback_data="admin_main")]
        ]
        await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # Helper functions for queries
    async def start_from_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start from query"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.edit_message_text(" **البوت تحت الصيانة**")
            return
            
        user = update.callback_query.from_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        keyboard = [
            [InlineKeyboardButton("⚙️ إعدادات الراوتر", callback_data="router_settings")],
            [InlineKeyboardButton("💰 الأسعار والعروض", callback_data="prices_offers")],
            [InlineKeyboardButton("❓ الأسئلة الشائعة", callback_data="faq")],
            [InlineKeyboardButton("📞 اتصل بنا", callback_data="contact")],
            [InlineKeyboardButton("🔗 مشاركة البوت", callback_data="share_bot")]
        ]
        
        if self.is_admin(user.id):
            keyboard.append([InlineKeyboardButton("🛠️ لوحة الأدمن", callback_data="admin_main")])
        
        welcome_text = self.get_bot_text('welcome')
        await update.callback_query.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def admin_panel_from_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel from query"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton("📝 إدارة النصوص", callback_data="admin_texts")],
            [InlineKeyboardButton("🖼️ إدارة الصور", callback_data="admin_images")],
            [InlineKeyboardButton("📁 إدارة الملفات", callback_data="admin_router_files")],
            [InlineKeyboardButton("💰 إدارة الباقات", callback_data="admin_packages")],
            [InlineKeyboardButton("❓ إدارة الأسئلة", callback_data="admin_faq")],
            [InlineKeyboardButton("👥 إدارة الأدمن", callback_data="admin_management")],
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
            [InlineKeyboardButton("🔧 الصيانة", callback_data="admin_maintenance")],
            [InlineKeyboardButton("📢 البث", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        await update.callback_query.edit_message_text("🛠️ **لوحة تحكم الأدمن**\n\nاختر القسم الذي تريد إدارته:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def router_settings_from_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Router settings from query"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.edit_message_text(" **البوت تحت الصيانة**")
            return
            
        user = update.callback_query.from_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        keyboard = [
            [InlineKeyboardButton("📶 ADSL", callback_data="router_adsl")],
            [InlineKeyboardButton("🌐 FTTH", callback_data="router_ftth")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        text = self.get_bot_text('router_settings')
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def show_prices_from_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show prices from query"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.edit_message_text(" **البوت تحت الصيانة**")
            return
            
        user = update.callback_query.from_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        packages = self.get_packages_from_db()
        if not packages:
            await update.callback_query.edit_message_text("📭 لا توجد باقات متاحة حالياً")
            return
        
        packages_image = self.get_bot_image('packages')
        if packages_image:
            await update.callback_query.message.reply_photo(photo=packages_image, caption="💰 **باقاتنا المتاحة**", parse_mode='Markdown')
        else:
            await update.callback_query.message.reply_text("💰 **باقاتنا المتاحة**", parse_mode='Markdown')
        
        for package in packages:
            features_text = '\n'.join([f'• {feature}' for feature in package['features']])
            package_text = f"**{package['name']}**\n💰 السعر: {package['price']}\n⚡ السرعة: {package['speed']}\n\n✨ المميزات:\n{features_text}"
            await update.callback_query.message.reply_text(package_text, parse_mode='Markdown')
        
        keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]]
        await update.callback_query.message.reply_text("اختر الخطوة التالية:", reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_faq_from_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show FAQ from query"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.edit_message_text(" **البوت تحت الصيانة**")
            return
            
        user = update.callback_query.from_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        faqs = self.get_faq_from_db()
        if not faqs:
            await update.callback_query.edit_message_text("📭 لا توجد أسئلة شائعة حالياً")
            return
        
        faq_image = self.get_bot_image('faq')
        if faq_image:
            await update.callback_query.message.reply_photo(photo=faq_image, caption="❓ **الأسئلة الشائعة**", parse_mode='Markdown')
        else:
            await update.callback_query.message.reply_text("❓ **الأسئلة الشائعة**", parse_mode='Markdown')
        
        for faq in faqs:
            await update.callback_query.message.reply_text(f"❓ **{faq['question']}**\n\n✅ {faq['answer']}", parse_mode='Markdown')
        
        keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]]
        await update.callback_query.message.reply_text("اختر الخطوة التالية:", reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_contact_from_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show contact from query"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.edit_message_text(" **البوت تحت الصيانة**")
            return
            
        user = update.callback_query.from_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        contact_info = self.get_bot_text('contact')
        keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(contact_info, reply_markup=reply_markup, parse_mode='Markdown')

    async def share_bot_from_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Share bot from query"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.edit_message_text(" **البوت تحت الصيانة**")
            return
            
        user = update.callback_query.from_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        share_text = f"🤖 **بوت الخدمات المتكامل**\n\n🔗 رابط البوت: https://t.me/{bot_username}\n\n✅ خدماتنا:\n• ⚙️ إعدادات الراوتر\n• 💰 باقات الإنترنت\n• ❓ دعم فني\n• 📞 خدمة عملاء"
        
        keyboard = [
            [InlineKeyboardButton("🔗 مشاركة الرابط", url=f"https://t.me/share/url?url=https://t.me/{bot_username}")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(share_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def show_router_files(self, update: Update, context: ContextTypes.DEFAULT_TYPE, router_type):
        """Show router files"""
        # Check maintenance mode
        if self.maintenance_mode and not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.edit_message_text(" **البوت تحت الصيانة**")
            return
            
        user = update.callback_query.from_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        router_files = self.get_router_files(router_type)
        if router_files:
            for file_info in router_files:
                try:
                    await update.callback_query.message.reply_document(
                        document=file_info['file_id'],
                        caption=f"📁 **{file_info['router_name']}**\n\n{file_info['description']}",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    await update.callback_query.message.reply_text(f"📁 **{file_info['router_name']}**\n\n{file_info['description']}\n\n❌ تعذر إرسال الملف", parse_mode='Markdown')
        else:
            await update.callback_query.message.reply_text("⚠️ لا توجد ملفات متاحة لهذا النوع حالياً.")
        
        keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]]
        await update.callback_query.message.reply_text("اختر الخطوة التالية:", reply_markup=InlineKeyboardMarkup(keyboard))

    # Delete confirmation functions
    async def confirm_delete_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE, file_id):
        """Confirm file deletion"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        file_info = self.get_router_file_by_id(file_id)
        if not file_info:
            await update.callback_query.edit_message_text("❌ الملف غير موجود")
            return
        
        keyboard = [
            [InlineKeyboardButton("✅ تأكيد الحذف", callback_data=f"confirm_delete_file_{file_id}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_delete_file")]
        ]
        await update.callback_query.edit_message_text(f"🗑️ **تأكيد حذف الملف**\n\nهل أنت متأكد من حذف ملف:\n{file_info['router_name']}؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def confirm_delete_package(self, update: Update, context: ContextTypes.DEFAULT_TYPE, package_id):
        """Confirm package deletion"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        package = self.get_package_by_id(package_id)
        if not package:
            await update.callback_query.edit_message_text("❌ الباقة غير موجودة")
            return
        
        keyboard = [
            [InlineKeyboardButton("✅ تأكيد الحذف", callback_data=f"confirm_delete_package_{package_id}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_delete_package")]
        ]
        await update.callback_query.edit_message_text(f"🗑️ **تأكيد حذف الباقة**\n\nهل أنت متأكد من حذف باقة:\n{package['name']}؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def confirm_delete_faq(self, update: Update, context: ContextTypes.DEFAULT_TYPE, faq_id):
        """Confirm FAQ deletion"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        faq = self.get_faq_by_id(faq_id)
        if not faq:
            await update.callback_query.edit_message_text("❌ السؤال غير موجود")
            return
        
        keyboard = [
            [InlineKeyboardButton("✅ تأكيد الحذف", callback_data=f"confirm_delete_faq_{faq_id}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_delete_faq")]
        ]
        await update.callback_query.edit_message_text(f"🗑️ **تأكيد حذف السؤال**\n\nهل أنت متأكد من حذف سؤال:\n{faq['question']}؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def confirm_delete_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id):
        """Confirm admin deletion"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        admin = self.get_admin_by_id(admin_id)
        if not admin:
            await update.callback_query.edit_message_text("❌ الأدمن غير موجود")
            return
        
        keyboard = [
            [InlineKeyboardButton("✅ تأكيد الحذف", callback_data=f"confirm_delete_admin_{admin_id}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_delete_admin")]
        ]
        await update.callback_query.edit_message_text(f"🗑️ **تأكيد حذف الأدمن**\n\nهل أنت متأكد من حذف الأدمن:\n{admin['user_id']}؟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def execute_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, item_id: int):
        """Execute delete operation"""
        if not self.is_admin(update.callback_query.from_user.id):
            await update.callback_query.answer("⛔ ليس لديك صلاحية", show_alert=True)
            return

        try:
            if action == 'file':
                self.delete_router_file(item_id)
                message = "✅ تم حذف الملف بنجاح"
                callback = "admin_router_files"
            elif action == 'package':
                self.delete_package(item_id)
                message = "✅ تم حذف الباقة بنجاح"
                callback = "admin_packages"
            elif action == 'faq':
                self.delete_faq(item_id)
                message = "✅ تم حذف السؤال بنجاح"
                callback = "admin_faq"
            elif action == 'admin':
                self.delete_admin(item_id)
                self.load_admins()
                message = "✅ تم حذف الأدمن بنجاح"
                callback = "admin_management"
            else:
                message = "❌ نوع الحذف غير معروف"
                callback = "admin_main"
            
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data=callback)]]
            await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            await update.callback_query.edit_message_text(f"❌ خطأ في الحذف: {str(e)}")

    async def cancel_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
        """Cancel delete operation"""
        callback_map = {
            'file': 'admin_router_files',
            'package': 'admin_packages', 
            'faq': 'admin_faq',
            'admin': 'admin_management'
        }
        
        callback = callback_map.get(action, 'admin_main')
        await self.button_handler(update, context)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        user = update.effective_user
        self.update_user_stats(user.id, user.username, user.first_name, user.last_name)
        
        text = update.message.text
        awaiting_input = context.user_data.get('awaiting_input')
        
        if not awaiting_input:
            return

        try:
            if awaiting_input == 'edit_welcome_text':
                if not self.is_admin(user.id): return
                self.save_bot_text('welcome', text)
                context.user_data['awaiting_input'] = None
                await update.message.reply_text("✅ تم تحديث نص البداية بنجاح!")
                await self.admin_texts(update, context)
            
            elif awaiting_input == 'edit_settings_text':
                if not self.is_admin(user.id): return
                self.save_bot_text('router_settings', text)
                context.user_data['awaiting_input'] = None
                await update.message.reply_text("✅ تم تحديث نص الإعدادات بنجاح!")
                await self.admin_texts(update, context)
            
            elif awaiting_input == 'edit_contact_text':
                if not self.is_admin(user.id): return
                self.save_bot_text('contact', text)
                context.user_data['awaiting_input'] = None
                await update.message.reply_text("✅ تم تحديث نص الاتصال بنجاح!")
                await self.admin_texts(update, context)
            
            elif awaiting_input == 'add_router_file':
                if not self.is_admin(user.id): return
                lines = text.split('\n')
                if len(lines) >= 3:
                    context.user_data['new_router_file'] = {
                        'type': lines[0].strip().lower(),
                        'router_name': lines[1].strip(),
                        'description': lines[2].strip()
                    }
                    context.user_data['awaiting_input'] = 'awaiting_router_file'
                    await update.message.reply_text("✅ تم حفظ البيانات. الآن قم بإرسال الملف:")
                else:
                    await update.message.reply_text("❌ البيانات غير مكتملة")
            
            elif awaiting_input == 'add_package':
                if not self.is_admin(user.id): return
                lines = text.split('\n')
                if len(lines) >= 4:
                    features = [f.strip() for f in lines[3].split(',')]
                    self.add_package_to_db(lines[0].strip(), lines[1].strip(), lines[2].strip(), features)
                    context.user_data['awaiting_input'] = None
                    await update.message.reply_text("✅ تم إضافة الباقة بنجاح!")
                    await self.admin_packages(update, context)
                else:
                    await update.message.reply_text("❌ البيانات غير مكتملة")
            
            elif awaiting_input == 'add_faq':
                if not self.is_admin(user.id): return
                lines = text.split('\n')
                if len(lines) >= 2:
                    self.add_faq_to_db(lines[0].strip(), lines[1].strip())
                    context.user_data['awaiting_input'] = None
                    await update.message.reply_text("✅ تم إضافة السؤال بنجاح!")
                    await self.admin_faq(update, context)
                else:
                    await update.message.reply_text("❌ يرجى إرسال السؤال والجواب في سطرين منفصلين.")
            
            elif awaiting_input == 'add_admin':
                if not self.is_admin(user.id): return
                try:
                    new_admin_id = int(text.strip())
                    if not self.is_admin(new_admin_id):
                        self.add_admin_to_db(new_admin_id, user.username)
                        self.load_admins()
                        await update.message.reply_text(f"✅ تم إضافة الأدمن: `{new_admin_id}`", parse_mode='Markdown')
                        await self.admin_management(update, context)
                    else:
                        await update.message.reply_text("⚠️ هذا المستخدم مسجل كأدمن مسبقاً.")
                except ValueError:
                    await update.message.reply_text("❌ الرقم غير صحيح. يرجى إرسال معرف رقمي صحيح.")
                context.user_data['awaiting_input'] = None
            
            elif awaiting_input == 'send_broadcast':
                if not self.is_admin(user.id): return
                users = self.get_all_users()
                
                if not users:
                    await update.message.reply_text("📭 لم يتم العثور على مستخدمين في قاعدة البيانات.")
                    context.user_data['awaiting_input'] = None
                    return

                await update.message.reply_text(f"📤 بدء البث إلى {len(users)} مستخدم...")
                
                success_count = 0
                fail_count = 0
                
                for user_data in users:
                    try:
                        await context.bot.send_message(
                            chat_id=user_data['user_id'],
                            text=f"📢 **إعلان من الأدمن**\n\n{text}",
                            parse_mode='Markdown'
                        )
                        success_count += 1
                        await asyncio.sleep(0.1)  # Rate limiting
                    except Exception as e:
                        fail_count += 1
                        continue

                await update.message.reply_text(
                    f"📊 **اكتمل البث**\n\n"
                    f"✅ ناجح: {success_count}\n"
                    f"❌ فاشل: {fail_count}\n"
                    f"📝 الإجمالي: {len(users)}"
                )
                context.user_data['awaiting_input'] = None
        
        except Exception as e:
            await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
            context.user_data['awaiting_input'] = None

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle documents"""
        user = update.effective_user
        if not self.is_admin(user.id): return

        if context.user_data.get('awaiting_input') == 'awaiting_router_file':
            document = update.message.document
            file_id = document.file_id
            file_name = document.file_name
            
            router_data = context.user_data['new_router_file']
            self.add_router_file_to_db(router_data['type'], router_data['router_name'], file_id, router_data['description'], file_name)
            
            context.user_data['awaiting_input'] = None
            context.user_data.pop('new_router_file', None)
            
            await update.message.reply_text("✅ تم إضافة ملف الراوتر بنجاح!")
            await self.admin_router_files(update, context)

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photos"""
        user = update.effective_user
        if not self.is_admin(user.id): return

        awaiting_input = context.user_data.get('awaiting_input')
        photo = update.message.photo[-1]

        if awaiting_input == 'change_welcome_image':
            self.save_bot_image('welcome', photo.file_id)
            context.user_data['awaiting_input'] = None
            await update.message.reply_text("✅ تم تغيير صورة البداية بنجاح!")
            await self.admin_images(update, context)
        
        elif awaiting_input == 'change_packages_image':
            self.save_bot_image('packages', photo.file_id)
            context.user_data['awaiting_input'] = None
            await update.message.reply_text("✅ تم تغيير صورة الباقات بنجاح!")
            await self.admin_images(update, context)
        
        elif awaiting_input == 'change_faq_image':
            self.save_bot_image('faq', photo.file_id)
            context.user_data['awaiting_input'] = None
            await update.message.reply_text("✅ تم تغيير صورة الأسئلة بنجاح!")
            await self.admin_images(update, context)

    # Database functions
    def get_bot_text(self, text_type):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT content FROM bot_texts WHERE type = ?", (text_type,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "النص غير محدد"
    
    def save_bot_text(self, text_type, content):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO bot_texts (type, content) VALUES (?, ?)', (text_type, content))
        conn.commit()
        conn.close()
    
    def get_bot_image(self, image_type):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT file_id FROM bot_images WHERE type = ?", (image_type,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def save_bot_image(self, image_type, file_id):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO bot_images (type, file_id) VALUES (?, ?)', (image_type, file_id))
        conn.commit()
        conn.close()
    
    def delete_bot_image(self, image_type):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bot_images WHERE type = ?", (image_type,))
        conn.commit()
        conn.close()

    # this for give option to users
        

    def get_router_files(self, router_type):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM router_files WHERE type = ?", (router_type,))
        files = cursor.fetchall()
        conn.close()
        return [{'id': f[0], 'type': f[1], 'router_name': f[2], 'file_id': f[3], 'description': f[4], 'file_name': f[5]} for f in files]
    
    def get_all_router_files(self):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM router_files")
        files = cursor.fetchall()
        conn.close()
        return [{'id': f[0], 'type': f[1], 'router_name': f[2], 'file_id': f[3], 'description': f[4], 'file_name': f[5]} for f in files]
    
    def get_router_file_by_id(self, file_id):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM router_files WHERE id = ?", (file_id,))
        file = cursor.fetchone()
        conn.close()
        if file:
            return {'id': file[0], 'type': file[1], 'router_name': file[2], 'file_id': file[3], 'description': file[4], 'file_name': file[5]}
        return None
    
    #  this can make code more cleaning


    def add_router_file_to_db(self, file_type, router_name, file_id, description, file_name):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO router_files (type, router_name, file_id, description, file_name) VALUES (?, ?, ?, ?, ?)', (file_type, router_name, file_id, description, file_name))
        conn.commit()
        conn.close()
    
    def delete_router_file(self, file_id):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM router_files WHERE id = ?", (file_id,))
        conn.commit()
        conn.close()
    
    def get_faq_from_db(self):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM faq")
        faqs = cursor.fetchall()
        conn.close()
        return [{'id': f[0], 'question': f[1], 'answer': f[2]} for f in faqs]
    
    def get_faq_by_id(self, faq_id):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM faq WHERE id = ?", (faq_id,))
        faq = cursor.fetchone()
        conn.close()
        if faq:
            return {'id': faq[0], 'question': faq[1], 'answer': faq[2]}
        return None
    
    def add_faq_to_db(self, question, answer):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO faq (question, answer) VALUES (?, ?)', (question, answer))
        conn.commit()
        conn.close()
    
    def delete_faq(self, faq_id):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM faq WHERE id = ?", (faq_id,))
        conn.commit()
        conn.close()
    
    def get_packages_from_db(self):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM packages")
        packages = cursor.fetchall()
        conn.close()
        return [{'id': p[0], 'name': p[1], 'price': p[2], 'speed': p[3], 'features': json.loads(p[4]) if p[4] else []} for p in packages]
    
    def get_package_by_id(self, package_id):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM packages WHERE id = ?", (package_id,))
        package = cursor.fetchone()
        conn.close()
        if package:
            return {'id': package[0], 'name': package[1], 'price': package[2], 'speed': package[3], 'features': json.loads(package[4]) if package[4] else []}
        return None
    
    def add_package_to_db(self, name, price, speed, features):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        features_json = json.dumps(features)
        cursor.execute('INSERT INTO packages (name, price, speed, features) VALUES (?, ?, ?, ?)', (name, price, speed, features_json))
        conn.commit()
        conn.close()
    
    def delete_package(self, package_id):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM packages WHERE id = ?", (package_id,))
        conn.commit()
        conn.close()
    
    def get_admins_from_db(self):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins")
        admins = cursor.fetchall()
        conn.close()
        return [{'user_id': a[0], 'username': a[1]} for a in admins]
    
    def get_admin_by_id(self, admin_id):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE user_id = ?", (admin_id,))
        admin = cursor.fetchone()
        conn.close()
        if admin:
            return {'user_id': admin[0], 'username': admin[1]}
        return None
    
    def add_admin_to_db(self, user_id, username):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO admins (user_id, username) VALUES (?, ?)', (user_id, username))
        conn.commit()
        conn.close()
    
     
    #    start bot

    def delete_admin(self, user_id):
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    def get_user_stats(self):
        """Get user statistics"""
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM user_stats")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(usage_count) FROM user_stats")
        total_usage = cursor.fetchone()[0] or 0
        
        avg_usage = total_usage / total_users if total_users > 0 else 0
        
        conn.close()
        
        return {
            'total_users': total_users,
            'total_usage': total_usage,
            'avg_usage': round(avg_usage, 2)
        }
    
    def get_all_users(self):
        """Get all users"""
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_stats ORDER BY last_seen DESC")
        users = cursor.fetchall()
        conn.close()
        
        return [{
            'user_id': u[0],
            'username': u[1],
            'first_name': u[2],
            'last_name': u[3],
            'usage_count': u[4],
            'first_seen': u[5],
            'last_seen': u[6]
        } for u in users]
    
    def get_bot_stats(self):
        """Get bot statistics"""
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM router_files WHERE type = 'adsl'")
        adsl_files = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM router_files WHERE type = 'ftth'")
        ftth_files = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM faq")
        total_faq = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM packages")
        total_packages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM admins")
        total_admins = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM bot_images")
        total_images = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM bot_texts")
        total_texts = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'adsl_files': adsl_files, 'ftth_files': ftth_files,
            'total_files': adsl_files + ftth_files, 'total_packages': total_packages,
            'total_faq': total_faq, 'total_admins': total_admins,
            'total_images': total_images, 'total_texts': total_texts
        }

def main():
    print("🚀 بدء تشغيل البوت...")
    
    if len(BOT_TOKEN) < 20:
        print("❌ يبدو أن التوكن غير صحيح!")
        return
    
    try:
        bot = TelecomBot(BOT_TOKEN)
        print("✅ البوت يعمل بنجاح!")
        print("📱 اذهب إلى تلغرام وجرب الأوامر:")
        print("   /start - القائمة الرئيسية")
        print("   /admin - لوحة التحكم (للمسؤولين فقط)")
        print("   /maintenance - تحكم في الصيانة (للمسؤولين فقط)") 
        print("   /broadcast - إرسال رسالة لجميع المستخدمين (للمسؤولين فقط)")
        bot.application.run_polling()
    except KeyboardInterrupt:
        print("\n🛑 إيقاف البوت...")
    except Exception as e:
        print(f"❌ خطأ: {e}")

if __name__ == '__main__':
    main()