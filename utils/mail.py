import logging
from flask import render_template, current_app
from flask_mail import Message
from app import mail
from models import get_setting

logger = logging.getLogger(__name__)


def _sender():
    username = current_app.config.get('MAIL_USERNAME', '')
    name = get_setting('mail_sender_name', 'Memory Lane Prints')
    return f'{name} <{username}>' if username else None


def _send(msg):
    """Send a message, silently logging any failure so orders never break."""
    sender = _sender()
    if not sender or not current_app.config.get('MAIL_USERNAME'):
        logger.warning('Mail not configured — skipping email "%s"', msg.subject)
        return
    msg.sender = sender
    try:
        mail.send(msg)
    except Exception as exc:
        logger.error('Failed to send email "%s": %s', msg.subject, exc)


def send_order_confirmation(order):
    admin_email = get_setting('admin_email')
    msg = Message(
        subject=f'Your Memory Lane Prints order is confirmed — {order.order_number}',
        recipients=[order.customer_email],
        bcc=[admin_email] if admin_email else [],
        html=render_template('emails/order_confirmation.html', order=order),
    )
    _send(msg)


def send_payment_confirmed_customer(order):
    msg = Message(
        subject=f'Payment confirmed — your book is in production ({order.order_number})',
        recipients=[order.customer_email],
        html=render_template('emails/payment_confirmed.html', order=order),
    )
    _send(msg)


def send_payment_received(order):
    admin_email = get_setting('admin_email')
    if not admin_email:
        return
    msg = Message(
        subject=f'Payment received — {order.order_number}',
        recipients=[admin_email],
        html=render_template('emails/payment_received.html', order=order),
    )
    _send(msg)


def send_processing_email(order):
    msg = Message(
        subject=f'Your book is in production — {order.order_number}',
        recipients=[order.customer_email],
        html=render_template('emails/order_processing.html', order=order),
    )
    _send(msg)


def send_cancelled_email(order):
    msg = Message(
        subject=f'Your order has been cancelled — {order.order_number}',
        recipients=[order.customer_email],
        html=render_template('emails/order_cancelled.html', order=order),
    )
    _send(msg)


def send_shipped_email(order):
    msg = Message(
        subject=f'Your order is on its way — {order.order_number}',
        recipients=[order.customer_email],
        html=render_template('emails/order_shipped.html', order=order),
    )
    _send(msg)


def send_abandoned_order_reminder(order):
    app_url = get_setting('app_url', 'http://localhost:5000')
    msg = Message(
        subject=f'You left something behind — complete your Memory Lane Prints order',
        recipients=[order.customer_email],
        html=render_template('emails/abandoned_order.html', order=order, app_url=app_url),
    )
    _send(msg)


def send_review_request_email(order):
    app_url = get_setting('app_url', 'http://localhost:5000')
    msg = Message(
        subject=f'How was your Memory Lane Prints book? Share your experience',
        recipients=[order.customer_email],
        html=render_template('emails/review_request.html', order=order, app_url=app_url),
    )
    _send(msg)
