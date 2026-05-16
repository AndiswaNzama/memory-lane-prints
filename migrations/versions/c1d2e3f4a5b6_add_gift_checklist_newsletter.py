"""add gift message, print checklist, reminder_sent_at, newsletter table

Revision ID: c1d2e3f4a5b6
Revises: b5c6d7e8f901
Create Date: 2026-05-16

"""
from alembic import op
import sqlalchemy as sa

revision = 'c1d2e3f4a5b6'
down_revision = 'b5c6d7e8f901'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # Add new columns to orders only if they don't already exist (SQLite safe)
    existing = [col['name'] for col in sa.inspect(bind).get_columns('orders')]
    if 'is_gift' not in existing:
        op.add_column('orders', sa.Column('is_gift', sa.Boolean(), nullable=True, server_default='0'))
    if 'gift_message' not in existing:
        op.add_column('orders', sa.Column('gift_message', sa.Text(), nullable=True))
    if 'print_checklist' not in existing:
        op.add_column('orders', sa.Column('print_checklist', sa.Text(), nullable=True))
    if 'reminder_sent_at' not in existing:
        op.add_column('orders', sa.Column('reminder_sent_at', sa.DateTime(), nullable=True))

    # Create newsletter table only if it doesn't already exist
    inspector = sa.inspect(bind)
    if 'newsletter' not in inspector.get_table_names():
        op.create_table(
            'newsletter',
            sa.Column('id',            sa.Integer(),     primary_key=True),
            sa.Column('email',         sa.String(120),   nullable=False, unique=True),
            sa.Column('name',          sa.String(100),   nullable=True),
            sa.Column('subscribed_at', sa.DateTime(),    nullable=True),
            sa.Column('is_active',     sa.Boolean(),     nullable=True, server_default='1'),
            sa.Column('source',        sa.String(50),    nullable=True, server_default='footer'),
        )


def downgrade():
    op.drop_table('newsletter')
    op.drop_column('orders', 'reminder_sent_at')
    op.drop_column('orders', 'print_checklist')
    op.drop_column('orders', 'gift_message')
    op.drop_column('orders', 'is_gift')
