"""Standardize embeddings at 1024 dimensions and add safe index state."""
from alembic import op
import sqlalchemy as sa

revision = "0002_embedding_compatibility"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("embedding_provider", sa.String(32), nullable=True))
    op.add_column("documents", sa.Column("embedding_model", sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("embedding_dimensions", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("indexing_status", sa.String(32), nullable=True))
    op.add_column("documents", sa.Column("indexing_error", sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("indexing_error_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE documents SET embedding_provider='legacy', embedding_model='unknown', embedding_dimensions=1536, indexing_status='requires_reindex'")
    for name in ("embedding_provider", "embedding_model", "embedding_dimensions", "indexing_status"):
        op.alter_column("documents", name, nullable=False)
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.alter_column("document_chunks", "embedding", nullable=True)
    op.execute("UPDATE document_chunks SET embedding=NULL")
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1024) USING NULL::vector(1024)")
    op.execute("CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops)")
    op.create_index("ix_documents_embedding_identity", "documents", ["embedding_provider", "embedding_model", "embedding_dimensions", "indexing_status"])


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536) USING NULL::vector(1536)")
    op.execute("UPDATE document_chunks SET embedding=array_fill(0::real, ARRAY[1536])::vector")
    op.alter_column("document_chunks", "embedding", nullable=False)
    op.execute("CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops)")
    op.drop_index("ix_documents_embedding_identity", table_name="documents")
    for name in ("indexing_error_at", "indexing_error", "indexing_status", "embedding_dimensions", "embedding_model", "embedding_provider"):
        op.drop_column("documents", name)
