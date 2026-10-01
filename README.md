# VIDYORA AI

> An AI-powered adaptive learning platform that transforms educational videos into structured learning materials, source-grounded explanations, quizzes, personalized revision paths, and measurable learning progress.

---

## 📖 Overview

**VIDYORA AI** bridges video lectures and deep, verifiable retention. By transforming educational video content into indexed, grounded knowledge units, VIDYORA AI enables learners to study actively rather than passively watch.

### Key Capabilities
- **Video Knowledge Extraction**: Extracts transcripts and segments lectures into conceptual topics.
- **Source-Grounded Explanations**: Answers questions with exact timestamp references and citations back to original video content using RAG (Retrieval-Augmented Generation).
- **Interactive Quizzes**: Generates formative assessments linked to specific lecture segments.
- **Personalized Revision Paths**: Identifies weak areas and builds adaptive review schedules.
- **Measurable Progress**: Tracks mastery over time with visual analytics.

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend** | React, TypeScript, Vite | Fast, typed, component-driven client interface |
| **Styling** | Tailwind CSS | Modern, utility-first responsive styling |
| **Backend** | Python, FastAPI | High-performance, asynchronous REST API |
| **Database** | PostgreSQL + pgvector | Relational metadata store + vector embeddings for semantic search |
| **AI / LLM** | Gemini API | Transcript processing, content generation, and Q&A |
| **AI Architecture**| RAG (Retrieval-Augmented Generation) | Grounded context retrieval with source attribution |
| **Deployment** | Docker, Vercel, Render | Containerization and cloud hosting |
| **Version Control**| Git & GitHub | Source control and collaboration |

---

## 📁 Repository Structure

```text
VIDYORA AI/
├── backend/            # FastAPI backend services, database models, and RAG pipelines
├── frontend/           # React + TypeScript + Vite web application
├── .gitignore          # Git exclusion rules for secrets, dependencies, and build artifacts
└── README.md           # Project documentation and architectural overview
```

---

## 🚀 Getting Started

*Project is currently in the initial setup phase.* Setup instructions for local development will be documented here as each module is built.
