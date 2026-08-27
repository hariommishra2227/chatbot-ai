"""Initial schema with pgvector."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision="0001_initial"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table("documents",sa.Column("id",sa.UUID(),primary_key=True),sa.Column("filename",sa.String(255),nullable=False),sa.Column("content_type",sa.String(100),nullable=False),sa.Column("sha256",sa.String(64),nullable=False,unique=True),sa.Column("size_bytes",sa.BigInteger(),nullable=False),sa.Column("content",sa.LargeBinary(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("conversations",sa.Column("id",sa.UUID(),primary_key=True),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("usage_records",sa.Column("id",sa.BigInteger(),primary_key=True,autoincrement=True),sa.Column("input_tokens",sa.Integer(),nullable=False),sa.Column("output_tokens",sa.Integer(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_usage_records_created_at","usage_records",["created_at"])
    op.create_table("document_chunks",sa.Column("id",sa.BigInteger(),primary_key=True,autoincrement=True),sa.Column("document_id",sa.UUID(),sa.ForeignKey("documents.id",ondelete="CASCADE"),nullable=False),sa.Column("chunk_index",sa.Integer(),nullable=False),sa.Column("content",sa.Text(),nullable=False),sa.Column("embedding",Vector(1536),nullable=False),sa.UniqueConstraint("document_id","chunk_index",name="uq_document_chunk_index"))
    op.create_index("ix_document_chunks_document_id","document_chunks",["document_id"])
    op.execute("CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops)")
    op.create_table("messages",sa.Column("id",sa.BigInteger(),primary_key=True,autoincrement=True),sa.Column("conversation_id",sa.UUID(),sa.ForeignKey("conversations.id",ondelete="CASCADE"),nullable=False),sa.Column("role",sa.String(20),nullable=False),sa.Column("content",sa.Text(),nullable=False),sa.Column("sources",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_messages_conversation_created","messages",["conversation_id","created_at"])
    op.create_table("leads",sa.Column("id",sa.UUID(),primary_key=True),sa.Column("conversation_id",sa.UUID(),sa.ForeignKey("conversations.id",ondelete="SET NULL")),sa.Column("name",sa.String(120),nullable=False),sa.Column("company",sa.String(160),nullable=False),sa.Column("email",sa.String(320),nullable=False),sa.Column("phone",sa.String(32),nullable=False),sa.Column("requirement",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_leads_email","leads",["email"]);op.create_index("ix_leads_created_at","leads",["created_at"])

def downgrade():
    op.drop_table("leads");op.drop_table("messages");op.drop_table("document_chunks");op.drop_table("usage_records");op.drop_table("conversations");op.drop_table("documents")
