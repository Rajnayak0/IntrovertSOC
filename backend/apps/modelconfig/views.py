from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from llm import adapter
from llm import health as health_module
from llm import local_engine
from llm.config import get_endpoint_config

from apps.accounts.permissions import IsAdminRole, ReadOnlyOrAdmin
from apps.audit.models import record

from .models import ModelConfig


def _status_payload(force: bool = False) -> dict:
    cfg = get_endpoint_config()
    health = health_module.health_check(force=force)
    ctx, ctx_source = adapter.context_info()
    payload = {
        "connected": health.ok,
        "base_url": health.base_url,
        "model": cfg.model,
        "gguf_path": cfg.gguf_path,
        "config_source": cfg.source,
        "server_model": health.server_model,
        "family": adapter.detect_family(
            f"{health.server_model or ''} {cfg.gguf_path} {cfg.model}"
        ),
        "context_window": ctx,
        "context_source": ctx_source,
        "detail": health.detail,
        "latency_ms": health.latency_ms,
        "checked_at": health.checked_at,
    }
    if not health.ok:
        payload["banner"] = health_module.unavailable_banner(health)
    return payload


def _launch_commands(cfg, gguf_path: str, port: int) -> dict:
    gguf = gguf_path or "path/to/model.gguf"
    quoted = f'"{gguf}"'
    return {
        "windows": f'llamafile-0.10.6.exe -m {quoted} --server --host 127.0.0.1 --port {port}',
        "posix": f"./llamafile -m {quoted} --server --host 127.0.0.1 --port {port}",
        "note": (
            "Run this in a terminal you keep open. Adjust the executable name to your "
            "llamafile binary. IntrovertSOC does not start or bundle the model process - "
            "it only connects to it."
        ),
    }


@api_view(["GET"])
def model_status(request):
    force = str(request.query_params.get("force", "")).lower() in {"1", "true", "yes"}
    return Response(_status_payload(force=force))


@api_view(["POST"])
@permission_classes([IsAdminRole])
def model_test(request):
    return Response(local_engine.test_connection())


@api_view(["GET", "PUT"])
@parser_classes([JSONParser])
@permission_classes([ReadOnlyOrAdmin])
def model_config_detail(request):
    if request.method == "GET":
        cfg = get_endpoint_config()
        row = ModelConfig.get_solo()
        port = int(cfg.base_url.rsplit(":", 1)[-1]) if ":" in cfg.base_url.rsplit("/", 1)[-1] else 8080
        return Response(
            {
                "effective": {"base_url": cfg.base_url, "model": cfg.model, "gguf_path": cfg.gguf_path},
                "source": cfg.source,
                "override": {
                    "base_url": row.base_url if row else "",
                    "model": row.model if row else "",
                    "gguf_path": row.gguf_path if row else "",
                    "context_window": row.context_window if row else 0,
                },
                "launch_commands": _launch_commands(cfg, cfg.gguf_path, port),
            }
        )

    row = ModelConfig.get_or_create_solo()
    base_url = str(request.data.get("base_url", row.base_url) or "").strip().rstrip("/")
    model = str(request.data.get("model", row.model) or "").strip()
    gguf_path = str(request.data.get("gguf_path", row.gguf_path) or "").strip()

    raw_ctx = request.data.get("context_window", row.context_window)
    try:
        context_window = max(0, min(int(raw_ctx if raw_ctx not in (None, "") else 0), adapter.MAX_CONTEXT_WINDOW))
    except (TypeError, ValueError):
        return Response({"detail": "context_window must be an integer (0 = auto)."}, status=status.HTTP_400_BAD_REQUEST)

    if base_url and not base_url.startswith(("http://", "https://")):
        return Response({"detail": "base_url must start with http:// or https://"}, status=status.HTTP_400_BAD_REQUEST)

    row.base_url = base_url
    row.model = model
    row.gguf_path = gguf_path
    row.context_window = context_window
    row.updated_by = request.user.username
    row.save()
    record(
        "update",
        obj=row,
        actor=request.user,
        changes={
            "base_url": base_url,
            "model": model,
            "gguf_path": gguf_path,
            "context_window": context_window,
        },
    )
    health_module.invalidate_cache()
    return Response(_status_payload(force=True))
