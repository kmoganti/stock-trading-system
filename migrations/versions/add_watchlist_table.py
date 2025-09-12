"""Add watchlist table

Revision ID: add_watchlist_table
Revises: 
Create Date: 2025-09-02 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_watchlist_table'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create watchlist table
    op.create_table(
        'watchlist',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, index=True),
        sa.Column('symbol', sa.String(length=50), nullable=False, index=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), onupdate=sa.text('now()')),
    )
    
    # Add initial watchlist data
    initial_symbols = [
        'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 
        'SBIN', 'ITC', 'LT', 'HINDUNILVR', 'BAJFINANCE'
    ]
    
    op.bulk_insert(
        sa.table('watchlist',
            sa.column('symbol', sa.String),
            sa.column('is_active', sa.Boolean),
            sa.column('created_at', sa.DateTime),
            sa.column('updated_at', sa.DateTime)
        ),
        [{'symbol': sym, 'is_active': True} for sym in initial_symbols]
    )

def downgrade():
    op.drop_table('watchlist')
