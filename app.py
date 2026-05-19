import os
import io
import streamlit as st
from groq import Groq
from dotenv import load_dotenv
import pypdf
import docx

# Load API key
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# System prompt
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

# Legal areas with example questions
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


# Page config
st.set_page_config(
    page_title="UK Legal Assistant",
    page_icon="⚖️",
    layout="wide"
)

# Custom CSS
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
</style>
""", unsafe_allow_html=True)

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

# Initialise session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "clicked_question" not in st.session_state:
    st.session_state.clicked_question = ""
if "document_text" not in st.session_state:
    st.session_state.document_text = ""

# Two column layout
col1, col2 = st.columns([1, 2])

with col1:
    # Document upload
    st.markdown("### 📄 Upload Your Document")
    st.markdown("Upload a contract or legal document for specific advice:")

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["pdf", "docx", "txt"],
        help="Supported: PDF, Word (.docx), Text (.txt)"
    )

    if uploaded_file is not None:
        with st.spinner("Reading your document..."):
            document_text = extract_text_from_file(uploaded_file)
        if document_text:
            st.session_state.document_text = document_text
            st.success(f"✅ Document loaded — {len(document_text.split())} words")
            with st.expander("Preview"):
                st.text(document_text[:500] + "..." if len(document_text) > 500 else document_text)
        else:
            st.error("Could not read this file. Please try another.")

    if st.session_state.document_text:
        if st.button("🗑️ Remove document", use_container_width=True):
            st.session_state.document_text = ""
            st.rerun()

    st.markdown("---")

    # Legal areas
    st.markdown("### 📚 Legal Areas")
    st.markdown("Click any question to ask it instantly:")

    for area, questions in LEGAL_AREAS.items():
        with st.expander(area):
            for question in questions:
                if st.button(question, key=question, use_container_width=True):
                    st.session_state.clicked_question = question

    st.markdown("---")

    # Clear chat
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.clicked_question = ""
        st.rerun()

    st.markdown("---")
    st.markdown("### 🇬🇧 Covers")
    st.markdown("""
    - England & Wales law
    - Housing & tenancy
    - Employment rights
    - Consumer rights
    - Family law
    - Criminal law
    - Immigration
    """)

with col2:
    st.markdown("### 💬 Ask your legal question")

    # Show document status
    if st.session_state.document_text:
        st.info("📄 Document loaded — answers will be based on your document")

    # Show conversation history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle clicked example question
    if st.session_state.clicked_question:
        prompt = st.session_state.clicked_question
        st.session_state.clicked_question = ""

        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Finding relevant UK law..."):
                answer = get_ai_response(
                    st.session_state.messages,
                    st.session_state.document_text
                )
                st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()

    # Manual text input
    if prompt := st.chat_input("Type your legal question here..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Finding relevant UK law..."):
                answer = get_ai_response(
                    st.session_state.messages,
                    st.session_state.document_text
                )
                st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})