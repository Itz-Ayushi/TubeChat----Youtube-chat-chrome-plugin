import re
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

app = FastAPI(title="YouTube Chat")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^chrome-extension://.*$",
    allow_methods=["*"],
    allow_headers=["*"],
)

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
FULL_CONTEXT_LIMIT = 300_000  # characters (~75k tokens); longer videos fall back to RAG

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

_embeddings = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return _embeddings


# video_id -> {"transcript": str, "store": FAISS | None}
videos = {}


def fetch_transcript(video_id: str) -> str:
    fetched = YouTubeTranscriptApi().fetch(video_id, languages=["en"])
    return " ".join(s.text for s in fetched)


def get_video(video_id: str) -> dict:
    if not VIDEO_ID_RE.match(video_id):
        raise HTTPException(400, "Invalid video id.")
    if video_id not in videos:
        try:
            transcript = fetch_transcript(video_id)
        except TranscriptsDisabled:
            raise HTTPException(404, "Captions are disabled for this video.")
        except NoTranscriptFound:
            raise HTTPException(404, "No English transcript found for this video.")
        except VideoUnavailable:
            raise HTTPException(404, "This video is unavailable.")
        except Exception as e:
            raise HTTPException(502, f"Could not fetch the transcript: {e}")
        videos[video_id] = {"transcript": transcript, "store": None}
    return videos[video_id]


def get_context(video: dict, question: str) -> tuple[str, str]:
    """Whole transcript for normal videos; top-matching chunks for very long ones."""
    transcript = video["transcript"]
    if len(transcript) <= FULL_CONTEXT_LIMIT:
        return transcript, ""
    if video["store"] is None:
        chunks = splitter.create_documents([transcript])
        video["store"] = FAISS.from_documents(chunks, get_embeddings())
    docs = video["store"].similarity_search(question, k=10)
    return (
        "\n\n".join(d.page_content for d in docs),
        " (excerpts from a very long video, not the full text)",
    )


def system_prompt(context: str, note: str) -> str:
    return f"""You are an assistant that answers questions about a YouTube video using its transcript.

- Answer whatever the user asks about the video: summaries, explanations, key points, quotes, quizzes, study notes, simplifications, and so on.
- Base your answers on the transcript. If the video doesn't cover something, say so briefly. You may then add helpful general knowledge, clearly marked as not coming from the video.
- The transcript has no speaker labels or timestamps and may contain auto-caption mistakes, so use judgment.
- Keep answers clear and reasonably concise.

Transcript{note}:
{context}"""


class HistoryItem(BaseModel):
    role: str  # "user" or "assistant"
    text: str


class IndexReq(BaseModel):
    video_id: str


class AskReq(BaseModel):
    video_id: str
    question: str
    history: list[HistoryItem] = []


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/index")
def index(req: IndexReq):
    get_video(req.video_id)
    return {"status": "ready", "video_id": req.video_id}


@app.post("/ask")
def ask(req: AskReq):
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "Empty question.")
    video = get_video(req.video_id)
    context, note = get_context(video, question)

    messages = [SystemMessage(content=system_prompt(context, note))]
    for h in req.history[-8:]:
        cls = HumanMessage if h.role == "user" else AIMessage
        messages.append(cls(content=h.text))
    messages.append(HumanMessage(content=question))

    try:
        return {"answer": llm.invoke(messages).content}
    except Exception as e:
        raise HTTPException(502, f"Answer generation failed: {e}")