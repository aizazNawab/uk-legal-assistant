import os
import io
import json
import sqlite3
import datetime
import streamlit as st
from groq import Groq
from dotenv import load_dotenv
import pypdf
import docx

# ── Load API key ──────────────────────────────────────────────────────────────
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert UK legal assistant specialising in
English and Welsh law. You help members of the public understand their
legal rights in plain English.

When answering questions:
- Always base your answers on current UK law
- Cover areas including: housing, employment, consumer rights,
  family law, immigration, and criminal law
- Give clear practical steps the user can take
- Use simple plain English — avoid complex legal jargon
- Always include this disclaimer at the end:
  "⚠️ This is general legal information only. For advice specific to
  your situation, please consult a qualified solicitor."
- If asked about non-UK law, politely explain you specialise in UK law only
- Be empathetic — people asking legal questions are often stressed
- Format your response with clear headings and bullet points where helpful

You are helpful, clear, and reassuring."""

# ── Legal areas ───────────────────────────────────────────────────────────────
LEGAL_AREAS = {
    "🏠 Housing": [
        "My landlord hasn't returned my deposit after 2 months",
        "My landlord wants to evict me — what are my rights?",
        "My landlord is not fixing a broken boiler — what can I do?",
        "What notice does my landlord need to give me to leave?",
    ],
    "💼 Employment": [
        "I think I have been unfairly dismissed — what can I do?",
        "My employer hasn't paid me — what are my rights?",
        "I am being bullied at work — what can I do?",
        "Can my employer change my contract without my agreement?",
    ],
    "🛒 Consumer Rights": [
        "I bought a faulty product — can I get a refund?",
        "A company is refusing to refund me — what can I do?",
        "I was mis-sold a product — what are my rights?",
        "My online order never arrived — what can I do?",
    ],
    "👨‍👩‍👧 Family Law": [
        "How does child custody work after separation?",
        "What are my rights during a divorce?",
        "Can I stop my ex taking our child abroad?",
        "How is money divided in a divorce?",
    ],
    "🚔 Criminal Law": [
        "I have been arrested — what are my rights?",
        "What happens if I get a caution?",
        "I received a fine I think is wrong — can I appeal?",
        "What is the difference between a caution and a charge?",
    ],
    "✈️ Immigration": [
        "I want to apply for UK citizenship — how do I start?",
        "My visa is expiring soon — what should I do?",
        "What is the right to remain in the UK?",
        "Can I work in the UK on a student visa?",
    ],
}

# ── Database functions ────────────────────────────────────────────────────────

def init_db():
    """Create the database and tables if they don't exist."""
    conn = sqlite3.connect("conversations.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)
    conn.commit()
    conn.close()


def create_conversation(title):
    """Create a new conversation and return its ID."""
    conn = sqlite3.connect("conversations.db")
    c = conn.cursor()
    c.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
    conv_id = c.lastrowid
    conn.commit()
    conn.close()
    return conv_id


def get_all_conversations():
    """Get all conversations ordered by most recent first."""
    conn = sqlite3.connect("conversations.db")
    c = conn.cursor()
    c.execute("SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC")
    conversations = c.fetchall()
    conn.close()
    return conversations


def get_messages(conversation_id):
    """Get all messages for a conversation."""
    conn = sqlite3.connect("conversations.db")
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages WHERE conversation_id=? ORDER BY created_at", (conversation_id,))
    messages = c.fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in messages]


def save_message(conversation_id, role, content):
    """Save a message to the database."""
    conn = sqlite3.connect("conversations.db")
    c = conn.cursor()
    c.execute("INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
              (conversation_id, role, content))
    c.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
              (conversation_id,))
    conn.commit()
    conn.close()


def update_conversation_title(conversation_id, title):
    """Update the title of a conversation."""
    conn = sqlite3.connect("conversations.db")
    c = conn.cursor()
    c.execute("UPDATE conversations SET title=? WHERE id=?", (title, conversation_id))
    conn.commit()
    conn.close()


def delete_conversation(conversation_id):
    """Delete a conversation and all its messages."""
    conn = sqlite3.connect("conversations.db")
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
    c.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
    conn.commit()
    conn.close()


def generate_title(first_message):
    """Generate a short title from the first message."""
    words = first_message.strip().split()
    title = " ".join(words[:6])
    if len(words) > 6:
        title += "..."
    return title


# ── File reading ──────────────────────────────────────────────────────────────

def extract_text_from_file(uploaded_file):
    """Reads text from uploaded PDF, Word, or text document."""
    text = ""
    file_name = uploaded_file.name.lower()

    if file_name.endswith(".pdf"):
        pdf_reader = pypdf.PdfReader(io.BytesIO(uploaded_file.read()))
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"

    elif file_name.endswith(".docx"):
        doc = docx.Document(io.BytesIO(uploaded_file.read()))
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"

    elif file_name.endswith(".txt"):
        text = uploaded_file.read().decode("utf-8")

    return text.strip()


# ── AI response ───────────────────────────────────────────────────────────────

def get_ai_response(messages, document_text=""):
    """Sends messages to Groq AI and returns the response."""
    if document_text:
        enhanced_prompt = SYSTEM_PROMPT + f"""

IMPORTANT: The user has uploaded a document. Here is the full text:

--- DOCUMENT START ---
{document_text[:8000]}
--- DOCUMENT END ---

When answering, refer to this specific document where relevant.
Quote directly from the document to support your answers."""
    else:
        enhanced_prompt = SYSTEM_PROMPT

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": enhanced_prompt}] + messages,
        temperature=0.7,
        max_tokens=1000
    )
    return response.choices[0].message.content


# ── Initialise ────────────────────────────────────────────────────────────────
init_db()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="UK Legal Assistant",
    page_icon="⚖️",
    layout="wide"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1E2761, #4FC3F7);
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        color: white;
    }
    .disclaimer-box {
        background: #FFC107;
        border-left: 4px solid #FF8F00;
        padding: 10px 15px;
        border-radius: 5px;
        margin-bottom: 15px;
        font-size: 13px;
        color: #000000 !important;
    }
    .conv-item {
        padding: 8px 12px;
        border-radius: 8px;
        margin-bottom: 4px;
        cursor: pointer;
    }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "current_conv_id" not in st.session_state:
    st.session_state.current_conv_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "clicked_question" not in st.session_state:
    st.session_state.clicked_question = ""
if "document_text" not in st.session_state:
    st.session_state.document_text = ""

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚖️ UK Legal Assistant")
    st.markdown("---")

    # New conversation button
    if st.button("✏️ New conversation", use_container_width=True, type="primary"):
        st.session_state.current_conv_id = None
        st.session_state.messages = []
        st.session_state.document_text = ""
        st.rerun()

    st.markdown("---")
    st.markdown("### 💬 Recent conversations")

    # Show all conversations
    conversations = get_all_conversations()

    if not conversations:
        st.caption("No conversations yet. Start chatting!")
    else:
        for conv_id, title, updated_at in conversations:
            col_a, col_b = st.columns([5, 1])
            with col_a:
                # Highlight current conversation
                if conv_id == st.session_state.current_conv_id:
                    if st.button(f"💬 {title}", key=f"conv_{conv_id}",
                                use_container_width=True, type="primary"):
                        pass
                else:
                    if st.button(f"💬 {title}", key=f"conv_{conv_id}",
                                use_container_width=True):
                        st.session_state.current_conv_id = conv_id
                        st.session_state.messages = get_messages(conv_id)
                        st.rerun()
            with col_b:
                if st.button("🗑", key=f"del_{conv_id}"):
                    delete_conversation(conv_id)
                    if st.session_state.current_conv_id == conv_id:
                        st.session_state.current_conv_id = None
                        st.session_state.messages = []
                    st.rerun()

    st.markdown("---")

    # Document upload in sidebar
    st.markdown("### 📄 Upload Document")
    uploaded_file = st.file_uploader(
        "PDF, Word, or Text file",
        type=["pdf", "docx", "txt"]
    )

    if uploaded_file is not None:
        with st.spinner("Reading..."):
            doc_text = extract_text_from_file(uploaded_file)
        if doc_text:
            st.session_state.document_text = doc_text
            st.success(f"✅ {len(doc_text.split())} words loaded")
        else:
            st.error("Could not read file")

    if st.session_state.document_text:
        if st.button("Remove document", use_container_width=True):
            st.session_state.document_text = ""
            st.rerun()

    st.markdown("---")

    # Legal areas
    st.markdown("### 📚 Legal Areas")
    for area, questions in LEGAL_AREAS.items():
        with st.expander(area):
            for question in questions:
                if st.button(question, key=f"q_{question}",
                            use_container_width=True):
                    st.session_state.clicked_question = question

# ── MAIN AREA ─────────────────────────────────────────────────────────────────

# Header
st.markdown("""
<div class="main-header">
    <h1>⚖️ UK Legal Assistant</h1>
    <p>Free legal guidance based on UK law — available 24/7</p>
</div>
""", unsafe_allow_html=True)

# Disclaimer
st.markdown("""
<div class="disclaimer-box">
    ⚠️ <strong>Important:</strong> This tool provides general legal information only,
    not legal advice. Always consult a qualified solicitor for advice specific to
    your situation. In an emergency call 999. For legal aid visit
    <strong>gov.uk/legal-aid</strong>
</div>
""", unsafe_allow_html=True)

# Document status
if st.session_state.document_text:
    st.info("📄 Document loaded — answers will be based on your specific document")

# Show conversation messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle clicked example question
if st.session_state.clicked_question:
    prompt = st.session_state.clicked_question
    st.session_state.clicked_question = ""

    # Create new conversation if needed
    if st.session_state.current_conv_id is None:
        title = generate_title(prompt)
        st.session_state.current_conv_id = create_conversation(title)

    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.messages.append({"role": "user", "content": prompt})
    save_message(st.session_state.current_conv_id, "user", prompt)

    with st.chat_message("assistant"):
        with st.spinner("Finding relevant UK law..."):
            answer = get_ai_response(
                st.session_state.messages,
                st.session_state.document_text
            )
            st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    save_message(st.session_state.current_conv_id, "assistant", answer)
    st.rerun()

# Chat input
if prompt := st.chat_input("Ask your legal question here..."):

    # Create new conversation if needed
    if st.session_state.current_conv_id is None:
        title = generate_title(prompt)
        st.session_state.current_conv_id = create_conversation(title)

    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.messages.append({"role": "user", "content": prompt})
    save_message(st.session_state.current_conv_id, "user", prompt)

    with st.chat_message("assistant"):
        with st.spinner("Finding relevant UK law..."):
            answer = get_ai_response(
                st.session_state.messages,
                st.session_state.document_text
            )
            st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    save_message(st.session_state.current_conv_id, "assistant", answer)