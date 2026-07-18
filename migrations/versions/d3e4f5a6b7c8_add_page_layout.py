"""add page_layout to orders

Revision ID: d3e4f5a6b7c8
Revises: c1d2e3f4a5b6
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa

revision = 'd3e4f5a6b7c8'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = [col['name'] for col in sa.inspect(bind).get_columns('orders')]
    if 'page_layout' not in existing:
        op.add_column('orders', sa.Column('page_layout', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('orders', 'page_layout')