import cloudinary.uploader
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
from app import db
from models import get_packages, get_addons, Order, Review, GalleryImage, Newsletter, get_setting

main_bp = Blueprint('main', __name__)


@main_bp.route('/robots.txt')
def robots():
    return send_from_directory(current_app.static_folder, 'robots.txt')


@main_bp.route('/')
def index():
    reviews = Review.query.filter_by(is_approved=True).order_by(Review.created_at.desc()).limit(6).all()
    return render_template('index.html', packages=get_packages(), reviews=reviews)


@main_bp.route('/packages')
def packages():
    return render_template('packages.html', packages=get_packages(), addons=get_addons())


@main_bp.route('/track')
def track():
    order_number = request.args.get('order', '').strip().upper()
    order = None
    error = None
    if order_number:
        order = Order.query.filter_by(order_number=order_number).first()
        if not order:
            error = f'No order found with reference "{order_number}". Please check and try again.'
    return render_template('track.html', order=order, order_number=order_number, error=error)


@main_bp.route('/privacy')
def privacy():
    return render_template('privacy.html')


@main_bp.route('/terms')
def terms():
    return render_template('terms.html')


@main_bp.route('/about')
def about():
    return render_template('about.html', about_photo_url=get_setting('about_photo_url'))


@main_bp.route('/faq')
def faq():
    return render_template('faq.html')


@main_bp.route('/gallery')
def gallery():
    images = GalleryImage.query.filter_by(is_active=True).order_by(
        GalleryImage.sort_order, GalleryImage.uploaded_at.desc()
    ).all()
    return render_template('gallery.html', images=images)


@main_bp.route('/newsletter/signup', methods=['POST'])
def newsletter_signup():
    email = request.form.get('email', '').strip().lower()
    name  = request.form.get('name', '').strip()
    if not email or '@' not in email:
        flash('Please enter a valid email address.', 'error')
        return redirect(request.referrer or url_for('main.index'))
    existing = Newsletter.query.filter_by(email=email).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.session.commit()
            flash("You're back on the list! We'll be in touch.", 'success')
        else:
            flash("You're already subscribed. Thank you!", 'success')
    else:
        db.session.add(Newsletter(email=email, name=name or None, source='footer'))
        db.session.commit()
        flash("You're subscribed! We'll keep you in the loop.", 'success')
    return redirect(request.referrer or url_for('main.index'))


@main_bp.route('/review/<order_number>', methods=['GET', 'POST'])
def review(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()

    if order.status != 'delivered':
        return render_template('review.html', order=order, blocked=True)

    if order.review:
        return render_template('review.html', order=order, already_submitted=True)

    if request.method == 'POST':
        rating = request.form.get('rating', type=int)
        text   = request.form.get('text', '').strip()

        if not rating or not (1 <= rating <= 5):
            flash('Please select a star rating.', 'error')
            return redirect(url_for('main.review', order_number=order_number))
        if not text:
            flash('Please write a few words about your experience.', 'error')
            return redirect(url_for('main.review', order_number=order_number))

        photo_url = None
        photo_public_id = None
        proof_file = request.files.get('proof_photo')
        if proof_file and proof_file.filename:
            allowed = {'jpg', 'jpeg', 'png', 'heic', 'webp'}
            ext = proof_file.filename.rsplit('.', 1)[-1].lower()
            if ext in allowed:
                result = cloudinary.uploader.upload(
                    proof_file,
                    folder='memory-lane-reviews',
                    resource_type='image',
                )
                photo_url = result['secure_url']
                photo_public_id = result['public_id']

        review = Review(
            order_id=order.id,
            rating=rating,
            text=text,
            photo_url=photo_url,
            photo_public_id=photo_public_id,
        )
        db.session.add(review)
        db.session.commit()

        return render_template('review_thanks.html', order=order)

    return render_template('review.html', order=order)
