"""add caption to order_images

Revision ID: a3f9b1c2d4e5
Revises: 693206dd750b
Create Date: 2026-05-14

"""
from alembic import op
import sqlalchemy as sa

revision = 'a3f9b1c2d4e5'
down_revision = '693206dd750b'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('order_images', sa.Column('caption', sa.String(200), nullable=True))


def downgrade():
    op.drop_column('order_images', 'caption')
