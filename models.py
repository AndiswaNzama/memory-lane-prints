from datetime import datetime, timezone

def _now():
    return datetime.now(timezone.utc)
import uuid
from app import db


_SEED_PACKAGES = {
    'mini': {
        'name': 'Mini Memories',
        'description': 'Softcover, 24 pages, simple layout',
        'price': 750,
        'color': '#D4B882',
        'sort_order': 0,
    },
    'signature': {
        'name': 'Signature Storybook',
        'description': 'Hardcover, 32 to 40 pages, custom layout',
        'price': 1100,
        'color': '#BF9C58',
        'sort_order': 1,
    },
    'luxury': {
        'name': 'Luxury Keepsake',
        'description': 'Premium layflat book, 50+ pages, comes in a gift box',
        'price': 1800,
        'color': '#A07D3A',
        'sort_order': 2,
    },
}

_SEED_ADDONS = {
    'custom_cover': {'name': 'Custom Cover Design', 'price': 150},
    'gift_wrap':    {'name': 'Gift Wrapping',        'price': 80},
    'extra_pages':  {'name': 'Extra 8 Pages',        'price': 100},
    'memory_box':   {'name': 'Memory Box Packaging', 'price': 200},
}


class Package(db.Model):
    __tablename__ = 'packages'

    id         = db.Column(db.Integer, primary_key=True)
    key        = db.Column(db.String(30), unique=True, nullable=False)
    name       = db.Column(db.String(100), nullable=False)
    description= db.Column(db.Text)
    price      = db.Column(db.Float, nullable=False)
    color      = db.Column(db.String(20))
    is_active  = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)


class Addon(db.Model):
    __tablename__ = 'addons'

    id        = db.Column(db.Integer, primary_key=True)
    key       = db.Column(db.String(30), unique=True, nullable=False)
    name      = db.Column(db.String(100), nullable=False)
    price     = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


def get_packages():
    rows = Package.query.filter_by(is_active=True).order_by(Package.sort_order).all()
    return {p.key: {'name': p.name, 'description': p.description,
                    'price': p.price, 'color': p.color} for p in rows}


def get_addons():
    rows = Addon.query.filter_by(is_active=True).all()
    return {a.key: {'name': a.name, 'price': a.price} for a in rows}


def seed_catalog():
    if Package.query.count() == 0:
        for key, data in _SEED_PACKAGES.items():
            db.session.add(Package(key=key, **data))
    if Addon.query.count() == 0:
        for key, data in _SEED_ADDONS.items():
            db.session.add(Addon(key=key, **data))
    db.session.commit()


class Setting(db.Model):
    __tablename__ = 'settings'

    key   = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, default='')


def get_setting(key: str, default: str = '') -> str:
    row = Setting.query.get(key)
    return row.value if row else default


def set_setting(key: str, value: str):
    row = Setting.query.get(key)
    if row:
        row.value = value
    else:
        db.session.add(Setting(key=key, value=value))


def seed_settings(app_config):
    """Populate settings from env/config on first run; never overwrite existing values."""
    defaults = {
        'payfast_merchant_id':  app_config.get('PAYFAST_MERCHANT_ID', ''),
        'payfast_merchant_key': app_config.get('PAYFAST_MERCHANT_KEY', ''),
        'payfast_passphrase':   app_config.get('PAYFAST_PASSPHRASE', ''),
        'payfast_sandbox':      'true' if app_config.get('PAYFAST_SANDBOX', True) else 'false',
        'app_url':              app_config.get('APP_URL', 'http://localhost:5000'),
        'whatsapp_number':      app_config.get('WHATSAPP_NUMBER', ''),
        'instagram_handle':     app_config.get('INSTAGRAM_HANDLE', ''),
        'admin_email':          app_config.get('ADMIN_EMAIL', ''),
    }
    for key, value in defaults.items():
        if not Setting.query.get(key):
            db.session.add(Setting(key=key, value=value))
    db.session.commit()


def generate_order_number():
    return 'MLP-' + uuid.uuid4().hex[:8].upper()


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False,
                             default=generate_order_number)

    customer_name    = db.Column(db.String(100), nullable=False)
    customer_email   = db.Column(db.String(120), nullable=False)
    customer_phone   = db.Column(db.String(20), nullable=False)
    delivery_address = db.Column(db.Text, nullable=False)

    package       = db.Column(db.String(20), nullable=False)
    addons        = db.Column(db.JSON, default=list)
    special_notes = db.Column(db.Text)

    cover_title      = db.Column(db.String(100))
    cover_subtitle   = db.Column(db.String(100))
    preface_message  = db.Column(db.Text)
    closing_message  = db.Column(db.Text)

    coupon_code      = db.Column(db.String(50))
    discount_amount  = db.Column(db.Float, default=0)

    is_gift      = db.Column(db.Boolean, default=False)
    gift_message = db.Column(db.Text)

    subtotal = db.Column(db.Float, nullable=False)
    total    = db.Column(db.Float, nullable=False)

    # pending → awaiting_payment → paid → processing → shipped → delivered
    status             = db.Column(db.String(30), default='pending')
    payfast_payment_id = db.Column(db.String(100))
    courier            = db.Column(db.String(20))
    tracking_number    = db.Column(db.String(100))
    admin_notes        = db.Column(db.Text)
    print_checklist    = db.Column(db.Text)
    page_layout        = db.Column(db.Text)
    reminder_sent_at   = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    images = db.relationship('OrderImage', backref='order', lazy=True,
                             cascade='all, delete-orphan')

    def get_package_info(self):
        pkg = Package.query.filter_by(key=self.package).first()
        if pkg:
            return {'name': pkg.name, 'description': pkg.description,
                    'price': pkg.price, 'color': pkg.color}
        return {}

    def get_addon_names(self):
        keys = self.addons or []
        rows = Addon.query.filter(Addon.key.in_(keys)).all()
        name_map = {a.key: a.name for a in rows}
        return [name_map[k] for k in keys if k in name_map]

    def calculate_total(self):
        pkg = Package.query.filter_by(key=self.package).first()
        base = pkg.price if pkg else 0
        keys = self.addons or []
        rows = Addon.query.filter(Addon.key.in_(keys)).all()
        addon_total = sum(a.price for a in rows)
        return base, base + addon_total


class Review(db.Model):
    __tablename__ = 'reviews'

    id              = db.Column(db.Integer, primary_key=True)
    order_id        = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, unique=True)
    rating          = db.Column(db.Integer, nullable=False)
    text            = db.Column(db.Text, nullable=False)
    photo_url       = db.Column(db.String(500))
    photo_public_id = db.Column(db.String(200))
    is_approved     = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=_now)

    order = db.relationship('Order', backref=db.backref('review', uselist=False))


class OrderImage(db.Model):
    __tablename__ = 'order_images'

    id                  = db.Column(db.Integer, primary_key=True)
    order_id            = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    cloudinary_url      = db.Column(db.String(500), nullable=False)
    cloudinary_public_id= db.Column(db.String(200), nullable=False)
    original_filename   = db.Column(db.String(200))
    caption             = db.Column(db.String(200))
    uploaded_at         = db.Column(db.DateTime, default=_now)


class ConsentLog(db.Model):
    """POPIA consent record — one entry per order submission."""
    __tablename__ = 'consent_logs'

    id               = db.Column(db.Integer, primary_key=True)
    order_id         = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    order_number     = db.Column(db.String(20), nullable=False, index=True)
    customer_name    = db.Column(db.String(100), nullable=False)
    customer_email   = db.Column(db.String(120), nullable=False)
    ip_address       = db.Column(db.String(45))
    user_agent       = db.Column(db.String(500))
    consent_version  = db.Column(db.String(10), default='1.0', nullable=False)
    consented_at     = db.Column(db.DateTime, default=_now, nullable=False)

    order = db.relationship('Order', backref=db.backref('consent_log', uselist=False, cascade='all, delete-orphan', single_parent=True))


class Coupon(db.Model):
    __tablename__ = 'coupons'

    id             = db.Column(db.Integer, primary_key=True)
    code           = db.Column(db.String(50), unique=True, nullable=False)
    discount_type  = db.Column(db.String(10), nullable=False)  # 'percent' or 'fixed'
    discount_value = db.Column(db.Float, nullable=False)
    min_order      = db.Column(db.Float, default=0)
    uses_left      = db.Column(db.Integer)
    expires_at     = db.Column(db.DateTime)
    is_active      = db.Column(db.Boolean, default=True)
    created_at     = db.Column(db.DateTime, default=_now)


class GalleryImage(db.Model):
    __tablename__ = 'gallery_images'

    id                   = db.Column(db.Integer, primary_key=True)
    cloudinary_url       = db.Column(db.String(500), nullable=False)
    cloudinary_public_id = db.Column(db.String(200), nullable=False)
    caption              = db.Column(db.String(200))
    sort_order           = db.Column(db.Integer, default=0)
    is_active            = db.Column(db.Boolean, default=True)
    uploaded_at          = db.Column(db.DateTime, default=_now)


class Newsletter(db.Model):
    __tablename__ = 'newsletter'

    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    name          = db.Column(db.String(100))
    subscribed_at = db.Column(db.DateTime, default=_now)
    is_active     = db.Column(db.Boolean, default=True)
    source        = db.Column(db.String(50), default='footer')

vc