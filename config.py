import logging
import os
from dotenv import load_dotenv
from celery import Celery

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

celery_app = Celery(
    "your_project",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0"
)

SECRET = os.getenv('SECRET_KEY', 'your-secret-key-here')
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.mail.ru")
EMAIL_PORT = os.getenv("EMAIL_PORT", "587")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")

logger.info(f"EMAIL_USER: {EMAIL_USER}")
logger.info(f"EMAIL_FROM: {EMAIL_FROM}")