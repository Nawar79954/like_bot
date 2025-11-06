import sqlite3

def init_database():
    """إنشاء وتجهيز قاعدة البيانات"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    # جدول ملفات الراوترات
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
    
    # جدول الأسئلة الشائعة
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faq (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # إضافة بيانات نموذجية للأسئلة الشائعة
    default_faq = [
        ('كيف أعيد تشغيل الراوتر؟', 'افصل الكهرباء لمدة 30 ثانية ثم أعد التوصيل.'),
        ('كيف أغير كلمة سر الواي فاي؟', 'ادخل على إعدادات الراوتر عبر 192.168.1.1 ثم قسم Wireless Settings.'),
        ('ما هو عنوان الـ DNS؟', 'يمكنك استخدام 8.8.8.8 و 8.8.4.4 من جوجل.'),
        ('الباقة الأساسية تشمل أي خدمات؟', 'الباقة الأساسية تشمل سرعة 10 ميجا مع دعم فني 24/7.'),
        ('كيف أتصل بالدعم الفني؟', 'يمكنك الاتصال على 0123456789 أو 01112223344 للدعم الفني.')
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO faq (question, answer) 
        VALUES (?, ?)
    ''', default_faq)
    
    conn.commit()
    conn.close()
    print("✅ تم إنشاء قاعدة البيانات بنجاح!")

if __name__ == '__main__':
    init_database()