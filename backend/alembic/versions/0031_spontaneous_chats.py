"""Independent brief chats with authenticated attachments, without patient assignments."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0031_spontaneous_chats'
down_revision = '0030_channel_working_hours'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('spontaneous_chats',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('professional_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(10), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('open','closed')", name='valid_spontaneous_chat_status'))
    op.create_index('ix_spontaneous_chats_patient_id', 'spontaneous_chats', ['patient_id'])
    op.create_index('ix_spontaneous_chats_professional_id', 'spontaneous_chats', ['professional_id'])
    op.create_index('uq_open_spontaneous_chat_pair', 'spontaneous_chats', ['patient_id', 'professional_id'], unique=True, postgresql_where=sa.text("status='open'"))
    op.create_table('spontaneous_chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('chat_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('spontaneous_chats.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('file_key', sa.String(255)), sa.Column('file_name', sa.String(150)),
        sa.Column('content_type', sa.String(50)), sa.Column('file_size', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('chat_id', 'sender_id', 'client_id', name='uq_spontaneous_message_request'))
    op.create_index('ix_spontaneous_message_history', 'spontaneous_chat_messages', ['chat_id', 'created_at', 'id'])


def downgrade():
    op.drop_table('spontaneous_chat_messages')
    op.drop_table('spontaneous_chats')
