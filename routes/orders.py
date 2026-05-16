import cloudinary.uploader
from datetime import datetime, timezone
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, current_app, jsonify)
from app import db
from models import Order, OrderImage, ConsentLog, Coupon, get_packages, get_addons, get_setting

orders_bp = Blueprint('orders', __name__)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'heic', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@orders_bp.route('/', methods=['GET', 'POST'])
def new_order():
    packages = get_packages()
    addons = get_addons()
    selected_package = request.args.get('package', 'mini')
    if selected_package not in packages:
        selected_package = next(iter(packages), 'mini')
    at_capacity = False
    max_str = get_setting('max_active_orders', '')
    if max_str.isdigit():
        active = Order.query.filter(
            Order.status.in_(['awaiting_payment', 'paid', 'processing', 'ready_for_delivery'])
        ).count()
        at_capacity = active >= int(max_str)
    return render_template('order.html', packages=packages, addons=addons,
                           selected_package=selected_package, at_capacity=at_capacity)


@orders_bp.route('/validate-coupon', methods=['POST'])
def validate_coupon():
    code = request.form.get('code', '').strip().upper()
    try:
        order_total = float(request.form.get('total', 0))
    except (ValueError, TypeError):
        order_total = 0
    coupon = Coupon.query.filter_by(code=code, is_active=True).first()
    if not coupon:
        return jsonify({'valid': False, 'error': 'Invalid or expired coupon code.'})
    if coupon.expires_at and coupon.expires_at < datetime.now(timezone.utc):
        return jsonify({'valid': False, 'error': 'This coupon has expired.'})
    if coupon.uses_left is not None and coupon.uses_left <= 0:
        return jsonify({'valid': False, 'error': 'This coupon has been fully redeemed.'})
    if coupon.min_order and order_total < coupon.min_order:
        return jsonify({'valid': False, 'error': f'Minimum order of R{coupon.min_order:.0f} required.'})
    if coupon.discount_type == 'percent':
        discount = round(order_total * coupon.discount_value / 100, 2)
        label = f'{coupon.discount_value:.0f}% off'
    else:
        discount = min(coupon.discount_value, order_total)
        label = f'R{discount:.0f} off'
    return jsonify({'valid': True, 'discount': discount, 'label': label, 'code': coupon.code})


@orders_bp.route('/upload-image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Use JPG, PNG, HEIC, or WEBP.'}), 400

    try:
        result = cloudinary.uploader.upload(
            file,
            folder='memory-lane-prints',
            resource_type='image',
            transformation=[{'quality': 'auto', 'fetch_format': 'auto'}],
        )
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

    return jsonify({
        'url': result['secure_url'],
        'public_id': result['public_id'],
        'filename': file.filename,
    })


@orders_bp.route('/submit', methods=['POST'])
def submit_order():
    form = request.form
    packages = get_packages()
    addons = get_addons()

    if not form.get('popia_consent'):
        flash('Please accept the POPIA privacy notice to continue.', 'error')
        return redirect(url_for('orders.new_order'))

    package_key = form.get('package')
    if package_key not in packages:
        flash('Invalid package selected.', 'error')
        return redirect(url_for('orders.new_order'))

    selected_addons = form.getlist('addons')
    selected_addons = [a for a in selected_addons if a in addons]

    image_urls = form.getlist('image_urls[]')
    image_public_ids = form.getlist('image_public_ids[]')
    image_filenames = form.getlist('image_filenames[]')
    image_captions = form.getlist('image_captions[]')

    if not image_urls:
        flash('Please upload at least one photo.', 'error')
        return redirect(url_for('orders.new_order', package=package_key))

    pkg = packages[package_key]
    addon_total = sum(addons[k]['price'] for k in selected_addons)
    subtotal = pkg['price']
    total = subtotal + addon_total

    coupon_code_input = form.get('coupon_code', '').strip().upper()
    discount_amount = 0.0
    applied_coupon = None
    if coupon_code_input:
        coupon = Coupon.query.filter_by(code=coupon_code_input, is_active=True).first()
        if coupon and (not coupon.expires_at or coupon.expires_at >= datetime.now(timezone.utc)):
            if (coupon.uses_left is None or coupon.uses_left > 0) and total >= (coupon.min_order or 0):
                if coupon.discount_type == 'percent':
                    discount_amount = round(total * coupon.discount_value / 100, 2)
                else:
                    discount_amount = min(coupon.discount_value, total)
                applied_coupon = coupon

    total = round(total - discount_amount, 2)

    order = Order(
        customer_name=form.get('customer_name', '').strip(),
        customer_email=form.get('customer_email', '').strip(),
        customer_phone=form.get('customer_phone', '').strip(),
        delivery_address=form.get('delivery_address', '').strip(),
        package=package_key,
        addons=selected_addons,
        special_notes=form.get('special_notes', '').strip() or None,
        cover_title=form.get('cover_title', '').strip() or None,
        cover_subtitle=form.get('cover_subtitle', '').strip() or None,
        preface_message=form.get('preface_message', '').strip() or None,
        closing_message=form.get('closing_message', '').strip() or None,
        is_gift=bool(form.get('is_gift')),
        gift_message=form.get('gift_message', '').strip() or None,
        coupon_code=applied_coupon.code if applied_coupon else None,
        discount_amount=discount_amount,
        subtotal=subtotal,
        total=total,
        status='awaiting_payment',
    )
    db.session.add(order)
    db.session.flush()

    if applied_coupon and applied_coupon.uses_left is not None:
        applied_coupon.uses_left = max(0, applied_coupon.uses_left - 1)

    for i, (url, public_id, filename) in enumerate(zip(image_urls, image_public_ids, image_filenames)):
        caption = image_captions[i].strip() if i < len(image_captions) else ''
        img = OrderImage(
            order_id=order.id,
            cloudinary_url=url,
            cloudinary_public_id=public_id,
            original_filename=filename,
            caption=caption or None,
        )
        db.session.add(img)

    from utils.mail import send_order_confirmation
    send_order_confirmation(order)

    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip:
        ip = ip.split(',')[0].strip()
    consent = ConsentLog(
        order_id=order.id,
        order_number=order.order_number,
        customer_name=order.customer_name,
        customer_email=order.customer_email,
        ip_address=ip,
        user_agent=request.user_agent.string[:500] if request.user_agent.string else None,
    )
    db.session.add(consent)

    db.session.commit()

    return redirect(url_for('orders.checkout', order_number=order.order_number))


@orders_bp.route('/checkout/<order_number>')
def checkout(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    app_url = current_app.config['APP_URL']
    return render_template('checkout.html', order=order, packages=get_packages(),
                           addons=get_addons(), app_url=app_url)
