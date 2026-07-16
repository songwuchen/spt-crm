"""守卫：backend/scripts/china-regions.json 必须与 frontend/src/data/ 的同名文件保持一致。

背景：地址回填脚本(scripts/backfill_customer_region.py)需要这份行政区划数据。前端目录不会打进
backend 镜像，因此在 backend/scripts/ 保留一份「烘焙进镜像」的副本(由 Dockerfile `COPY . .` 带入)，
容器重建后依然可用，避免 FileNotFoundError。此测试防止两份副本悄悄漂移。
更新数据时：改前端那份后，执行
    cp frontend/src/data/china-regions.json backend/scripts/china-regions.json
"""
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_BACKEND_COPY = _ROOT / "backend" / "scripts" / "china-regions.json"
_FRONTEND_SRC = _ROOT / "frontend" / "src" / "data" / "china-regions.json"


def test_backend_region_data_bundled():
    assert _BACKEND_COPY.is_file(), (
        "backend/scripts/china-regions.json 缺失：地址回填脚本依赖它、且需随镜像发布。"
        " 请从 frontend/src/data/china-regions.json 同步一份。"
    )


def test_backend_region_data_matches_frontend():
    # 前端目录在 backend 容器内可能不存在；仅在完整仓库(CI/本地)校验两份一致。
    if not _FRONTEND_SRC.is_file():
        return
    assert _BACKEND_COPY.read_bytes() == _FRONTEND_SRC.read_bytes(), (
        "backend/scripts/china-regions.json 与 frontend/src/data/china-regions.json 不一致。"
        " 请执行: cp frontend/src/data/china-regions.json backend/scripts/china-regions.json"
    )
