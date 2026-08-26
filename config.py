import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

DB_PATH = os.getenv("DB_PATH", "botdata/prizmquest.db")

admin_ids_raw = os.getenv("ADMIN_TG_IDS", "")

ADMIN_TG_IDS = {
    int(admin_id)
    for admin_id in admin_ids_raw.replace(" ", "").split(",")
    if admin_id.isdigit()
}
