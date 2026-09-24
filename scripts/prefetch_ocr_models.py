from app.core.config import Settings
from app.services.ocr_engine import build_ocr_engine


def main() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        ocr_inference_engine="paddle",
        ocr_language="en",
        ocr_model_version="PP-OCRv5",
        ocr_device="cpu",
        ocr_min_confidence=0.0,
        ocr_enable_mkldnn=False,
    )
    engine = build_ocr_engine(settings)
    print(
        "Prefetched OCR runtime:",
        engine.name,
        engine.version,
        engine.model_version,
        engine.language,
    )


if __name__ == "__main__":
    main()
