"""
FastAPI backend for translating competitive-programming C++ code to Python.

Run locally with:
    uvicorn backend.fastapi_app:app --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.cpp_python_translator import translate_competitive_cpp


TRANSLATOR_MODE = os.getenv("TRANSLATOR_MODE", "rules").strip().lower()
USE_MODEL_TRANSLATOR = TRANSLATOR_MODE == "model"
MODEL_NAME = os.getenv("TRANSLATION_MODEL_NAME", "Salesforce/codet5-small")
TASK_PREFIX = "translate C++ to Python: "
MAX_INPUT_TOKENS = 512
MAX_OUTPUT_TOKENS = 512


class TranslationRequest(BaseModel):
    """JSON request body expected by POST /translate."""

    source_code: str = Field(
        ...,
        min_length=1,
        description="The C++ source code that should be translated to Python.",
    )


class TranslationResponse(BaseModel):
    """JSON response body returned by POST /translate."""

    translated_code: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load the model and tokenizer once when the API process starts, if enabled.

    FastAPI stores these objects on app.state so every request can reuse the
    same in-memory tokenizer and PyTorch model instead of downloading/loading
    them again.
    """

    if not USE_MODEL_TRANSLATOR:
        yield
        return

    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    model.to(device)
    model.eval()

    app.state.device = device
    app.state.tokenizer = tokenizer
    app.state.model = model

    yield

    # Explicit cleanup is helpful in long-running services and test suites.
    del app.state.model
    del app.state.tokenizer
    import torch

    if torch.cuda.is_available():
        torch.cuda.empty_cache()


app = FastAPI(
    title="C++ to Python Code Translator",
    description="Translate competitive-programming C++ snippets into Python.",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Small health endpoint for deployment checks."""

    return {"status": "ok"}


@app.post("/translate", response_model=TranslationResponse)
def translate_code(request: TranslationRequest) -> TranslationResponse:
    """
    Translate C++ source code to Python.

    HTTP handling:
    - FastAPI parses the incoming JSON request body into TranslationRequest.
    - Pydantic validates that source_code exists and is not empty.
    - The translated Python code is returned as JSON:
        {"translated_code": "..."}
    """

    source_code = request.source_code.strip()
    if not source_code:
        raise HTTPException(status_code=422, detail="source_code cannot be empty")

    if not USE_MODEL_TRANSLATOR:
        return TranslationResponse(translated_code=translate_competitive_cpp(source_code))

    tokenizer: Any = app.state.tokenizer
    model: Any = app.state.model
    device: Any = app.state.device

    model_input = f"{TASK_PREFIX}{source_code}"

    # Tokenization converts text into integer token IDs that the model can read.
    # With return_tensors="pt", Hugging Face returns PyTorch tensors:
    # - input_ids shape:      [batch_size=1, input_sequence_length]
    # - attention_mask shape: [batch_size=1, input_sequence_length]
    # Padding/truncation ensures the sequence is bounded by MAX_INPUT_TOKENS.
    encoded_input = tokenizer(
        model_input,
        return_tensors="pt",
        max_length=MAX_INPUT_TOKENS,
        padding="max_length",
        truncation=True,
    )

    # Move each tensor from CPU to the selected inference device. On a CUDA
    # machine, input_ids and attention_mask become GPU tensors with the same
    # shapes shown above.
    encoded_input = {
        tensor_name: tensor_value.to(device)
        for tensor_name, tensor_value in encoded_input.items()
    }

    try:
        # inference_mode disables gradient tracking. This reduces memory use and
        # latency because generation does not need backpropagation tensors.
        with torch.inference_mode():
            generated_ids = model.generate(
                input_ids=encoded_input["input_ids"],
                attention_mask=encoded_input["attention_mask"],
                max_length=MAX_OUTPUT_TOKENS,
                num_beams=4,
                early_stopping=True,
            )

        # generated_ids is an integer tensor with shape:
        # [batch_size=1, generated_sequence_length].
        # batch_decode maps token IDs back into a Python string and removes
        # special tokens such as <pad> and </s>.
        translated_code = tokenizer.batch_decode(
            generated_ids,
            skip_special_tokens=True,
        )[0].strip()

    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Model inference failed: {exc}",
        ) from exc

    return TranslationResponse(translated_code=translated_code)
