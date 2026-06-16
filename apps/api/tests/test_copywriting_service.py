import json

import httpx

from app.schemas.copywriting import CopywritingRequest
from app.services.copywriting_service import CopywritingService


def copywriting_request() -> CopywritingRequest:
    return CopywritingRequest(
        site="tiktok",
        product_name="便携榨汁杯",
        audience="健身和通勤人群",
        selling_points="USB充电, 小巧便携, 易清洗",
        keywords="portable blender, smoothie cup",
        tone="轻快直接",
    )


def test_copywriting_service_generates_template_copy(monkeypatch) -> None:
    class Settings:
        siliconflow_use_mock = True
        siliconflow_api_key = "test-key"
        siliconflow_base_url = "https://api.siliconflow.cn/v1"
        siliconflow_model = "inclusionAI/Ling-flash-2.0"
        siliconflow_timeout_seconds = 30

    monkeypatch.setattr("app.services.copywriting_service.get_settings", lambda: Settings())

    result = CopywritingService().generate(copywriting_request())

    assert result.site == "TikTok Shop"
    assert result.generation_source == "template"
    assert result.model is None
    assert result.skill == "amazon-copywriting-v1"
    assert "便携榨汁杯" in result.title
    assert len(result.bullet_points) >= 4
    assert "健身和通勤人群" in result.description
    assert "portable blender" in result.seo_keywords


def test_copywriting_service_generates_with_siliconflow(monkeypatch) -> None:
    class Settings:
        siliconflow_use_mock = False
        siliconflow_api_key = "test-key"
        siliconflow_base_url = "https://api.siliconflow.cn/v1"
        siliconflow_model = "inclusionAI/Ling-flash-2.0"
        siliconflow_timeout_seconds = 30

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "inclusionAI/Ling-flash-2.0"
        assert "response_format" not in body
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": """
                            {
                              "title": "便携榨汁杯 USB充电 适合健身通勤",
                              "short_title": "便携 USB 榨汁杯",
                              "bullet_points": ["USB充电，适合外出携带", "小巧杯身，方便通勤收纳", "易清洗结构，减少日常维护时间"],
                              "description": "面向健身和通勤人群的便携榨汁杯，适合制作果汁、奶昔等日常饮品。",
                              "tags": ["便携榨汁杯", "USB充电", "通勤"],
                              "seo_keywords": ["portable blender", "smoothie cup", "mini juicer"]
                            }
                            """
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def client_factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr("app.services.copywriting_service.get_settings", lambda: Settings())
    monkeypatch.setattr(httpx, "Client", client_factory)

    result = CopywritingService().generate(copywriting_request())

    assert result.generation_source == "siliconflow"
    assert result.model == "inclusionAI/Ling-flash-2.0"
    assert result.skill == "amazon-copywriting-v1"
    assert result.title == "便携榨汁杯 USB充电 适合健身通勤"
    assert result.bullet_points[0] == "USB充电，适合外出携带"
    assert "portable blender" in result.seo_keywords


def test_copywriting_service_falls_back_when_siliconflow_fails(monkeypatch) -> None:
    class Settings:
        siliconflow_use_mock = False
        siliconflow_api_key = "test-key"
        siliconflow_base_url = "https://api.siliconflow.cn/v1"
        siliconflow_model = "inclusionAI/Ling-flash-2.0"
        siliconflow_timeout_seconds = 30

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "temporary failure"})

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def client_factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr("app.services.copywriting_service.get_settings", lambda: Settings())
    monkeypatch.setattr(httpx, "Client", client_factory)

    result = CopywritingService().generate(copywriting_request())

    assert result.generation_source == "template"
    assert result.model is None
    assert "便携榨汁杯" in result.title
