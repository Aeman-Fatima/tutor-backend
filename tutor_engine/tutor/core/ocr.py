"""
Change E — OCR with TrOCR (local model) as primary, vision API as fallback.

Primary:  microsoft/trocr-base-handwritten via HuggingFace transformers + Pillow.
Fallback: Anthropic/Gemini vision API (existing behaviour).

The TrOCR model (~300 MB) is downloaded once on first use and cached by HuggingFace.
If transformers or Pillow are not installed, the fallback is used silently.
"""

import sys

try:
    from PIL import Image as PILImage
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    _TROCR_AVAILABLE = True
except ImportError:
    _TROCR_AVAILABLE = False

_trocr_processor = None
_trocr_model     = None

_SYSTEM = (
    "You are a transcription assistant. You will receive an image of a student's "
    "handwritten or typed math solution.\n\n"
    "Your job is to transcribe EXACTLY what is written — preserve all numbers, "
    "arithmetic operations (+, -, ×, ÷, =), and any final-answer statement.\n\n"
    "Rules:\n"
    "  • Do NOT solve, simplify, or correct the math.\n"
    "  • Do NOT add words or explanations that are not in the image.\n"
    "  • Ignore background noise, ruled lines, smudges.\n"
    "  • Output plain text only — no markdown, no bullet points.\n"
    "  • If a final answer is circled or underlined, include it on its own line "
    "    prefixed with 'Answer:'\n"
    "  • If the image is blank or unreadable, output the single word: UNREADABLE"
)


def _get_trocr():
    global _trocr_processor, _trocr_model
    if _trocr_processor is None:
        _trocr_processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
        _trocr_model     = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")
    return _trocr_processor, _trocr_model


def _extract_trocr(image_path: str) -> str:
    """Run TrOCR on the image and return transcribed text."""
    processor, model = _get_trocr()
    image = PILImage.open(image_path).convert("RGB")
    pixel_values = processor(image, return_tensors="pt").pixel_values
    generated_ids = model.generate(pixel_values)
    text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return text.strip()


# TODO: Anthropic/Gemini vision API fallback — uncomment if local OCR is unavailable
# def _extract_vision_api(image_path: str) -> str:
#     media_type, _ = mimetypes.guess_type(image_path)
#     if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
#         media_type = "image/jpeg"
#     with open(image_path, "rb") as f:
#         image_data = base64.standard_b64encode(f.read()).decode("utf-8")
#     from core.llm_client import image_response
#     return image_response(image_data, media_type, _SYSTEM)


def extract_text(image_path: str) -> str:
    """
    Transcribe a student's handwritten math solution from an image file.
    Uses TrOCR (local, no API cost) exclusively.
    Raises RuntimeError if transformers/Pillow are not installed.
    """
    if not _TROCR_AVAILABLE:
        raise RuntimeError(
            "Local OCR unavailable: install transformers and Pillow "
            "('pip install transformers Pillow'). "
            "Anthropic vision API fallback is disabled."
        )
    result = _extract_trocr(image_path)
    if not result or result.upper() == "UNREADABLE":
        return "UNREADABLE"
    return result
