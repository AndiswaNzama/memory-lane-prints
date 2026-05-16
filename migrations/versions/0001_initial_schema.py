"""initial schema with consent_logs

Revision ID: 0001_initial_schema
Revises:
Create Date: 2025-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'packages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_table(
        'addons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_table(
        'settings',
        sa.Column('key', sa.String(length=80), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('key'),
    )
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_number', sa.String(length=20), nullable=False),
        sa.Column('customer_name', sa.String(length=100), nullable=False),
        sa.Column('customer_email', sa.String(length=120), nullable=False),
        sa.Column('customer_phone', sa.String(length=20), nullable=False),
        sa.Column('delivery_address', sa.Text(), nullable=False),
        sa.Column('package', sa.String(length=20), nullable=False),
        sa.Column('addons', sa.JSON(), nullable=True),
        sa.Column('special_notes', sa.Text(), nullable=True),
        sa.Column('subtotal', sa.Float(), nullable=False),
        sa.Column('total', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=True),
        sa.Column('payfast_payment_id', sa.String(length=100), nullable=True),
        sa.Column('courier', sa.String(length=20), nullable=True),
        sa.Column('tracking_number', sa.String(length=100), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_number'),
    )
    op.create_table(
        'order_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('cloudinary_url', sa.String(length=500), nullable=False),
        sa.Column('cloudinary_public_id', sa.String(length=200), nullable=False),
        sa.Column('original_filename', sa.String(length=200), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('photo_url', sa.String(length=500), nullable=True),
        sa.Column('photo_public_id', sa.String(length=200), nullable=True),
        sa.Column('is_approved', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id'),
    )
    op.create_table(
        'consent_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('order_number', sa.String(length=20), nullable=False),
        sa.Column('customer_name', sa.String(length=100), nullable=False),
        sa.Column('customer_email', sa.String(length=120), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('consent_version', sa.String(length=10), nullable=False),
        sa.Column('consented_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_consent_logs_order_number', 'consent_logs', ['order_number'])


def downgrade():
    op.drop_index('ix_consent_logs_order_number', table_name='consent_logs')
    op.drop_table('consent_logs')
    op.drop_table('reviews')
    op.drop_table('order_images')
    op.drop_table('orders')
    op.drop_table('settings')
    op.drop_table('addons')
    op.drop_table('packages')
