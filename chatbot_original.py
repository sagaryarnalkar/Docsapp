import os
import tempfile
import streamlit as st
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.question_answering import load_qa_chain
from PyPDF2 import PdfReader

def process_pdf(pdf_file):
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def get_text_chunks(text):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=50,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    return chunks

def get_vector_store(text_chunks, openai_api_key):
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    vector_store = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
    return vector_store

def get_conversation_chain(vector_store, openai_api_key):
    llm = ChatOpenAI(
        temperature=0.7,
        model_name='gpt-3.5-turbo',
        openai_api_key=openai_api_key
    )
    chain = load_qa_chain(llm=llm, chain_type="stuff")
    return chain

with st.sidebar:
    openai_api_key = st.text_input("OpenAI API Key", key="api_key", type="password")
    "WE DO NOT STORE YOUR OPENAI KEY."
    "[Get your OpenAI API key](https://platform.openai.com/api-keys)"
    
    if openai_api_key:
        uploaded_files = st.file_uploader(
            "Upload your PDF files",
            accept_multiple_files=True,
            type="pdf"
        )

st.title("📄 Chat with your PDFs")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": """
            Hi! I'm your PDF assistant. I can help you understand your PDF documents.
            Upload your PDFs and I'll answer your questions about them!
            """,
        }
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if not openai_api_key:
    st.warning("Please enter your OpenAI API key to continue.", icon="⚠️")
    st.stop()

if "vector_store" not in st.session_state:
    st.session_state.vector_store = None

if uploaded_files:
    with st.spinner("Processing your PDFs..."):
        text = ""
        for pdf in uploaded_files:
            text += process_pdf(pdf)
        
        # Create text chunks
        text_chunks = get_text_chunks(text)
        
        # Create vector store
        st.session_state.vector_store = get_vector_store(text_chunks, openai_api_key)
        
        st.success("PDFs processed successfully!")

if prompt := st.chat_input("Ask me anything about your PDFs!"):
    if not st.session_state.vector_store:
        st.error("Please upload some PDFs first!", icon="🚫")
        st.stop()
        
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
        
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        # Search for similar content
        docs = st.session_state.vector_store.similarity_search(prompt)
        
        # Get the conversation chain
        chain = get_conversation_chain(st.session_state.vector_store, openai_api_key)
        
        # Get the response
        response = chain.run(input_documents=docs, question=prompt)
        
        message_placeholder.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response}) 