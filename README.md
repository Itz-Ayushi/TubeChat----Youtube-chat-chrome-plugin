# YouTube Chat

> A Chrome extension that lets you chat with any YouTube video. Open a video, click the icon, and ask questions about it: summaries, key takeaways, explanations, quizzes, and more, all answered from the video's transcript.

![Chrome](https://img.shields.io/badge/Chrome-Manifest%20V3-4285F4?logo=googlechrome&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-RAG-1C3C3C)

<!-- Add a screenshot or GIF here:  ![Demo](docs/demo.gif) -->

## Features

- **Side-panel chat** that stays open while you watch, and switches automatically when you open another video (it follows YouTube's single-page navigation and tab changes).
- **Ask anything** about the video: summaries, key points, explanations, study notes, "what did they say about X?"
- **Conversation memory**, so follow-ups like "explain that more simply" work.
- **Grounded answers.** The assistant is instructed to rely on the transcript and to flag anything that comes from outside the video.
- **Hybrid long-context + RAG design.** Normal videos are sent to the LLM in full. Very long videos fall back to chunked retrieval with a FAISS vector store.
- **Quick-action buttons** for *Summarize* and *Key takeaways*, plus light and dark themes.
- **Clear error messages** for videos without captions, an unreachable backend, or API failures.

## How it works

```
┌──────────────────────┐   video id + question   ┌────────────────────────────┐
│  Chrome extension    │ ──────────────────────▶ │  FastAPI backend           │
│  (Manifest V3,       │                         │                            │
│   side panel UI)     │ ◀────────────────────── │  1. fetch transcript       │
└──────────────────────┘         answer          │  2. build context          │
                                                 │     • short video: full    │
                                                 │       transcript           │
                                                 │     • long video: FAISS    │
                                                 │       top-k chunks (RAG)   │
                                                 │  3. LLM answers            │
                                                 └────────────────────────────┘
```

1. The extension reads the video ID from the active tab and asks the backend to prepare it.
2. The backend fetches the English transcript with `youtube-transcript-api` and caches it in memory.
3. For each question it builds the context, adds the recent chat history, and calls the LLM.
4. For transcripts above a size threshold, it splits the text (`RecursiveCharacterTextSplitter`, 1000 chars, 200 overlap), embeds the chunks, stores them in FAISS, and retrieves the top matches for the question.

This project started as a LangChain RAG notebook (`rag_using_langchain.ipynb`): load transcript → split → embed → retrieve → augment → generate.

## Tech stack

| Layer | Tools |
| --- | --- |
| Extension | JavaScript, Chrome Manifest V3, Side Panel API |
| Backend | Python, FastAPI, Uvicorn |
| Orchestration | LangChain |
| Vector store | FAISS |
| Embeddings | Hugging Face `sentence-transformers/all-MiniLM-L6-v2` (local, free) |
| LLM | Google Gemini (`gemini-2.5-flash`) |
| Transcripts | `youtube-transcript-api` |

The LLM and embedding providers are easy to swap, since both are single lines near the top of `backend/main.py`.

## Project structure

```
yt-chat/
├── backend/
│   ├── main.py             # FastAPI app: transcript, context building, LLM call
│   ├── requirements.txt
│   └── .env.example        # copy to .env and add your key
├── extension/
│   ├── manifest.json       # Manifest V3 config
│   ├── background.js       # opens the side panel on icon click
│   ├── sidepanel.html      # chat UI
│   ├── sidepanel.css
│   ├── sidepanel.js        # chat logic, video detection, API calls
│   └── icons/
└── README.md
```

## Getting started

### Prerequisites

- Python 3.10 or newer
- Google Chrome 114 or newer (needed for the Side Panel API)
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com/)

### 1. Backend

```bash
cd backend
python -m venv .venv

# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

pip install fastapi "uvicorn[standard]" python-dotenv "youtube-transcript-api>=1.0.0" \
            langchain-core langchain-community langchain-text-splitters \
            langchain-google-genai langchain-huggingface sentence-transformers faiss-cpu
```

Create `backend/.env`:

```
GOOGLE_API_KEY=your-key-here
```

Start the server:

```bash
uvicorn main:app --port 8000
```

Check that it's up by opening <http://localhost:8000/health>. You should see `{"ok":true}`.

### 2. Extension

1. Open `chrome://extensions`.
2. Turn on **Developer mode** (top right).
3. Click **Load unpacked** and select the `extension/` folder.
4. Open any YouTube video that has English captions and click the extension icon. The side panel opens and you can start asking questions.

After editing extension files, click the reload icon on the extension's card at `chrome://extensions`.

## Usage tips

- Use **Summarize** or **Key takeaways** for a quick overview.
- Ask follow-ups naturally. The last few turns are remembered, and switching videos starts a fresh chat.
- Try prompts like *"Make a 5-question quiz from this video"*, *"Explain the main idea like I'm a beginner"*, or *"What did they say about X?"*

## Limitations

- **English captions only.** The video needs captions, either uploaded or auto-generated.
- **YouTube may block transcript requests** from some IPs, including cloud servers, VPNs, and shared or mobile networks. If you see a "Could not retrieve a transcript" error, switch networks, turn off your VPN, or wait a while. Running the backend locally helps.
- **The backend must be running** on `localhost:8000`. The extension shows a message if it can't reach it.
- **Local use only for now.** The server uses your own API key and has no authentication, so don't expose it publicly as is.
- Auto-generated captions have no speaker labels and can contain errors, which can affect answer quality.
- The in-memory cache is cleared whenever the server restarts.

## Roadmap

- [ ] Fetch transcripts inside the extension to avoid server-side IP blocks
- [ ] Settings panel so each user can enter their own API key, with no backend to host
- [ ] Timestamped answers that link to the exact moment in the video
- [ ] Support for non-English captions
- [ ] Streaming responses
- [ ] Chrome Web Store release

## Security notes

- Never commit your `.env` file or paste API keys into source code or notebooks. Add `.env` to `.gitignore`.
- If a key is ever exposed, revoke it immediately and create a new one.
- Video transcripts and your questions are sent to Google's Gemini API to generate answers.

## Acknowledgements

- [`youtube-transcript-api`](https://github.com/jdepoix/youtube-transcript-api) for transcript access
- [LangChain](https://www.langchain.com/), [FAISS](https://github.com/facebookresearch/faiss), and [Sentence Transformers](https://www.sbert.net/)

<!--## License

Add a license of your choice (for example MIT) before publishing.-->
