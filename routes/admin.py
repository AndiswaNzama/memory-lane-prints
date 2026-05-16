import csv
import io
import json
import functools
import cloudinary.uploader
from datetime import datetime, timezone, timedelta
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, current_app, Response)
from sqlalchemy.orm import selectinload
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, limiter
from models import (Order, Package, Addon, Review, ConsentLog, Coupon, GalleryImage, Newsletter,
                    get_packages, get_addons, get_setting, set_setting)

admin_bp = Blueprint('admin', __name__)

STATUSES = [
    ('awaiting_payment', 'Awaiting Payment'),
    ('paid',             'Paid'),
    ('processing',       'Processing'),
    ('ready_for_delivery', 'Ready for Delivery'),
    ('shipped',          'Shipped'),
    ('delivered',        'Delivered'),
    ('cancelled',        'Cancelled'),
]

COURIERS = [
    ('pudo', 'Pudo'),
    ('paxi', 'Paxi'),
]


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login', next=request.url))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute; 3 per 10 seconds')
def login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        stored_hash = get_setting('admin_password_hash')
        env_password = current_app.config.get('ADMIN_PASSWORD', '')
        if stored_hash:
            authenticated = check_password_hash(stored_hash, password)
        else:
            authenticated = password == env_password
        if authenticated:
            session['admin_logged_in'] = True
            session.permanent = True
            return redirect(request.args.get('next') or url_for('admin.dashboard'))
        flash('Incorrect password.', 'error')
    return render_template('admin/login.html')


@admin_bp.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.login'))


@admin_bp.route('/')
@login_required
def dashboard():
    status_filter = request.args.get('status', 'paid')
    query = (
        Order.query
        .options(selectinload(Order.images))
        .order_by(Order.created_at.desc())
    )
    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)
    orders = query.all()

    counts = {}
    for key, _ in STATUSES:
        counts[key] = Order.query.filter_by(status=key).count()
    counts['all'] = Order.query.count()

    from sqlalchemy import func
    total_revenue = db.session.query(func.sum(Order.total)).scalar() or 0
    paid_revenue = db.session.query(func.sum(Order.total)).filter(
        Order.status.in_(['paid', 'processing', 'ready_for_delivery', 'shipped', 'delivered'])
    ).scalar() or 0

    stats = {
        'total_orders': counts['all'],
        'pending': counts.get('awaiting_payment', 0) + Order.query.filter_by(status='pending').count(),
        'paid': counts.get('paid', 0),
        'processing': counts.get('processing', 0),
        'shipped': counts.get('shipped', 0),
        'total_revenue': total_revenue,
        'paid_revenue': paid_revenue,
    }

    today = datetime.now(timezone.utc).date()
    days = [(today - timedelta(days=i)) for i in range(13, -1, -1)]
    chart_labels = [d.strftime('%d %b') for d in days]
    chart_orders, chart_revenue = [], []
    for day in days:
        start = datetime.combine(day, datetime.min.time())
        end   = datetime.combine(day + timedelta(days=1), datetime.min.time())
        count = Order.query.filter(Order.created_at >= start, Order.created_at < end).count()
        rev   = db.session.query(func.sum(Order.total)).filter(
            Order.created_at >= start, Order.created_at < end,
            Order.status.in_(['paid', 'processing', 'ready_for_delivery', 'shipped', 'delivered'])
        ).scalar() or 0
        chart_orders.append(count)
        chart_revenue.append(float(rev))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    abandoned = Order.query.filter(
        Order.status == 'awaiting_payment',
        Order.created_at <= cutoff,
    ).count()

    return render_template('admin/dashboard.html',
                           orders=orders,
                           statuses=STATUSES,
                           counts=counts,
                           current_status=status_filter,
                           packages=get_packages(),
                           stats=stats,
                           chart_labels=json.dumps(chart_labels),
                           chart_orders=json.dumps(chart_orders),
                           chart_revenue=json.dumps(chart_revenue),
                           abandoned_count=abandoned)


@admin_bp.route('/order/<order_number>')
@login_required
def order_detail(order_number):
    order = (
        Order.query
        .options(selectinload(Order.images))
        .filter_by(order_number=order_number)
        .first_or_404()
    )
    return render_template('admin/order_detail.html',
                           order=order,
                           statuses=STATUSES,
                           couriers=COURIERS,
                           packages=get_packages(),
                           addons=get_addons())


@admin_bp.route('/order/<order_number>/update', methods=['POST'])
@login_required
def update_order(order_number):
    from utils.mail import send_shipped_email, send_processing_email, send_cancelled_email
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    prev_status = order.status
    new_status = request.form.get('status')
    courier = request.form.get('courier', '').strip()
    tracking = request.form.get('tracking_number', '').strip()

    valid_statuses = [s[0] for s in STATUSES]
    if new_status in valid_statuses:
        order.status = new_status
    if courier in ('pudo', 'paxi', ''):
        order.courier = courier or None
    if tracking:
        order.tracking_number = tracking
    order.admin_notes = request.form.get('admin_notes', '').strip() or None

    db.session.commit()

    if prev_status != 'processing' and order.status == 'processing':
        send_processing_email(order)
    elif prev_status != 'shipped' and order.status == 'shipped':
        send_shipped_email(order)
    elif prev_status != 'cancelled' and order.status == 'cancelled':
        send_cancelled_email(order)

    flash(f'Order {order.order_number} updated successfully.', 'success')
    return redirect(url_for('admin.order_detail', order_number=order_number))


@admin_bp.route('/catalog')
@login_required
def catalog():
    packages = Package.query.order_by(Package.sort_order).all()
    addons = Addon.query.all()
    return render_template('admin/catalog.html', packages=packages, addons=addons)


@admin_bp.route('/catalog/package/<int:pkg_id>', methods=['POST'])
@login_required
def update_package(pkg_id):
    pkg = Package.query.get_or_404(pkg_id)
    pkg.name        = request.form.get('name', pkg.name).strip()
    pkg.description = request.form.get('description', pkg.description).strip()
    pkg.price       = float(request.form.get('price', pkg.price))
    pkg.is_active   = 'is_active' in request.form
    db.session.commit()
    flash(f'Package "{pkg.name}" updated.', 'success')
    return redirect(url_for('admin.catalog'))


@admin_bp.route('/catalog/addon/<int:addon_id>', methods=['POST'])
@login_required
def update_addon(addon_id):
    addon = Addon.query.get_or_404(addon_id)
    addon.name      = request.form.get('name', addon.name).strip()
    addon.price     = float(request.form.get('price', addon.price))
    addon.is_active = 'is_active' in request.form
    db.session.commit()
    flash(f'Add-on "{addon.name}" updated.', 'success')
    return redirect(url_for('admin.catalog'))


@admin_bp.route('/reviews')
@login_required
def reviews():
    pending  = Review.query.filter_by(is_approved=False).order_by(Review.created_at.desc()).all()
    approved = Review.query.filter_by(is_approved=True).order_by(Review.created_at.desc()).all()
    return render_template('admin/reviews.html', pending=pending, approved=approved)


@admin_bp.route('/reviews/<int:review_id>/approve', methods=['POST'])
@login_required
def approve_review(review_id):
    review = Review.query.get_or_404(review_id)
    review.is_approved = True
    db.session.commit()
    flash('Review approved and now visible on the website.', 'success')
    return redirect(url_for('admin.reviews'))


@admin_bp.route('/reviews/<int:review_id>/reject', methods=['POST'])
@login_required
def reject_review(review_id):
    review = Review.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    flash('Review removed.', 'success')
    return redirect(url_for('admin.reviews'))


@admin_bp.route('/orders/export')
@login_required
def export_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'Order Number', 'Date', 'Customer Name', 'Email', 'Phone',
        'Package', 'Add-ons', 'Subtotal', 'Total',
        'Status', 'Courier', 'Tracking Number', 'Delivery Address', 'Notes',
    ])
    for o in orders:
        writer.writerow([
            o.order_number,
            o.created_at.strftime('%Y-%m-%d %H:%M'),
            o.customer_name,
            o.customer_email,
            o.customer_phone,
            o.package,
            ', '.join(o.addons or []),
            o.subtotal,
            o.total,
            o.status,
            o.courier or '',
            o.tracking_number or '',
            o.delivery_address.replace('\n', ' '),
            o.admin_notes or '',
        ])
    output = buf.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=orders.csv'},
    )


@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        section = request.form.get('form_section', 'payfast')

        if section == 'mail':
            set_setting('mail_server',      request.form.get('mail_server', '').strip())
            set_setting('mail_port',        request.form.get('mail_port', '587').strip())
            set_setting('mail_use_tls',     'true' if request.form.get('mail_use_tls') else 'false')
            set_setting('mail_username',    request.form.get('mail_username', '').strip())
            set_setting('mail_sender_name', request.form.get('mail_sender_name', '').strip())
            new_mail_pw = request.form.get('mail_password', '').strip()
            if new_mail_pw:
                set_setting('mail_password', new_mail_pw)
            db.session.commit()
            _apply_mail_config(current_app)
            flash('Email settings saved.', 'success')
            return redirect(url_for('admin.settings'))

        if section == 'password':
            new_pw     = request.form.get('new_password', '').strip()
            confirm_pw = request.form.get('confirm_password', '').strip()
            current_pw = request.form.get('current_password', '').strip()
            stored_hash  = get_setting('admin_password_hash')
            env_password = current_app.config.get('ADMIN_PASSWORD', '')
            current_ok   = check_password_hash(stored_hash, current_pw) if stored_hash else current_pw == env_password
            if not current_ok:
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('admin.settings'))
            if len(new_pw) < 8:
                flash('New password must be at least 8 characters.', 'error')
                return redirect(url_for('admin.settings'))
            if new_pw != confirm_pw:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('admin.settings'))
            set_setting('admin_password_hash', generate_password_hash(new_pw))
            db.session.commit()
            flash('Password changed successfully.', 'success')
            return redirect(url_for('admin.settings'))

        if section == 'capacity':
            set_setting('max_active_orders', request.form.get('max_active_orders', '').strip())
            db.session.commit()
            flash('Capacity setting saved.', 'success')
            return redirect(url_for('admin.settings'))

        if section == 'about_photo':
            photo_file = request.files.get('about_photo')
            if photo_file and photo_file.filename:
                old_pid = get_setting('about_photo_public_id')
                result = cloudinary.uploader.upload(
                    photo_file,
                    folder='memory-lane-about',
                    resource_type='image',
                    transformation=[{'quality': 'auto', 'fetch_format': 'auto', 'width': 1200, 'crop': 'limit'}],
                )
                set_setting('about_photo_url', result['secure_url'])
                set_setting('about_photo_public_id', result['public_id'])
                db.session.commit()
                if old_pid:
                    try:
                        cloudinary.uploader.destroy(old_pid)
                    except Exception:
                        pass
                flash('About page photo updated.', 'success')
            else:
                flash('No file selected.', 'error')
            return redirect(url_for('admin.settings'))

        # Default: PayFast + contact section
        set_setting('payfast_merchant_id',  request.form.get('payfast_merchant_id', '').strip())
        set_setting('payfast_merchant_key', request.form.get('payfast_merchant_key', '').strip())
        set_setting('app_url',              request.form.get('app_url', '').strip().rstrip('/'))
        set_setting('payfast_sandbox',      'true' if request.form.get('payfast_sandbox') else 'false')
        set_setting('whatsapp_number',      request.form.get('whatsapp_number', '').strip())
        set_setting('instagram_handle',     request.form.get('instagram_handle', '').strip().lstrip('@'))
        set_setting('admin_email',          request.form.get('admin_email', '').strip())
        new_passphrase = request.form.get('payfast_passphrase', '').strip()
        if new_passphrase:
            set_setting('payfast_passphrase', new_passphrase)
        db.session.commit()
        flash('Settings saved.', 'success')
        return redirect(url_for('admin.settings'))

    return render_template('admin/settings.html',
                           merchant_id       = get_setting('payfast_merchant_id'),
                           merchant_key      = get_setting('payfast_merchant_key'),
                           sandbox           = get_setting('payfast_sandbox', 'true') == 'true',
                           app_url           = get_setting('app_url'),
                           whatsapp_number   = get_setting('whatsapp_number'),
                           instagram_handle  = get_setting('instagram_handle'),
                           admin_email       = get_setting('admin_email'),
                           mail_server       = get_setting('mail_server', 'smtp.gmail.com'),
                           mail_port         = get_setting('mail_port', '587'),
                           mail_use_tls      = get_setting('mail_use_tls', 'true') == 'true',
                           mail_username     = get_setting('mail_username'),
                           mail_sender_name  = get_setting('mail_sender_name', 'Memory Lane Prints'),
                           about_photo_url   = get_setting('about_photo_url'),
                           max_active_orders = get_setting('max_active_orders'))


def _apply_mail_config(app):
    """Hot-reload Flask-Mail config from DB settings without restart."""
    app.config['MAIL_SERVER']   = get_setting('mail_server', 'smtp.gmail.com')
    app.config['MAIL_PORT']     = int(get_setting('mail_port', '587'))
    app.config['MAIL_USE_TLS']  = get_setting('mail_use_tls', 'true') == 'true'
    app.config['MAIL_USERNAME'] = get_setting('mail_username')
    app.config['MAIL_PASSWORD'] = get_setting('mail_password')


@admin_bp.route('/orders/delete-awaiting-payment', methods=['POST'])
@login_required
def delete_awaiting_payment():
    orders = Order.query.filter_by(status='awaiting_payment').all()
    count = len(orders)
    for order in orders:
        public_ids = [img.cloudinary_public_id for img in order.images if img.cloudinary_public_id]
        db.session.delete(order)
        db.session.flush()
        for pid in public_ids:
            try:
                cloudinary.uploader.destroy(pid)
            except Exception:
                pass
    db.session.commit()
    flash(f'{count} unpaid order{"s" if count != 1 else ""} deleted.', 'success')
    return redirect(url_for('admin.dashboard', status='awaiting_payment'))


@admin_bp.route('/order/<order_number>/delete', methods=['POST'])
@login_required
def delete_order(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    public_ids = [img.cloudinary_public_id for img in order.images if img.cloudinary_public_id]
    db.session.delete(order)
    db.session.commit()
    for pid in public_ids:
        try:
            cloudinary.uploader.destroy(pid)
        except Exception:
            pass
    flash(f'Order {order_number} deleted.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/customers')
@login_required
def customers():
    from sqlalchemy import func
    rows = (
        db.session.query(
            Order.customer_email,
            Order.customer_name,
            func.count(Order.id).label('order_count'),
            func.sum(Order.total).label('total_spend'),
            func.max(Order.created_at).label('last_order'),
        )
        .group_by(Order.customer_email)
        .order_by(func.max(Order.created_at).desc())
        .all()
    )
    return render_template('admin/customers.html', customers=rows)


@admin_bp.route('/coupons')
@login_required
def coupons():
    all_coupons = Coupon.query.order_by(Coupon.created_at.desc()).all()
    return render_template('admin/coupons.html', coupons=all_coupons)


@admin_bp.route('/coupons/create', methods=['POST'])
@login_required
def create_coupon():
    code = request.form.get('code', '').strip().upper()
    discount_type = request.form.get('discount_type', 'percent')
    try:
        discount_value = float(request.form.get('discount_value', 0))
        min_order = float(request.form.get('min_order', 0) or 0)
    except ValueError:
        flash('Invalid discount value.', 'error')
        return redirect(url_for('admin.coupons'))
    uses_left_raw = request.form.get('uses_left', '').strip()
    uses_left = int(uses_left_raw) if uses_left_raw.isdigit() else None
    expires_raw = request.form.get('expires_at', '').strip()
    expires_at = None
    if expires_raw:
        try:
            expires_at = datetime.strptime(expires_raw, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    if not code:
        flash('Coupon code cannot be empty.', 'error')
        return redirect(url_for('admin.coupons'))
    if Coupon.query.filter_by(code=code).first():
        flash(f'Code "{code}" already exists.', 'error')
        return redirect(url_for('admin.coupons'))
    db.session.add(Coupon(code=code, discount_type=discount_type,
                          discount_value=discount_value, min_order=min_order,
                          uses_left=uses_left, expires_at=expires_at))
    db.session.commit()
    flash(f'Coupon "{code}" created.', 'success')
    return redirect(url_for('admin.coupons'))


@admin_bp.route('/coupons/<int:coupon_id>/toggle', methods=['POST'])
@login_required
def toggle_coupon(coupon_id):
    coupon = Coupon.query.get_or_404(coupon_id)
    coupon.is_active = not coupon.is_active
    db.session.commit()
    flash(f'"{coupon.code}" {"activated" if coupon.is_active else "deactivated"}.', 'success')
    return redirect(url_for('admin.coupons'))


@admin_bp.route('/coupons/<int:coupon_id>/delete', methods=['POST'])
@login_required
def delete_coupon(coupon_id):
    coupon = Coupon.query.get_or_404(coupon_id)
    code = coupon.code
    db.session.delete(coupon)
    db.session.commit()
    flash(f'Coupon "{code}" deleted.', 'success')
    return redirect(url_for('admin.coupons'))


@admin_bp.route('/gallery')
@login_required
def admin_gallery():
    images = GalleryImage.query.order_by(GalleryImage.sort_order, GalleryImage.uploaded_at.desc()).all()
    return render_template('admin/gallery.html', images=images)


@admin_bp.route('/gallery/upload', methods=['POST'])
@login_required
def gallery_upload():
    photo_file = request.files.get('photo')
    if not photo_file or not photo_file.filename:
        flash('No file selected.', 'error')
        return redirect(url_for('admin.admin_gallery'))
    caption = request.form.get('caption', '').strip() or None
    result = cloudinary.uploader.upload(
        photo_file,
        folder='memory-lane-gallery',
        resource_type='image',
        transformation=[{'quality': 'auto', 'fetch_format': 'auto', 'width': 1400, 'crop': 'limit'}],
    )
    db.session.add(GalleryImage(
        cloudinary_url=result['secure_url'],
        cloudinary_public_id=result['public_id'],
        caption=caption,
    ))
    db.session.commit()
    flash('Photo added to gallery.', 'success')
    return redirect(url_for('admin.admin_gallery'))


@admin_bp.route('/gallery/<int:img_id>/toggle', methods=['POST'])
@login_required
def gallery_toggle(img_id):
    img = GalleryImage.query.get_or_404(img_id)
    img.is_active = not img.is_active
    db.session.commit()
    return redirect(url_for('admin.admin_gallery'))


@admin_bp.route('/gallery/<int:img_id>/delete', methods=['POST'])
@login_required
def gallery_delete(img_id):
    img = GalleryImage.query.get_or_404(img_id)
    pid = img.cloudinary_public_id
    db.session.delete(img)
    db.session.commit()
    try:
        cloudinary.uploader.destroy(pid)
    except Exception:
        pass
    flash('Photo removed from gallery.', 'success')
    return redirect(url_for('admin.admin_gallery'))


@admin_bp.route('/orders/bulk-update', methods=['POST'])
@login_required
def bulk_update_orders():
    order_ids = request.form.getlist('order_ids')
    new_status = request.form.get('bulk_status')
    valid_statuses = [s[0] for s in STATUSES]
    if not order_ids or new_status not in valid_statuses:
        flash('Nothing to update.', 'error')
        return redirect(url_for('admin.dashboard'))
    updated = 0
    for oid in order_ids:
        order = Order.query.get(oid)
        if order:
            order.status = new_status
            updated += 1
    db.session.commit()
    flash(f'{updated} order{"s" if updated != 1 else ""} moved to "{new_status.replace("_", " ").title()}".', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/order/<order_number>/checklist', methods=['POST'])
@login_required
def update_checklist(order_number):
    import json as _json
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    checked = request.form.getlist('checklist')
    order.print_checklist = _json.dumps(checked)
    db.session.commit()
    flash('Checklist saved.', 'success')
    return redirect(url_for('admin.order_detail', order_number=order_number))


@admin_bp.route('/newsletter')
@login_required
def newsletter():
    subs = Newsletter.query.order_by(Newsletter.subscribed_at.desc()).all()
    active = sum(1 for s in subs if s.is_active)
    return render_template('admin/newsletter.html', subs=subs, active_count=active)


@admin_bp.route('/newsletter/<int:sub_id>/toggle', methods=['POST'])
@login_required
def toggle_subscriber(sub_id):
    sub = Newsletter.query.get_or_404(sub_id)
    sub.is_active = not sub.is_active
    db.session.commit()
    flash(f'{sub.email} {"re-subscribed" if sub.is_active else "unsubscribed"}.', 'success')
    return redirect(url_for('admin.newsletter'))


@admin_bp.route('/newsletter/export')
@login_required
def export_newsletter():
    subs = Newsletter.query.filter_by(is_active=True).order_by(Newsletter.subscribed_at.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Email', 'Name', 'Subscribed At', 'Source'])
    for s in subs:
        writer.writerow([s.email, s.name or '', s.subscribed_at.strftime('%Y-%m-%d %H:%M') if s.subscribed_at else '', s.source or ''])
    return Response(buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=newsletter.csv'})


@admin_bp.route('/order/<order_number>/send-reminder', methods=['POST'])
@login_required
def send_reminder(order_number):
    from utils.mail import send_abandoned_order_reminder
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    send_abandoned_order_reminder(order)
    order.reminder_sent_at = datetime.now(timezone.utc)
    db.session.commit()
    flash(f'Payment reminder sent to {order.customer_email}.', 'success')
    return redirect(url_for('admin.order_detail', order_number=order_number))


@admin_bp.route('/order/<order_number>/send-review-request', methods=['POST'])
@login_required
def send_review_request(order_number):
    from utils.mail import send_review_request_email
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    send_review_request_email(order)
    flash(f'Review request sent to {order.customer_email}.', 'success')
    return redirect(url_for('admin.order_detail', order_number=order_number))


@admin_bp.route('/popia-register')
@login_required
def popia_register():
    search = request.args.get('q', '').strip()
    query = ConsentLog.query.order_by(ConsentLog.consented_at.desc())
    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(
                ConsentLog.customer_name.ilike(like),
                ConsentLog.customer_email.ilike(like),
                ConsentLog.order_number.ilike(like),
            )
        )
    entries = query.all()
    return render_template('admin/popia_register.html', entries=entries, search=search)
