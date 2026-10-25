"""
VIDYORA AI - Tests for Step 12 Quiz and Flashcard FastAPI Endpoints
"""

import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from main import app, QUIZ_STORE
from models import (
    GeneratedQuizInternal,
    PerformanceTier,
    QuizDifficulty,
    QuizQuestionInternal,
    SourceTimestamp,
    TranscriptChunk,
)
from services.gemini_service import GeminiRateLimitError, GeminiTimeoutError

client = TestClient(app)


@pytest.fixture
def sample_chunks():
    return [
        {
            "chunk_id": "test_chunk_001",
            "chunk_index": 0,
            "video_id": "vid_123",
            "text": "Artificial neurons compute a weighted sum of inputs and apply an activation function.",
            "start_time": 0.0,
            "end_time": 45.0,
            "duration": 45.0,
            "word_count": 13,
            "segment_start_index": 0,
            "segment_end_index": 1,
        },
        {
            "chunk_id": "test_chunk_002",
            "chunk_index": 1,
            "video_id": "vid_123",
            "text": "Gradient descent minimizes the cost function by iteratively adjusting weights and biases.",
            "start_time": 45.0,
            "end_time": 90.0,
            "duration": 45.0,
            "word_count": 13,
            "segment_start_index": 2,
            "segment_end_index": 3,
        }
    ]


@pytest.fixture
def sample_internal_quiz():
    return GeneratedQuizInternal(
        quiz_id="quiz_session_abc",
        video_id="vid_123",
        title="Neural Networks Assessment",
        instructions="Choose the best answer for each question.",
        questions=[
            QuizQuestionInternal(
                id="q_1",
                question="What is an activation function?",
                options=["Non-linear mathematical transformation", "Linear slope", "File compression tool", "Display driver"],
                correct_answer="Non-linear mathematical transformation",
                explanation="Activation functions introduce non-linearity into neural networks.",
                difficulty=QuizDifficulty.EASY,
                source_timestamp=SourceTimestamp(timestamp=20.0, formatted_time="00:20", label="Activation function"),
                source_chunk_id="test_chunk_001",
            ),
            QuizQuestionInternal(
                id="q_2",
                question="What does gradient descent minimize?",
                options=["The cost/loss function", "The number of neurons", "The video resolution", "The learning rate"],
                correct_answer="The cost/loss function",
                explanation="Gradient descent finds parameters that minimize prediction error.",
                difficulty=QuizDifficulty.MEDIUM,
                source_timestamp=SourceTimestamp(timestamp=60.0, formatted_time="01:00", label="Gradient descent"),
                source_chunk_id="test_chunk_002",
            ),
            QuizQuestionInternal(
                id="q_3",
                question="Which component determines when a neuron meaningfully fires?",
                options=["Bias and threshold", "Network cable", "Video monitor", "Power supply"],
                correct_answer="Bias and threshold",
                explanation="The bias sets the activation threshold for the weighted sum.",
                difficulty=QuizDifficulty.HARD,
                source_timestamp=SourceTimestamp(timestamp=35.0, formatted_time="00:35", label="Bias concept"),
                source_chunk_id="test_chunk_001",
            ),
            QuizQuestionInternal(
                id="q_4",
                question="How are weights adjusted during training?",
                options=["Backpropagation and gradient updates", "Manual slider adjustment", "Random guesswork", "Resetting the computer"],
                correct_answer="Backpropagation and gradient updates",
                explanation="Training iteratively computes gradients to adjust weights.",
                difficulty=QuizDifficulty.MEDIUM,
                source_timestamp=SourceTimestamp(timestamp=75.0, formatted_time="01:15", label="Backpropagation"),
                source_chunk_id="test_chunk_002",
            ),
            QuizQuestionInternal(
                id="q_5",
                question="What is the input layer in digit recognition?",
                options=["784 neurons representing pixel grayscale values", "A camera sensor", "10 output digits", "A microphone"],
                correct_answer="784 neurons representing pixel grayscale values",
                explanation="Each pixel in the 28x28 image corresponds to one input neuron.",
                difficulty=QuizDifficulty.EASY,
                source_timestamp=SourceTimestamp(timestamp=10.0, formatted_time="00:10", label="Input layer"),
                source_chunk_id="test_chunk_001",
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Quiz Generation Endpoint Tests
# ---------------------------------------------------------------------------

@patch("main.generate_quiz")
def test_create_quiz_success_and_security(mock_gen_quiz, sample_chunks, sample_internal_quiz):
    mock_gen_quiz.return_value = (sample_internal_quiz, "gemini-2.5-flash")

    payload = {
        "video_id": "vid_123",
        "title": "Neural Networks",
        "chunks": sample_chunks,
        "num_questions": 5,
    }

    response = client.post("/api/ai/quiz", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["video_id"] == "vid_123"
    assert data["model_used"] == "gemini-2.5-flash"
    assert data["chunk_count"] == 2

    # Check quiz client view
    quiz = data["quiz"]
    assert quiz["quiz_id"] == "quiz_session_abc"
    assert quiz["question_count"] == 5

    # CRITICAL SECURITY CHECK: correct_answer and explanation must NOT exist in the response
    for q in quiz["questions"]:
        assert "correct_answer" not in q, "SECURITY FLAW: correct_answer exposed in client response!"
        assert "explanation" not in q, "SECURITY FLAW: explanation exposed in client response!"
        assert len(q["options"]) == 4

    # Verify quiz was securely saved into QUIZ_STORE
    assert "quiz_session_abc" in QUIZ_STORE
    assert QUIZ_STORE["quiz_session_abc"].quiz_id == "quiz_session_abc"


def test_create_quiz_empty_chunks_fails_validation():
    payload = {
        "video_id": "vid_123",
        "chunks": [],
        "num_questions": 5,
    }
    response = client.post("/api/ai/quiz", json=payload)
    assert response.status_code == 422


@patch("main.generate_quiz")
def test_create_quiz_gemini_error_mapped(mock_gen_quiz, sample_chunks):
    mock_gen_quiz.side_effect = GeminiRateLimitError("Rate limit exceeded")

    payload = {
        "video_id": "vid_123",
        "chunks": sample_chunks,
        "num_questions": 5,
    }
    response = client.post("/api/ai/quiz", json=payload)
    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Quiz Evaluation Endpoint Tests (Deterministic Adaptive Scoring)
# ---------------------------------------------------------------------------

def test_evaluate_quiz_all_correct_strong_tier(sample_internal_quiz):
    QUIZ_STORE[sample_internal_quiz.quiz_id] = sample_internal_quiz

    payload = {
        "quiz_id": sample_internal_quiz.quiz_id,
        "selected_answers": {
            "q_1": "Non-linear mathematical transformation",
            "q_2": "The cost/loss function",
            "q_3": "Bias and threshold",
            "q_4": "Backpropagation and gradient updates",
            "q_5": "784 neurons representing pixel grayscale values",
        }
    }

    response = client.post("/api/ai/quiz/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["total_questions"] == 5
    assert data["correct_count"] == 5
    assert data["score_percentage"] == 100.0
    assert data["performance_tier"] == "Strong"
    assert "Excellent mastery" in data["performance_summary"]
    assert len(data["weak_chunk_ids"]) == 0

    # Ensure answers and explanations are now revealed for review
    for res in data["question_results"]:
        assert res["is_correct"] is True
        assert res["correct_answer"] is not None
        assert res["explanation"] is not None


def test_evaluate_quiz_developing_tier_60_percent(sample_internal_quiz):
    QUIZ_STORE[sample_internal_quiz.quiz_id] = sample_internal_quiz

    # 3 out of 5 correct = 60.0%
    payload = {
        "quiz_id": sample_internal_quiz.quiz_id,
        "selected_answers": {
            "q_1": "Non-linear mathematical transformation", # correct
            "q_2": "The cost/loss function",                 # correct
            "q_3": "Bias and threshold",                     # correct
            "q_4": "Random guesswork",                       # incorrect (chunk_002)
            "q_5": "A microphone",                           # incorrect (chunk_001)
        }
    }

    response = client.post("/api/ai/quiz/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["total_questions"] == 5
    assert data["correct_count"] == 3
    assert data["score_percentage"] == 60.0
    assert data["performance_tier"] == "Developing"
    assert "Good progress" in data["performance_summary"]

    # Verify weak chunks identified
    assert "test_chunk_001" in data["weak_chunk_ids"]
    assert "test_chunk_002" in data["weak_chunk_ids"]


def test_evaluate_quiz_needs_revision_tier_40_percent(sample_internal_quiz):
    QUIZ_STORE[sample_internal_quiz.quiz_id] = sample_internal_quiz

    # 2 out of 5 correct = 40.0%
    payload = {
        "quiz_id": sample_internal_quiz.quiz_id,
        "selected_answers": {
            "q_1": "Non-linear mathematical transformation", # correct
            "q_2": "The cost/loss function",                 # correct
            "q_3": "Power supply",                           # incorrect
            "q_4": "Resetting the computer",                 # incorrect
            "q_5": "A microphone",                           # incorrect
        }
    }

    response = client.post("/api/ai/quiz/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["total_questions"] == 5
    assert data["correct_count"] == 2
    assert data["score_percentage"] == 40.0
    assert data["performance_tier"] == "Needs Revision"
    assert "Needs revision" in data["performance_summary"]


def test_evaluate_quiz_missing_answers_gracefully_handled(sample_internal_quiz):
    QUIZ_STORE[sample_internal_quiz.quiz_id] = sample_internal_quiz

    # User only answered q_1 and skipped the other 4
    payload = {
        "quiz_id": sample_internal_quiz.quiz_id,
        "selected_answers": {
            "q_1": "Non-linear mathematical transformation",
        }
    }

    response = client.post("/api/ai/quiz/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["correct_count"] == 1
    assert data["score_percentage"] == 20.0
    assert data["performance_tier"] == "Needs Revision"
    # Skipped questions have selected_answer=None and is_correct=False
    skipped_results = [r for r in data["question_results"] if r["question_id"] != "q_1"]
    for sr in skipped_results:
        assert sr["selected_answer"] is None
        assert sr["is_correct"] is False


def test_evaluate_quiz_unknown_quiz_id_returns_404():
    payload = {
        "quiz_id": "non_existent_quiz_xyz",
        "selected_answers": {"q_1": "Some Option"},
    }
    response = client.post("/api/ai/quiz/evaluate", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_evaluate_quiz_unknown_question_id_returns_422(sample_internal_quiz):
    QUIZ_STORE[sample_internal_quiz.quiz_id] = sample_internal_quiz

    payload = {
        "quiz_id": sample_internal_quiz.quiz_id,
        "selected_answers": {"q_999": "Bogus question answer"},
    }
    response = client.post("/api/ai/quiz/evaluate", json=payload)
    assert response.status_code == 422
    assert "unknown question id" in response.json()["detail"].lower()


def test_evaluate_quiz_invalid_answer_choice_returns_422(sample_internal_quiz):
    QUIZ_STORE[sample_internal_quiz.quiz_id] = sample_internal_quiz

    payload = {
        "quiz_id": sample_internal_quiz.quiz_id,
        "selected_answers": {"q_1": "An answer option that does not exist in options list"},
    }
    response = client.post("/api/ai/quiz/evaluate", json=payload)
    assert response.status_code == 422
    assert "invalid answer choice" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Flashcards Endpoint Tests
# ---------------------------------------------------------------------------

@patch("main.generate_flashcards")
def test_create_flashcards_success(mock_gen_flashcards, sample_chunks):
    from models import Flashcard, GeneratedFlashcards

    mock_deck = GeneratedFlashcards(
        topic="Neural Network Architecture",
        card_count=2,
        cards=[
            Flashcard(
                id="c_1",
                front="What is a layer?",
                back="A group of neurons operating at the same stage of computation.",
                difficulty=QuizDifficulty.EASY,
                source_timestamp=SourceTimestamp(timestamp=15.0, formatted_time="00:15", label="Layer concept"),
                source_chunk_id="test_chunk_001",
            ),
            Flashcard(
                id="c_2",
                front="What is backpropagation?",
                back="An algorithm to compute the gradient of the loss function with respect to weights.",
                difficulty=QuizDifficulty.MEDIUM,
                source_timestamp=SourceTimestamp(timestamp=70.0, formatted_time="01:10", label="Backprop concept"),
                source_chunk_id="test_chunk_002",
            )
        ]
    )
    mock_gen_flashcards.return_value = (mock_deck, "gemini-2.5-flash")

    payload = {
        "video_id": "vid_123",
        "title": "Neural Networks",
        "chunks": sample_chunks,
        "num_cards": 2,
    }

    response = client.post("/api/ai/flashcards", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["video_id"] == "vid_123"
    assert data["model_used"] == "gemini-2.5-flash"
    assert data["chunk_count"] == 2
    assert data["flashcards"]["card_count"] == 2
    assert data["flashcards"]["cards"][0]["front"] == "What is a layer?"
    assert data["flashcards"]["cards"][0]["source_chunk_id"] == "test_chunk_001"


def test_create_flashcards_empty_chunks_fails_validation():
    payload = {
        "video_id": "vid_123",
        "chunks": [],
        "num_cards": 5,
    }
    response = client.post("/api/ai/flashcards", json=payload)
    assert response.status_code == 422


@patch("main.generate_quiz")
def test_create_quiz_and_evaluate_with_long_gemini_question_ids(mock_gen_quiz, sample_chunks):
    """
    Regression test for QuizQuestion.id VARCHAR(128) fix:
    Verifies that quizzes with realistic long Gemini slug IDs (>64 chars)
    persist successfully to PostgreSQL without string truncation errors,
    can be evaluated, and have their attempts and answers saved correctly.
    """
    long_quiz_id = "quiz_but_what_is_a_neural_network_chapter_1"  # 46 chars
    long_q1_id = "q1_neuron_definition_and_activation_range"     # 42 chars -> composite = 89 chars
    long_q2_id = "q2_input_layer_handwritten_digit_pixels"       # 39 chars -> composite = 86 chars

    mock_quiz = GeneratedQuizInternal(
        quiz_id=long_quiz_id,
        video_id="vid_123",
        title="Deep Learning Chapter 1: Neural Networks",
        instructions="Choose the best answer for each question.",
        questions=[
            QuizQuestionInternal(
                id=long_q1_id,
                question="In neural networks, what is a neuron?",
                options=["A holder of a number between 0 and 1", "A biological brain cell", "A database table", "A network wire"],
                correct_answer="A holder of a number between 0 and 1",
                explanation="Neurons hold activation numbers between 0 and 1.",
                difficulty=QuizDifficulty.EASY,
                source_timestamp=SourceTimestamp(timestamp=165.0, formatted_time="02:45", label="Neuron definition"),
                source_chunk_id="test_chunk_001",
            ),
            QuizQuestionInternal(
                id=long_q2_id,
                question="What does the input layer represent in MNIST classification?",
                options=["Grayscale pixel values of 28x28 image", "Output digits 0 through 9", "Hidden weights", "Learning rate"],
                correct_answer="Grayscale pixel values of 28x28 image",
                explanation="Each input neuron holds a pixel value.",
                difficulty=QuizDifficulty.MEDIUM,
                source_timestamp=SourceTimestamp(timestamp=175.0, formatted_time="02:55", label="Input layer"),
                source_chunk_id="test_chunk_002",
            ),
        ],
    )
    mock_gen_quiz.return_value = (mock_quiz, "gemini-2.5-flash")

    # 1. Generate & persist quiz
    payload = {
        "video_id": "vid_123",
        "title": "Deep Learning Chapter 1",
        "chunks": sample_chunks,
        "num_questions": 2,
    }
    response = client.post("/api/ai/quiz", json=payload)
    assert response.status_code == 200, f"Quiz generation failed: {response.text}"
    data = response.json()
    assert data["status"] == "completed"
    assert data["quiz"]["quiz_id"] == long_quiz_id
    assert len(data["quiz"]["questions"]) == 2
    assert data["quiz"]["questions"][0]["id"] == long_q1_id

    # 2. Evaluate submission using the client question IDs
    eval_payload = {
        "quiz_id": long_quiz_id,
        "selected_answers": {
            long_q1_id: "A holder of a number between 0 and 1",
            long_q2_id: "Grayscale pixel values of 28x28 image",
        },
    }
    eval_resp = client.post("/api/ai/quiz/evaluate", json=eval_payload)
    assert eval_resp.status_code == 200, f"Quiz evaluation failed: {eval_resp.text}"
    eval_data = eval_resp.json()
    assert eval_data["score_percentage"] == 100.0
    assert eval_data["performance_tier"] == "Strong"
    assert eval_data["correct_count"] == 2

