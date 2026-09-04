"""initial_schema_consolidation

Revision ID: 198e2f33cf80
Revises: 
Create Date: 2026-09-03 20:14:36.320138

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '198e2f33cf80'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: inicializa e consolida todas as tabelas fiscais."""
    from backend.database import init_db
    init_db()


def downgrade() -> None:
    """Downgrade schema."""
    pass
