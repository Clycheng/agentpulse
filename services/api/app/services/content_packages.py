from __future__ import annotations

import json

from app.schemas.content_package import ContentPackageV1


def parse_content_package(value: object) -> ContentPackageV1:
    if isinstance(value, str):
        value = json.loads(value)
    return ContentPackageV1.model_validate(value)


def content_package_markdown(package: ContentPackageV1) -> str:
    lines = [
        f"# {package.platform} 内容发布计划",
        "",
        f"- 受众：{package.audience}",
        f"- 目标：{package.objective}",
        "",
        "## 发布日历",
    ]
    for item in sorted(package.schedule, key=lambda value: value.order):
        lines.extend(
            [
                "",
                f"### {item.order}. {item.title}",
                f"- 发布时间：{item.publish_at}",
                f"- 类型：{item.content_type}",
                f"- 开场钩子：{item.hook}",
                f"- CTA：{item.cta}",
                f"- 素材建议：{item.asset_suggestion}",
                f"- 来源：{', '.join(item.source_refs) or '无'}",
                "",
                item.body or item.script or "",
            ]
        )
    lines.extend(["", "## 来源"])
    for source in package.sources:
        lines.append(f"- {source.title or source.reference}: {source.reference}")
    lines.extend(["", "## 假设与未知项"])
    lines.extend(f"- {assumption}" for assumption in package.assumptions)
    return "\n".join(lines).strip() + "\n"
