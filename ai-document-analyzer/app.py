"""AI Document Analyzer: Streamlit front end.

Run with:  python run.py     (or: streamlit run app.py)
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from docanalyzer import config
from docanalyzer.charts import auto_charts
from docanalyzer.extractors import ExtractedDocument, build_corpus, extract_file
from docanalyzer.history import ChatStore, relative_time
from docanalyzer.llm import Analyzer, estimate_tokens, friendly_error

load_dotenv()

st.set_page_config(page_title=config.APP_NAME, page_icon=config.APP_ICON, layout="wide")

st.markdown(
    """
    <style>
      #MainMenu, footer {visibility: hidden;}
      .block-container {padding-top: 2rem; max-width: 1100px;}
      [data-testid="stSidebar"] .stButton button {justify-content: flex-start; text-align: left;}
      [data-testid="stFileUploaderDropzone"] {padding: 0.75rem 1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

SUGGESTIONS = [
    "Summarise these documents in 5 bullet points",
    "List all key figures, dates and names",
    "What are the main risks or open issues?",
]


# ------------------------------------------------------------------------ state
def init_state() -> None:
    ss = st.session_state
    ss.setdefault("store", ChatStore(config.DATA_DIR))
    ss.setdefault("messages", [])
    ss.setdefault("chat_id", None)
    ss.setdefault("uploader_key", 0)
    ss.setdefault("pending_prompt", None)
    ss.setdefault("restored_files", [])
    ss.setdefault("current_files", [])


init_state()
ss = st.session_state
store: ChatStore = ss.store


@st.cache_data(show_spinner=False, max_entries=32)
def cached_extract(name: str, data: bytes) -> ExtractedDocument:
    """Each file is read once; later reruns hit the cache."""
    return extract_file(name, data)


@st.cache_data(show_spinner="Building charts…", max_entries=16)
def cached_charts(df):
    return auto_charts(df)


# -------------------------------------------------------------------- callbacks
def start_new_chat() -> None:
    ss.messages, ss.chat_id, ss.restored_files = [], None, []
    ss.uploader_key += 1  # clears the uploader


def open_chat(chat_id: str) -> None:
    data = store.load(chat_id)
    if data:
        ss.messages = data["messages"]
        ss.chat_id = chat_id
        ss.restored_files = data.get("file_names", [])
        ss.uploader_key += 1


def delete_chat(chat_id: str) -> None:
    store.delete(chat_id)
    if ss.chat_id == chat_id:
        start_new_chat()


def rename_chat(chat_id: str) -> None:
    store.rename(chat_id, ss.get(f"title_{chat_id}", ""))


def delete_all_chats() -> None:
    for c in store.list():
        store.delete(c["id"])
    start_new_chat()


def use_suggestion(text: str) -> None:
    ss.pending_prompt = text


# ---------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown(f"### {config.APP_ICON} {config.APP_NAME}")
    st.button("＋  New chat", on_click=start_new_chat, width="stretch", type="primary")
    chat_list_box = st.container()

    st.divider()
    with st.expander("⚙️ Settings"):
        env_key = os.getenv("ANTHROPIC_API_KEY", "")
        if env_key:
            st.success("API key loaded from environment", icon="🔑")
            api_key = env_key
        else:
            api_key = st.text_input("Anthropic API key", type="password", placeholder="sk-ant-…")
            st.caption("Tip: put it in a `.env` file as `ANTHROPIC_API_KEY=...` to skip this.")
        model_label = st.selectbox("Model", list(config.MODELS), index=list(config.MODELS).index(config.DEFAULT_MODEL))
        model = config.MODELS[model_label]
        with st.popover("Delete all chats", width="stretch"):
            st.warning("This permanently removes every saved chat.")
            st.button("Yes, delete everything", on_click=delete_all_chats)


# -------------------------------------------------------------------- documents
st.markdown("## Ask questions about your documents")
st.caption("PDF, Word, Excel and CSV. Files are read once, then you can chat freely.")

uploaded = st.file_uploader(
    "Upload documents",
    type=config.SUPPORTED_TYPES,
    accept_multiple_files=True,
    label_visibility="collapsed",
    key=f"uploader_{ss.uploader_key}",
)

docs: list[ExtractedDocument] = []
if uploaded:
    with st.spinner("Reading documents…"):
        docs = [cached_extract(f.name, f.getvalue()) for f in uploaded]
ss.current_files = [d.name for d in docs]

good = [d for d in docs if d.ok]
corpus = build_corpus(good)
tokens = estimate_tokens(corpus)

if docs:
    mode = "map-reduce (large input)" if Analyzer.needs_map_reduce(corpus) else "direct"
    st.caption(f"📄 {len(good)}/{len(docs)} readable · ≈ {tokens:,} tokens · mode: {mode}")
    for d in docs:
        if not d.ok:
            st.error(f"**{d.name}**: {d.note}", icon="⚠️")
    with st.expander("Document details"):
        st.dataframe(
            [{"File": d.name, "Type": d.kind, "Status": "OK" if d.ok else "Failed",
              "Details": d.note, "Characters": f"{d.chars:,}"} for d in docs],
            hide_index=True,
            width="stretch",
        )

tab_chat, tab_data, tab_export = st.tabs(["💬 Chat", "📊 Data & charts", "📥 Export"])

# Pinned to the bottom of the page by Streamlit.
typed = st.chat_input("Ask about your documents…")
prompt = typed or ss.pending_prompt
ss.pending_prompt = None

# ------------------------------------------------------------------------- chat
with tab_chat:
    if ss.restored_files and not docs:
        st.info(
            "This chat used: " + ", ".join(f"`{n}`" for n in ss.restored_files)
            + ". Upload the files again to ask new questions."
        )

    if not ss.messages and not prompt:
        if not docs:
            st.info("👆 Upload one or more documents to get started.")
        else:
            st.markdown("**Try one of these:**")
            for s in SUGGESTIONS:
                st.button(s, key=f"sugg_{s}", on_click=use_suggestion, args=(s,))

    for m in ss.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("time"):
                st.caption(m["time"])

    if prompt:
        if not api_key:
            st.error("Add your Anthropic API key under ⚙️ Settings in the sidebar.")
        elif not good:
            st.error("Upload at least one readable document first.")
        else:
            history = list(ss.messages)
            now = datetime.now().strftime("%H:%M")
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                bar = st.empty()

                def show_progress(fraction: float, text: str) -> None:
                    bar.progress(fraction, text=text)

                try:
                    answer = st.write_stream(
                        Analyzer(api_key, model).stream_answer(prompt, corpus, history, show_progress)
                    )
                except Exception as exc:  # noqa: BLE001 - shown to the user
                    answer = None
                    st.error(friendly_error(exc))
                    st.caption(f"Your question was: {prompt}")
                bar.empty()

            if answer:
                ss.messages += [
                    {"role": "user", "content": prompt, "time": now},
                    {"role": "assistant", "content": answer, "time": datetime.now().strftime("%H:%M")},
                ]
                ss.chat_id = store.save(ss.chat_id, ss.messages, ss.current_files)

# ------------------------------------------------------------------------- data
datasets = {f"{d.name} › {sheet}": df for d in good for sheet, df in d.dataframes.items()}

with tab_data:
    if not datasets:
        st.info("Upload an Excel or CSV file to explore it and get automatic charts.")
    else:
        choice = st.selectbox("Dataset", list(datasets))
        df = datasets[choice]
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows", f"{len(df):,}")
        c2.metric("Columns", len(df.columns))
        c3.metric("Missing cells", f"{int(df.isnull().sum().sum()):,}")

        view = st.segmented_control("View", ["Table", "Statistics", "Charts"], default="Table")
        if view == "Table":
            st.dataframe(df, width="stretch", height=420)
        elif view == "Statistics":
            st.dataframe(df.describe(include="all").T, width="stretch")
        else:
            charts = cached_charts(df)
            if not charts:
                st.info("Nothing to chart for this dataset.")
            for title, fig in charts:
                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    st.plotly_chart(fig, width="stretch")

# ----------------------------------------------------------------------- export
with tab_export:
    if not ss.messages:
        st.info("Nothing to export yet. Ask a question first.")
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        label = {"user": "You", "assistant": "Claude"}
        as_md = "# Chat export\n\n" + "\n\n".join(
            f"**{label[m['role']]}**\n\n{m['content']}\n\n---" for m in ss.messages
        )
        as_txt = "\n\n".join(f"{label[m['role']].upper()}: {m['content']}" for m in ss.messages)
        as_json = json.dumps(ss.messages, indent=2)
        c1, c2, c3 = st.columns(3)
        c1.download_button("Markdown", as_md, f"chat_{stamp}.md", "text/markdown", width="stretch")
        c2.download_button("Plain text", as_txt, f"chat_{stamp}.txt", "text/plain", width="stretch")
        c3.download_button("JSON", as_json, f"chat_{stamp}.json", "application/json", width="stretch")

    if datasets:
        st.divider()
        name = st.selectbox("Export dataset as CSV", list(datasets), key="export_ds")
        st.download_button("Download CSV", datasets[name].to_csv(index=False), "data.csv", "text/csv")

# ------------------------------------------------------------- sidebar chat list
with chat_list_box:
    query = st.text_input("Search chats", placeholder="🔍 Search chats", label_visibility="collapsed", key="chat_search")
    chats = store.search(query)
    if not chats:
        st.caption("No chats yet." if not query else "No matches.")
    for c in chats[:30]:
        row = st.columns([6, 1], vertical_alignment="center")
        row[0].button(
            c["title"],
            key=f"open_{c['id']}",
            on_click=open_chat,
            args=(c["id"],),
            width="stretch",
            type="primary" if c["id"] == ss.chat_id else "tertiary",
            help=f"{c.get('message_count', 0)} messages · {relative_time(c['updated_at'])}",
        )
        with row[1].popover("⋯"):
            st.text_input("Title", value=c["title"], key=f"title_{c['id']}")
            st.button("Rename", key=f"ren_{c['id']}", on_click=rename_chat, args=(c["id"],))
            st.button("Delete", key=f"del_{c['id']}", on_click=delete_chat, args=(c["id"],))
