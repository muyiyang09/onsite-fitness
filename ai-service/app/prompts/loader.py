"""Prompt 加载器：从 YAML 读取模板，带 lru_cache 缓存。

设计要点：
  - prompt 是**关键资源**（缺失会导致节点无法工作），所以加载失败直接抛异常、
    让服务在启动时就暴露问题，而不是静默返回空串；
  - 用 lru_cache 缓存，避免每个请求都读磁盘；
  - 定位用 `Path(__file__).parent`，配合 pyproject 的 package-data 把 YAML 打进安装包。
"""

from __future__ import annotations

import logging
from functools import cache
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).parent


@cache
def _load_raw(name: str) -> dict:
    path = _PROMPT_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt 文件不存在：{path}（请确认 app/prompts/{name}.yaml 已打包）"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    logger.info("加载 Prompt：%s (version=%s)", data.get("name"), data.get("version"))
    return data


def load_prompt(name: str) -> str:
    """加载指定 prompt 的模板文本（production label）。"""
    return _load_raw(name)["template"]


def load_prompt_meta(name: str) -> dict:
    """加载完整元数据（含 version/changelog），用于展示/审计。"""
    return _load_raw(name)


__all__ = ["load_prompt", "load_prompt_meta"]
