# check_token.py
BOT_TOKEN = "التوكن_الذي_وضعته"  # استخدم نفس التوكن من new_bot.py

print("🔍 فحص التوكن...")
print(f"📝 التوكن: {BOT_TOKEN}")

if "8379619010:AAHxGdB1s6Dq7UaOMWZ0tKMIUBolaa6tNAg" in BOT_TOKEN or "8379619010:AAHxGdB1s6Dq7UaOMWZ0tKMIUBolaa6tNAg" in BOT_TOKEN or "8379619010:AAHxGdB1s6Dq7UaOMWZ0tKMIUBolaa6tNAg" in BOT_TOKEN:
    print("❌ لم تقم بتحديث التوكن!")
    print("💡 استبدل النص في new_bot.py بالتوكن الحقيقي")
else:
    print("✅ التوكن محدث - جاهز للتشغيل")
    print(f"📏 طول التوكن: {len(BOT_TOKEN)} حرف")