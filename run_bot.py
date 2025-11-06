import asyncio
import new_bot

if __name__ == "__main__":
    try:
        new_bot.main()
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            print("✅ البوت توقف بشكل طبيعي")
        else:
            raise