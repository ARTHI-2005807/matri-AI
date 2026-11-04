"""Gradio front end. It is a pure API client: everything goes through the FastAPI service (no agent code here)."""
import os
import uuid

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")  # no usage pings to Hugging Face from the students' UI

import gradio as gr
import httpx

API = os.getenv("API_URL", "http://localhost:8000")                # server-side calls
PUBLIC_API = os.getenv("PUBLIC_API_URL", "http://localhost:8000")   # URLs the browser opens (chart iframes)
http = httpx.Client(base_url=API, timeout=300)  # ingestion = OCR + several Groq calls


def detail(r: httpx.Response) -> str:
    """Readable error text from any failed API response (JSON detail, validation list, or a plain-text body)."""
    try:
        d = r.json().get("detail", r.text)
    except ValueError:
        d = r.text
    if isinstance(d, list):  # FastAPI validation errors
        d = "; ".join(str(e.get("msg", e)) for e in d)
    return str(d)[:300] or f"HTTP {r.status_code}"


def new_sid() -> str:
    return uuid.uuid4().hex[:12]


def kb_markdown(sid: str) -> str:
    kb = http.get(f"/kb/{sid}").json()
    if not kb["documents"]:
        return "_Empty. Upload a PDF, DOCX, TXT or image on the left._"
    lines = [f"**Overview:** {kb['overview']}", f"**Keywords:** {', '.join(kb['keywords'])}", ""]
    for d in kb["documents"]:
        ocr = f", {d['ocr_pages']} OCR pages" if d["ocr_pages"] else ""
        lines.append(f"- **{d['filename']}** ({d['doc_type']}; {d['n_sections']} sections, {d['n_chunks']} chunks{ocr})  \n  {d['summary']}")
    return "\n".join(lines)


def chart_html(urls: list[str]) -> str:
    if not urls:
        return "<i>No chart yet. Ask for one, e.g. top 5 artists in Chinook as a bar chart.</i>"
    return f'<iframe src="{PUBLIC_API}{urls[-1]}" style="width:100%;height:480px;border:0"></iframe>'


def ask(message: str, sid: str) -> dict:
    try:
        r = http.post("/agent", json={"message": message, "thread_id": sid})
    except httpx.HTTPError:
        return {"answer": "Error: the API is not reachable. Please try again in a moment.", "steps": [], "charts": []}
    if r.status_code != 200:
        return {"answer": f"Error {r.status_code}: {detail(r)}", "steps": [], "charts": []}
    return r.json()


def turn(message, history, sid):
    """One chat turn: show the user message at once, then the answer, steps, chart and knowledge base."""
    history = [*history, {"role": "user", "content": message}, {"role": "assistant", "content": "Working..."}]
    yield history, gr.update(), gr.update(), gr.update(), ""
    res = ask(message, sid)
    history[-1] = {"role": "assistant", "content": res["answer"]}
    yield history, res["steps"], chart_html(res["charts"]), kb_markdown(sid), ""


def upload(paths, history, sid):
    """Upload each file to the API, then tell the agent about it. The agent decides to call ingest_document."""
    final = (history, gr.update(), gr.update(), gr.update(), None)
    for path in paths or []:
        try:
            with open(path, "rb") as f:
                r = http.post("/upload", data={"session_id": sid}, files={"file": (os.path.basename(path), f)})
        except httpx.HTTPError:
            history = [*history, {"role": "assistant", "content": "Upload failed: the API is not reachable."}]
            final = (history, *final[1:])
            continue
        if r.status_code != 200:
            history = [*history, {"role": "assistant", "content": f"Upload failed: {detail(r)}"}]
            final = (history, *final[1:])
            continue
        up = r.json()
        msg = f"I uploaded '{up['filename']}' (file_id={up['file_id']}). Please add it to the knowledge base."
        for out in turn(msg, history, sid):
            history = out[0]
            final = (*out[:4], None)  # 5th output here is the File component (turn's 5th is the textbox: "" would resolve to a path)
            yield final
    yield final  # always end with a state, so failures (and empty uploads) show up


def reset_session():
    sid = new_sid()
    return sid, [], [], chart_html([]), kb_markdown(sid)


def clear_kb(sid):
    http.delete(f"/kb/{sid}")
    return kb_markdown(sid)


with gr.Blocks(title="Document Agent") as demo:
    sid = gr.State(new_sid)  # a CALLABLE: runs per browser session (a value would be created once and shared by everyone)
    gr.Markdown("## Document Agent\nSession 1 tools (SQL, charts, OpenML, web) + your documents. Upload a file, then ask about it.")
    with gr.Row():
        with gr.Column(scale=3):
            chat = gr.Chatbot(height=480, label="Chat")
            box = gr.Textbox(placeholder="Ask anything, e.g. 'What does the contract say about termination?'", show_label=False)
            files = gr.File(label="Upload documents (PDF, DOCX, TXT, MD, images)", file_count="multiple", type="filepath")
        with gr.Column(scale=2):
            with gr.Tab("Knowledge base"):
                kb = gr.Markdown("_Empty. Upload a PDF, DOCX, TXT or image on the left._")
                with gr.Row():
                    new = gr.Button("New session")
                    clear = gr.Button("Clear knowledge base")
            with gr.Tab("Steps"):
                steps = gr.JSON(label="Tool calls this turn")
            with gr.Tab("Chart"):
                chart = gr.HTML(chart_html([]))

    outputs = [chat, steps, chart, kb, box]
    demo.load(kb_markdown, sid, kb)  # fresh browser session -> its (empty) knowledge base
    box.submit(turn, [box, chat, sid], outputs)
    files.upload(upload, [files, chat, sid], [chat, steps, chart, kb, files])
    new.click(reset_session, None, [sid, chat, steps, chart, kb])
    clear.click(clear_kb, sid, kb)

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")))
