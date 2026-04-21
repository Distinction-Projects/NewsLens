import os
import unittest

from fastapi.middleware.cors import CORSMiddleware

from src.api.fastapi_app import _parse_cors_origins, create_fastapi_app


class FastApiAppTests(unittest.TestCase):
    def test_parse_cors_origins_defaults(self):
        self.assertEqual(
            _parse_cors_origins(None),
            ["http://localhost:3000", "http://127.0.0.1:3000"],
        )

    def test_parse_cors_origins_filters_blanks(self):
        raw = "https://a.example.com,  ,https://b.example.com"
        self.assertEqual(
            _parse_cors_origins(raw),
            ["https://a.example.com", "https://b.example.com"],
        )

    def test_create_fastapi_app_installs_cors_middleware(self):
        old_value = os.environ.get("NEWS_API_CORS_ORIGINS")
        os.environ["NEWS_API_CORS_ORIGINS"] = "https://frontend.example.com"
        try:
            app = create_fastapi_app()
        finally:
            if old_value is None:
                os.environ.pop("NEWS_API_CORS_ORIGINS", None)
            else:
                os.environ["NEWS_API_CORS_ORIGINS"] = old_value

        cors_layers = [layer for layer in app.user_middleware if layer.cls is CORSMiddleware]
        self.assertEqual(len(cors_layers), 1)
        self.assertEqual(cors_layers[0].kwargs.get("allow_origins"), ["https://frontend.example.com"])
        self.assertTrue(cors_layers[0].kwargs.get("allow_credentials"))


if __name__ == "__main__":
    unittest.main()
