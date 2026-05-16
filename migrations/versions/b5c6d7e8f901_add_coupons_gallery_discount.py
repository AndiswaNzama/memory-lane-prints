"""add coupons, gallery_images, discount fields to orders

Revision ID: b5c6d7e8f901
Revises: a3f9b1c2d4e5
Create Date: 2026-05-14

"""
from alembic import op
import sqlalchemy as sa

revision = 'b5c6d7e8f901'
down_revision = 'a3f9b1c2d4e5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orders', sa.Column('coupon_code', sa.String(50), nullable=True))
    op.add_column('orders', sa.Column('discount_amount', sa.Float, nullable=True))

    op.create_table('coupons',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('discount_type', sa.String(10), nullable=False),
        sa.Column('discount_value', sa.Float, nullable=False),
        sa.Column('min_order', sa.Float, nullable=True),
        sa.Column('uses_left', sa.Integer, nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
    )

    op.create_table('gallery_images',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('cloudinary_url', sa.String(500), nullable=False),
        sa.Column('cloudinary_public_id', sa.String(200), nullable=False),
        sa.Column('caption', sa.String(200), nullable=True),
        sa.Column('sort_order', sa.Integer, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=True),
        sa.Column('uploaded_at', sa.DateTime, nullable=True),
    )


def downgrade():
    op.drop_column('orders', 'coupon_code')
    op.drop_column('orders', 'discount_amount')
    op.drop_table('coupons')
    op.drop_table('gallery_images')
