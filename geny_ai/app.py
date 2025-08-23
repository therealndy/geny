"""Streamlit render server for Geny (unified chat UI + controls).

This does not replace FastAPI; it complements it for local/hosted rendering.
"""

import os

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Geny AI", page_icon="🧠", layout="centered")

st.title("Geny AI – Unified Chat")

# Simple, clean chat UI shared style
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.container():
    for m in st.session_state.messages:
        role = m.get("role", "user")
        if role == "user":
            st.chat_message("user").markdown(m["content"])
        else:
            st.chat_message("assistant").markdown(m["content"])

prompt = st.chat_input("Write a message to Geny…")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").markdown(prompt)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/chat", json={"message": prompt}, timeout=20
        )
        data = resp.json() if resp.ok else {"reply": f"Error: {resp.status_code}"}
        reply = data.get("reply", "(no reply)")
    except Exception as e:
        reply = f"Network error: {e}"
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.chat_message("assistant").markdown(reply)

with st.sidebar:
    st.header("Diagnostics")
    st.write("Backend:", BACKEND_URL)
    if st.button("Health check"):
        try:
            r = requests.get(f"{BACKEND_URL}/healthz", timeout=5)
            st.success(r.json())
        except Exception as e:
            st.error(str(e))
    if st.button("Run nightly now"):
        try:
            r = requests.post(
                f"{BACKEND_URL}/admin/run-nightly",
                json={"params": {"temperature": 0.7}},
                timeout=15,
            )
            st.info(r.json())
        except Exception as e:
            st.error(str(e))
    st.divider()
    st.header("MemorySphere")
    sample = st.text_area(
        "Ingest sample text", "Geny learns from everyday notes and ideas."
    )
    if st.button("Ingest"):
        try:
            r = requests.post(
                f"{BACKEND_URL}/mem/ingest",
                json={"text": sample, "meta": {"source": "streamlit"}},
                timeout=10,
            )
            st.success(r.json())
        except Exception as e:
            st.error(str(e))
    q = st.text_input("Search MemorySphere", "Geny")
    if st.button("Search"):
        try:
            r = requests.get(
                f"{BACKEND_URL}/mem/search", params={"q": q, "k": 5}, timeout=10
            )
            st.json(r.json())
        except Exception as e:
            st.error(str(e))
    st.divider()
    st.header("LifeTwin RAG")
    ltq = st.text_input("Ask with context", "What has Geny learned about memory?")
    if st.button("Ask LifeTwin"):
        try:
            r = requests.post(
                f"{BACKEND_URL}/lifetwin/reply", json={"message": ltq}, timeout=20
            )
            st.success(r.json())
        except Exception as e:
            st.error(str(e))
    st.divider()
    st.header("NeuroFeedback")
    mood = st.slider("Mood", 0.0, 1.0, 0.5, 0.05)
    sleep = st.slider("Sleep", 0.0, 1.0, 0.5, 0.05)
    stress = st.slider("Stress", 0.0, 1.0, 0.5, 0.05)
    if st.button("Update state"):
        try:
            r = requests.post(
                f"{BACKEND_URL}/neuro/state",
                json={"mood": mood, "sleep": sleep, "stress": stress},
                timeout=10,
            )
            st.info(r.json())
        except Exception as e:
            st.error(str(e))
    neuro_q = st.text_input("Neuro chat msg", "Hello!")
    if st.button("Neuro chat"):
        try:
            # Let server compute temperature from state
            r = requests.post(
                f"{BACKEND_URL}/neuro/chat", json={"message": neuro_q}, timeout=20
            )
            st.success(r.json())
        except Exception as e:
            st.error(str(e))
    if st.button("Neuro 50x stress test"):
        try:
            r = requests.get(f"{BACKEND_URL}/neuro/stress50x", timeout=10)
            st.info(r.json())
        except Exception as e:
            st.error(str(e))
    if st.button("GenAI status"):
        try:
            r = requests.get(f"{BACKEND_URL}/admin/genai-status", timeout=5)
            st.info(r.json())
        except Exception as e:
            st.error(str(e))
