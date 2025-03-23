import smtplib
import ssl
from email.mime.text import MIMEText
from config import celery_app, EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FROM, logger

def send_stock_alert_email(user_email: str, product_name: str, quantity: int, minimum_quantity: int = 10):
    if not user_email:
        logger.warning("Email пользователя не указан")
        return

    subject = "Уведомление о низких остатках"
    body = (
        f"Внимание! Остаток товара '{product_name}' упал ниже {minimum_quantity}. "
        f"Текущее количество: {quantity}."
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = user_email

    try:
        with smtplib.SMTP(EMAIL_HOST, int(EMAIL_PORT)) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email успешно отправлен на {user_email}")
    except Exception as e:
        logger.error(f"Ошибка при отправке email: {str(e)}")
        raise

@celery_app.task
def send_stock_alert_email_task(user_email: str, product_name: str, quantity: int):
    send_stock_alert_email(user_email, product_name, quantity)