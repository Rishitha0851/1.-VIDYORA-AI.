"""
VIDYORA AI - Tests for Step 12 Quiz and Flashcard AI Generation Services
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from google.genai import errors as genai_errors
from models import (
    Flashcard,
    GeneratedFlashcards,
    GeneratedQuizInternal,
    QuizDifficulty,
    QuizQuestionInternal,
    SourceTimestamp,
    TranscriptChunk,
)
from services.gemini_service import (
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiValidationError,
    build_flashcards_prompt,
    build_quiz_prompt,
    convert_quiz_to_client_view,
    find_matching_chunk_id,
    generate_flashcards,
    generate_quiz,
)


@pytest.fixture
def sample_chunks():
    return [
        TranscriptChunk(
            chunk_id="test_vid_chunk_000",
            chunk_index=0,
            video_id="test_vid",
            text="Neural networks are computational models composed of layers of artificial neurons. Each neuron in the input layer holds an activation representing grayscale pixel intensity.",
            start_time=0.0,
            end_time=60.0,
            duration=60.0,
            word_count=26,
            segment_start_index=0,
            segment_end_index=2,
        ),
        TranscriptChunk(
            chunk_id="test_vid_chunk_001",
            chunk_index=1,
            video_id="test_vid",
            text="Weights and biases determine when a neuron fires. A sigmoid squishing function compresses the weighted sum into a value between zero and one.",
            start_time=60.0,
            end_time=120.0,
            duration=60.0,
            word_count=23,
            segment_start_index=3,
            segment_end_index=5,
        ),
    ]


@pytest.fixture
def mock_valid_quiz_json():
    return json.dumps({
        "quiz_id": "quiz_test_123",
        "video_id": "test_vid",
        "title": "Neural Networks Fundamentals Quiz",
        "instructions": "Answer the multiple choice questions based on the video.",
        "questions": [
            {
                "id": "q_1",
                "question": "What does a neuron's activation in the first layer represent?",
                "options": [
                    "Grayscale pixel intensity",
                    "The final prediction score",
                    "The learning rate",
                    "The cost gradient",
                ],
                "correct_answer": "Grayscale pixel intensity",
                "explanation": "Input neurons represent the pixel intensities of the 28x28 image.",
                "difficulty": "easy",
                "source_timestamp": {
                    "timestamp": 25.0,
                    "formatted_time": "00:25",
                    "label": "Input layer pixel activations",
                },
                "source_chunk_id": "test_vid_chunk_000",
            },
            {
                "id": "q_2",
                "question": "What function squishes the weighted sum into a range between 0 and 1?",
                "options": [
                    "Sigmoid function",
                    "ReLU function",
                    "Identity function",
                    "Linear transformation",
                ],
                "correct_answer": "Sigmoid function",
                "explanation": "The video explains that the sigmoid function compresses values between 0 and 1.",
                "difficulty": "medium",
                "source_timestamp": {
                    "timestamp": 85.0,
                    "formatted_time": "01:25",
                    "label": "Sigmoid squishing function",
                },
                "source_chunk_id": "test_vid_chunk_001",
            }
        ]
    })


@pytest.fixture
def mock_valid_flashcards_json():
    return json.dumps({
        "topic": "Neural Network Fundamentals",
        "card_count": 2,
        "cards": [
            {
                "id": "card_1",
                "front": "What is an activation in an artificial neuron?",
                "back": "A numerical value (typically between 0 and 1) representing the excitement or intensity of that neuron.",
                "difficulty": "easy",
                "source_timestamp": {
                    "timestamp": 20.0,
                    "formatted_time": "00:20",
                    "label": "Activation concept",
                },
                "source_chunk_id": "test_vid_chunk_000",
            },
            {
                "id": "card_2",
                "front": "What purpose does the bias serve in a neuron?",
                "back": "It sets a threshold for how active the inputs need to be before the neuron meaningfully activates.",
                "difficulty": "medium",
                "source_timestamp": {
                    "timestamp": 90.0,
                    "formatted_time": "01:30",
                    "label": "Bias and threshold explanation",
                },
                "source_chunk_id": "test_vid_chunk_001",
            }
        ]
    })


# ---------------------------------------------------------------------------
# Prompt Building Unit Tests
# ---------------------------------------------------------------------------

def test_build_quiz_prompt_contains_rules_and_chunks():
    prompt = build_quiz_prompt("Deep Learning Intro", "[Chunk 1: Hello]", num_questions=3)
    assert "Deep Learning Intro" in prompt
    assert "exactly 3 multiple-choice questions" in prompt
    assert "Provide exactly 4 options per question" in prompt
    assert "'correct_answer' MUST exactly match" in prompt
    assert "[Chunk 1: Hello]" in prompt


def test_build_flashcards_prompt_contains_rules_and_chunks():
    prompt = build_flashcards_prompt("Deep Learning Intro", "[Chunk 1: Hello]", num_cards=5)
    assert "Deep Learning Intro" in prompt
    assert "deck of 5 high-yield conceptual flashcards" in prompt
    assert "'front'" in prompt
    assert "'back'" in prompt
    assert "[Chunk 1: Hello]" in prompt


def test_find_matching_chunk_id(sample_chunks):
    # Within chunk 0 (0.0 to 60.0)
    assert find_matching_chunk_id(30.0, sample_chunks) == "test_vid_chunk_000"
    # Within chunk 1 (60.0 to 120.0)
    assert find_matching_chunk_id(95.0, sample_chunks) == "test_vid_chunk_001"
    # Preserves valid candidate_id
    assert find_matching_chunk_id(10.0, sample_chunks, "test_vid_chunk_001") == "test_vid_chunk_001"


# ---------------------------------------------------------------------------
# Quiz Generation Tests
# ---------------------------------------------------------------------------

@patch("services.gemini_service.get_gemini_client")
def test_generate_quiz_success(mock_get_client, sample_chunks, mock_valid_quiz_json):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = mock_valid_quiz_json
    mock_client.models.generate_content.return_value = mock_resp
    mock_get_client.return_value = mock_client

    quiz, model_used = generate_quiz("test_vid", "Test Title", sample_chunks, num_questions=2)

    assert isinstance(quiz, GeneratedQuizInternal)
    assert len(quiz.questions) == 2
    assert quiz.questions[0].correct_answer == "Grayscale pixel intensity"
    assert len(quiz.questions[0].options) == 4
    assert quiz.questions[0].source_chunk_id == "test_vid_chunk_000"
    assert model_used == "gemini-2.5-flash"


def test_convert_quiz_to_client_view(mock_valid_quiz_json):
    internal_quiz = GeneratedQuizInternal.model_validate_json(mock_valid_quiz_json)
    client_view = convert_quiz_to_client_view(internal_quiz)

    assert client_view.quiz_id == internal_quiz.quiz_id
    assert client_view.question_count == 2
    dumped = client_view.model_dump()
    for q in dumped["questions"]:
        assert "correct_answer" not in q, "Security failure: correct_answer exposed in client model"
        assert "explanation" not in q, "Security failure: explanation exposed in client model"
        assert len(q["options"]) == 4


def test_generate_quiz_empty_chunks_raises_value_error():
    with pytest.raises(ValueError, match="Cannot generate quiz without transcript chunks"):
        generate_quiz("test_vid", "Test Title", [])


@patch("services.gemini_service.get_gemini_client")
def test_generate_quiz_empty_response_raises_validation_error(mock_get_client, sample_chunks):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = ""
    mock_client.models.generate_content.return_value = mock_resp
    mock_get_client.return_value = mock_client

    with pytest.raises(GeminiValidationError, match="Gemini returned an empty response"):
        generate_quiz("test_vid", "Test Title", sample_chunks)


@patch("services.gemini_service.get_gemini_client")
def test_generate_quiz_invalid_options_raises_validation_error(mock_get_client, sample_chunks):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    # Bad payload: only 3 options
    mock_resp.text = json.dumps({
        "quiz_id": "quiz_123",
        "video_id": "test_vid",
        "title": "Quiz",
        "instructions": "Instructions",
        "questions": [
            {
                "id": "q_1",
                "question": "What is an activation?",
                "options": ["A", "B", "C"],
                "correct_answer": "A",
                "explanation": "...",
                "difficulty": "easy",
                "source_timestamp": {"timestamp": 10.0, "formatted_time": "00:10", "label": "test"},
            }
        ]
    })
    mock_client.models.generate_content.return_value = mock_resp
    mock_get_client.return_value = mock_client

    with pytest.raises(GeminiValidationError, match="Failed to validate structured AI response"):
        generate_quiz("test_vid", "Test Title", sample_chunks)


@patch("services.gemini_service.get_gemini_client")
def test_generate_quiz_mismatched_correct_answer_raises_validation_error(mock_get_client, sample_chunks):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    # Bad payload: correct_answer is "Z", not in options ["A", "B", "C", "D"]
    mock_resp.text = json.dumps({
        "quiz_id": "quiz_123",
        "video_id": "test_vid",
        "title": "Quiz",
        "instructions": "Instructions",
        "questions": [
            {
                "id": "q_1",
                "question": "What is an activation?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "Z",
                "explanation": "...",
                "difficulty": "easy",
                "source_timestamp": {"timestamp": 10.0, "formatted_time": "00:10", "label": "test"},
            }
        ]
    })
    mock_client.models.generate_content.return_value = mock_resp
    mock_get_client.return_value = mock_client

    with pytest.raises(GeminiValidationError, match="Failed to validate structured AI response"):
        generate_quiz("test_vid", "Test Title", sample_chunks)


@patch("services.gemini_service.get_gemini_client")
def test_generate_quiz_timeout_raises_gemini_timeout(mock_get_client, sample_chunks):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TimeoutError("Request timed out")
    mock_get_client.return_value = mock_client

    with pytest.raises(GeminiTimeoutError):
        generate_quiz("test_vid", "Test Title", sample_chunks)


@patch("services.gemini_service.get_gemini_client")
def test_generate_quiz_rate_limit_raises_gemini_rate_limit(mock_get_client, sample_chunks):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.body_segments = [{"error": {"message": "Resource exhausted: quota exceeded", "code": 429}}]
    err = genai_errors.APIError(429, mock_resp)
    mock_client.models.generate_content.side_effect = err
    mock_get_client.return_value = mock_client

    with pytest.raises(GeminiRateLimitError):
        generate_quiz("test_vid", "Test Title", sample_chunks)


# ---------------------------------------------------------------------------
# Flashcards Generation Tests
# ---------------------------------------------------------------------------

@patch("services.gemini_service.get_gemini_client")
def test_generate_flashcards_success(mock_get_client, sample_chunks, mock_valid_flashcards_json):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = mock_valid_flashcards_json
    mock_client.models.generate_content.return_value = mock_resp
    mock_get_client.return_value = mock_client

    flashcards, model_used = generate_flashcards("test_vid", "Test Title", sample_chunks, num_cards=2)

    assert isinstance(flashcards, GeneratedFlashcards)
    assert flashcards.card_count == 2
    assert flashcards.cards[0].front == "What is an activation in an artificial neuron?"
    assert flashcards.cards[0].source_chunk_id == "test_vid_chunk_000"
    assert model_used == "gemini-2.5-flash"


def test_generate_flashcards_empty_chunks_raises_value_error():
    with pytest.raises(ValueError, match="Cannot generate flashcards without transcript chunks"):
        generate_flashcards("test_vid", "Test Title", [])


@patch("services.gemini_service.get_gemini_client")
def test_generate_flashcards_rate_limit_raises_gemini_rate_limit(mock_get_client, sample_chunks):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.body_segments = [{"error": {"message": "Resource exhausted: quota exceeded", "code": 429}}]
    err = genai_errors.APIError(429, mock_resp)
    mock_client.models.generate_content.side_effect = err
    mock_get_client.return_value = mock_client

    with pytest.raises(GeminiRateLimitError):
        generate_flashcards("test_vid", "Test Title", sample_chunks)
