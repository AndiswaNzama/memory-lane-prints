import hashlib
import ipaddress
import urllib.parse
import requests
from flask import (Blueprint, render_template, request, redirect,
                   url_for, abort)
from app import db, csrf
from models import Order, get_setting

payments_bp = Blueprint('payments', __name__)

# PayFast's published IP ranges
PAYFAST_VALID_IPS = [
    ipaddress.ip_network('197.97.145.144/28'),
    ipaddress.ip_network('41.74.179.192/27'),
]


def _is_valid_payfast_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in PAYFAST_VALID_IPS)
    except ValueError:
        return False


def build_payfast_signature(data: dict, passphrase: str = '') -> str:
    payload = {k: v for k, v in data.items() if v != '' and k != 'signature'}
    query = urllib.parse.urlencode(payload)
    if passphrase:
        query += '&passphrase=' + urllib.parse.quote_plus(passphrase)
    return hashlib.md5(query.encode()).hexdigest()


def payfast_url(sandbox: bool) -> str:
    if sandbox:
        return 'https://sandbox.payfast.co.za/eng/process'
    return 'https://www.payfast.co.za/eng/process'


def payfast_validate_url(sandbox: bool) -> str:
    if sandbox:
        return 'https://sandbox.payfast.co.za/eng/query/validate'
    return 'https://www.payfast.co.za/eng/query/validate'


@payments_bp.route('/initiate/<order_number>')
def initiate(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()

    merchant_id  = get_setting('payfast_merchant_id')
    merchant_key = get_setting('payfast_merchant_key')
    passphrase   = get_setting('payfast_passphrase')
    sandbox      = get_setting('payfast_sandbox', 'true') == 'true'
    app_url      = get_setting('app_url', 'http://localhost:5000').rstrip('/')

    data = {
        'merchant_id':          merchant_id,
        'merchant_key':         merchant_key,
        'return_url':           f"{app_url}/payment/success/{order.order_number}",
        'cancel_url':           f"{app_url}/payment/cancel/{order.order_number}",
        'notify_url':           f"{app_url}/payment/notify",
        'name_first':           order.customer_name.split()[0],
        'name_last':            ' '.join(order.customer_name.split()[1:]) or '-',
        'email_address':        order.customer_email,
        'm_payment_id':         order.order_number,
        'amount':               f'{order.total:.2f}',
        'item_name':            f'Memory Lane Prints – {order.get_package_info().get("name", "")}',
        'item_description':     f'Order {order.order_number}',
        'email_confirmation':   '1',
        'confirmation_address': order.customer_email,
    }

    data['signature'] = build_payfast_signature(data, passphrase)

    return render_template(
        'payfast_redirect.html',
        payfast_url=payfast_url(sandbox),
        data=data,
    )


@payments_bp.route('/notify', methods=['POST'])
@csrf.exempt
def notify():
    """PayFast Instant Transfer Notification (ITN) handler."""
    passphrase = get_setting('payfast_passphrase')
    sandbox    = get_setting('payfast_sandbox', 'true') == 'true'

    # 1. Source IP check (skip in sandbox mode)
    if not sandbox:
        source_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        if not _is_valid_payfast_ip(source_ip):
            abort(403, 'Untrusted source IP')

    form_data = request.form.to_dict()

    # 2. Signature check
    received_sig = form_data.pop('signature', '')
    expected_sig = build_payfast_signature(form_data, passphrase)
    if received_sig != expected_sig:
        abort(400, 'Invalid signature')

    # 3. Validate with PayFast's servers
    validate_url = payfast_validate_url(sandbox)
    try:
        resp = requests.post(
            validate_url,
            data={**form_data, 'signature': received_sig},
            headers={'User-Agent': 'Memory Lane Prints ITN'},
            timeout=10,
        )
        if resp.text.strip().upper() != 'VALID':
            abort(400, f'PayFast validation failed: {resp.text}')
    except requests.RequestException:
        # If we can't reach PayFast to validate, reject the ITN
        abort(503, 'Could not reach PayFast for validation')

    # 4. Match order and verify amount
    order_number = form_data.get('m_payment_id')
    order = Order.query.filter_by(order_number=order_number).first()
    if not order:
        abort(404)

    received_amount = float(form_data.get('amount_gross', 0))
    if abs(received_amount - order.total) > 0.01:
        abort(400, 'Amount mismatch')

    # 5. Update order status
    from utils.mail import send_payment_received, send_payment_confirmed_customer
    payment_status = form_data.get('payment_status')
    if payment_status == 'COMPLETE':
        order.status = 'paid'
        order.payfast_payment_id = form_data.get('pf_payment_id', '')
        db.session.commit()
        send_payment_confirmed_customer(order)
        send_payment_received(order)
    elif payment_status == 'CANCELLED':
        order.status = 'cancelled'
        db.session.commit()
    else:
        db.session.commit()

    return 'OK', 200


@payments_bp.route('/success/<order_number>')
def success(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    return render_template('success.html', order=order)


@payments_bp.route('/cancel/<order_number>')
def cancel(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    return render_template('cancel.html', order=order)
