"""add_audit_logs_table

Revision ID: d0218685e32e
Revises: 198e2f33cf80
Create Date: 2026-09-03 20:18:56.203464

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0218685e32e'
down_revision: Union[str, Sequence[str], None] = '198e2f33cf80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: cria a tabela audit_logs e seus índices para conformidade fiscal."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            usuario_email TEXT,
            usuario_nome TEXT,
            acao TEXT NOT NULL,
            entidade TEXT NOT NULL,
            entidade_id TEXT,
            ip TEXT,
            detalhe TEXT,
            status TEXT DEFAULT 'SUCESSO'
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_acao ON audit_logs(acao)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_usuario ON audit_logs(usuario_email)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_entidade ON audit_logs(entidade, entidade_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS audit_logs")
