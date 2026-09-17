"""Five-class tag normalisation and validation.

Tags are deliberately deterministic. The embedding backend only produces the
vector tag; it never creates arbitrary graph edges or bypasses validation.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from .models import Event, Tag, TagKind, Topic

ROLE_ALIASES = {
    "发起人": "initiator", "审核人": "reviewer", "参会人": "participant",
    "联系人": "contact", "执行人": "executor", "其他": "other",
    "initiator": "initiator", "reviewer": "reviewer", "participant": "participant",
    "contact": "contact", "executor": "executor", "other": "other",
}
DEFAULT_ROLES = ("initiator", "reviewer", "participant", "contact", "executor", "other")
WIDE_KEYWORDS = {"办公", "报告", "会议", "文档", "文件", "docx", "项目", "工作"}
WIDE_KEYWORDS |= {'opencode', '会话', '用户', '助手', '测试', '修改', '处理', '继续', '你好', '今天', '昨天'}
WIDE_KEYWORDS |= {'执行成功', '执行完成', '执行失败', '运行结果', 'success', 'failed', 'completed'}
# This vocabulary is an extractor, not the lexical tokenizer used by FTS.
# Unrecognised host-model proposals remain pending until a user confirms them.
KEYWORD_ALIASES = {
    '断网补传': '离线补传', '离线同步': '离线补传', '数据补传': '离线补传',
    '验收签字': '交付验收', '交付验收': '交付验收', '回滚': '版本回滚',
    '去重': '幂等去重', '重复上传': '幂等去重', '权限校验': '接口鉴权',
    '接口鉴权': '接口鉴权', '打印驱动': '打印驱动', '灰度发布': '灰度发布',
    '客户端打包': '客户端打包', '麒麟适配': '麒麟适配', '模型评估': '模型评估',
    '模型量化': '模型量化', '数据清洗': '数据清洗', '排班规则': '排班规则',
    '费用报销': '费用报销', '预算调整': '预算调整', '采购审批': '采购审批',
    '无障碍': '无障碍适配', '备份恢复': '备份恢复', '标签规范': '标签规范',
    '话题边界': '话题边界', '合同附件': '合同附件', '培训签到': '培训签到',
    '时间同步': '时间同步', '数据迁移': '数据迁移', '双语校对': '双语校对',
}


def extract_keywords(text):
    value = _clean_text(text).lower()
    return sorted({canonical for word, canonical in KEYWORD_ALIASES.items() if word in value})[:8]


def _clean_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value)).strip()
    return re.sub(r"\s+", " ", text)


def _stable_source(event_id: str | None) -> tuple[str, ...]:
    return (event_id,) if event_id else ()


def normalize_person(value: str, event_id: str | None = None, role: str | None = None,
                     confidence: float = 1.0) -> Tag:
    raw = _clean_text(value)
    parsed_role = role
    if "@" in raw:
        raw, parsed_role = raw.rsplit("@", 1)
    canonical_role = ROLE_ALIASES.get(_clean_text(parsed_role or "other"), "other")
    person_id = raw.removeprefix("person:").strip().lower()
    if not person_id:
        raise ValueError("person tag requires a non-empty id")
    canonical = f"person:{person_id}@{canonical_role}"
    return Tag(TagKind.PERSON, canonical, person_id, confidence,
               _stable_source(event_id), role=canonical_role)


def normalize_resource(value: str, event_id: str | None = None,
                       confidence: float = 1.0) -> Tag:
    raw = _clean_text(value)
    if raw.startswith("res:") and not raw.startswith("res:sha1("):
        identifier = raw[4:]
        if not identifier: raise ValueError("empty resource id")
        return Tag(TagKind.RESOURCE, "res:" + identifier, identifier, confidence, _stable_source(event_id))
    if raw.startswith("res:"):
        raw = raw[4:]
    if raw.startswith("sha1(") and raw.endswith(")"):
        digest = raw[5:-1].lower()
        if re.fullmatch(r"[0-9a-f]{40}", digest):
            return Tag(TagKind.RESOURCE, f"res:{digest}", digest, confidence, _stable_source(event_id))
    if re.fullmatch(r"[0-9a-f]{40}", raw.lower()):
        digest = raw.lower()
        return Tag(TagKind.RESOURCE, f"res:{digest}", digest, confidence, _stable_source(event_id))
    if not raw or (not any(separator in raw for separator in ('/', '\\')) and not Path(raw).suffix):
        raise ValueError('resource requires a stable res: identifier or an explicit file path')
    path = Path(raw).expanduser()
    try:
        norm = unicodedata.normalize("NFC", str(path.resolve(strict=False)))
    except OSError:
        norm = unicodedata.normalize("NFC", str(path))
    norm = norm.rstrip("/\\") or "/"
    return Tag(TagKind.RESOURCE, f"res:path:{norm}", norm, confidence, _stable_source(event_id))


def normalize_time(value: str | datetime, event_id: str | None = None,
                   confidence: float = 1.0) -> list[Tag]:
    if isinstance(value, datetime):
        dt = value
    else:
        raw = _clean_text(value).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            # Accept a date or YYYY-MM directly for imported events.
            if re.fullmatch(r"\d{4}-\d{2}", raw):
                return [Tag(TagKind.TIME, f"time:{raw}", raw, confidence, _stable_source(event_id))]
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                dt = datetime.fromisoformat(raw)
            else:
                raise ValueError(f"unsupported time value: {value!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    iso_year, iso_week, _ = dt.isocalendar()
    month = dt.strftime("%Y-%m")
    week = f"{iso_year}-W{iso_week:02d}"
    return [
        Tag(TagKind.TIME, f"time:{month}", month, confidence, _stable_source(event_id)),
        Tag(TagKind.TIME, f"time:{week}", week, confidence, _stable_source(event_id)),
    ]


def normalize_keyword(value: str, event_id: str | None = None,
                      confidence: float = 1.0,
                      synonyms: Mapping[str, str] | None = None) -> Tag:
    text = _clean_text(value).lower().replace(" ", "")
    synonyms = synonyms or {}
    text = synonyms.get(text, text)
    if not text:
        raise ValueError("keyword tag requires a non-empty value")
    # Keep arbitrary punctuation out of the graph key while retaining CJK/word chars.
    text = re.sub(r"[^\w\-\u3400-\u9fff]", "", text, flags=re.UNICODE)
    if not text:
        raise ValueError("keyword tag has no normalisable characters")
    return Tag(TagKind.KEYWORD, f"kw:{text}", text, confidence, _stable_source(event_id))


def normalize_vector(topic_id: str, model_rev: str, event_id: str | None = None,
                     confidence: float = 1.0) -> Tag:
    model = _clean_text(model_rev).replace(" ", "_")
    tid = _clean_text(topic_id)
    if not model or not tid:
        raise ValueError("vector tag requires model revision and topic id")
    return Tag(TagKind.VECTOR, f"vec:{model}:{tid}", tid, confidence, _stable_source(event_id))


def event_tags(event: Event, *, topic_id: str | None = None,
               model_rev: str | None = None,
               embedding_confidence: float = 1.0,
               synonyms: Mapping[str, str] | None = None) -> list[Tag]:
    """Build deterministic tags from the structured parts of an event."""
    result: list[Tag] = []
    for person in event.person_refs:
        role = None
        label = None
        if isinstance(person, Mapping):
            role, label, person = person.get("role"), person.get('name'), person.get("id", "")
        tag = normalize_person(str(person), event.event_id, role, event.confidence)
        if re.search(r'[\u3400-\u9fff]', tag.value):
            tag = replace(tag, status='pending')
        result.append(replace(tag, label=label))
    for resource in event.resource_ids:
        value = str(resource)
        base = event.metadata.get('opencode_directory') or event.metadata.get('project_ref')
        if base and not value.startswith('res:') and not Path(value).is_absolute():
            value = str(Path(base) / value)
        tag = normalize_resource(value, event.event_id, event.confidence)
        label = next((item.get('name') for item in event.metadata.get('resources', [])
                      if isinstance(item, Mapping) and item.get('id') == resource), None)
        result.append(replace(tag, label=label))
    if event.occurred_at:
        result.extend(normalize_time(event.occurred_at, event.event_id, event.confidence))
    words = event.metadata.get("keywords", []) if event.metadata else []
    if isinstance(words, str):
        words = [words]
    for word in words:
        tag = normalize_keyword(str(word), event.event_id, event.confidence, synonyms=synonyms or KEYWORD_ALIASES)
        structured = bool(event.metadata.get('keywords_confirmed') or event.metadata.get('synthetic'))
        phrase = str(word).strip()
        if not keyword_is_specific(phrase):
            tag = replace(tag, status='attribute')
        elif not structured and tag.value not in KEYWORD_ALIASES.values():
            tag = replace(tag, status='pending')
        result.append(tag)
    for candidate in event.metadata.get('keyword_candidates', []):
        if not isinstance(candidate, Mapping) or not candidate.get('value'):
            continue
        phrase = str(candidate['value'])
        quote = str(candidate.get('quote') or '')
        confidence = min(event.confidence, float(candidate.get('confidence', 0)))
        # Open vocabulary: a new technical phrase may be accepted based on its
        # evidence, not whether it appears in a preconfigured domain dictionary.
        supported = quote and quote in event.content and phrase in quote
        status = 'accepted' if supported and confidence >= 0.85 and keyword_is_specific(phrase) else 'pending'
        result.append(replace(normalize_keyword(phrase, event.event_id, confidence), status=status))
    if topic_id and model_rev:
        result.append(normalize_vector(topic_id, model_rev, event.event_id,
                                       min(event.confidence, embedding_confidence)))
    return _dedupe_tags(result)


def validate_topic_tags(topic: Topic, tags: Iterable[Tag], *, degree_counts: Mapping[str, int] | None = None,
                        degree_limits: Mapping[TagKind, int] | None = None) -> tuple[list[Tag], list[Tag], list[str]]:
    """Validate tags and return ``(accepted, pending, missing_kinds)``.

    A missing kind is reported rather than fabricated. Topics can therefore be
    marked incomplete until an event supplies the missing evidence.
    """
    degree_counts = degree_counts or {}
    limits = degree_limits or {
        TagKind.PERSON: 100, TagKind.RESOURCE: 200, TagKind.TIME: 500,
        TagKind.KEYWORD: 40, TagKind.VECTOR: 20,
    }
    accepted: list[Tag] = []
    pending: list[Tag] = []
    for tag in _dedupe_tags(tags):
        if not tag.source_event_ids or tag.status == 'pending':
            pending.append(replace(tag, status='pending'))
            continue
        if tag.confidence < 0.5:
            pending.append(replace(tag, status='pending'))
            continue
        degree = degree_counts.get(tag.canonical, 0)
        if tag.kind == TagKind.TIME or (tag.kind == TagKind.KEYWORD and tag.value in WIDE_KEYWORDS) or degree > limits.get(tag.kind, 100):
            accepted.append(replace(tag, status='attribute'))
        else:
            accepted.append(tag)
    present = {tag.kind for tag in accepted}
    missing = [kind.value for kind in TagKind if kind not in present]
    topic.state = "incomplete" if missing else "active"
    # Prefer recurrent, specific anchors. Extra descriptive words remain
    # attributes instead of turning the topic into a bag of graph nodes.
    keywords = sorted((tag for tag in accepted if tag.kind == TagKind.KEYWORD and tag.status == 'accepted'),
                      key=lambda tag: (-len(tag.source_event_ids), -tag.confidence, tag.canonical))
    keep = {tag.canonical for tag in keywords[:8]}
    accepted = [replace(tag, status='attribute') if tag.kind == TagKind.KEYWORD and tag.status == 'accepted' and tag.canonical not in keep else tag for tag in accepted]
    return accepted, pending, missing


def keyword_is_specific(value):
    text = _clean_text(value).lower()
    if text in WIDE_KEYWORDS or not 2 <= len(text) <= 24:
        return False
    if re.search(r'[，。！？；\n?]|^(请|帮我|我想|你能|我们|怎么|为什么|是不是)|[吗呢吧]$', text):
        return False
    if re.search(r'[/\\]|\.(md|txt|docx|pdf|xlsx|csv|json|log)$', text):
        return False
    return not bool(re.fullmatch(r'v?\d[\d.\-: ]*', text))


def _dedupe_tags(tags: Iterable[Tag]) -> list[Tag]:
    merged: dict[str, Tag] = {}
    for tag in tags:
        previous = merged.get(tag.canonical)
        if previous is None:
            merged[tag.canonical] = tag
            continue
        if previous.status != tag.status and 'pending' in (previous.status, tag.status):
            merged[tag.canonical] = previous if tag.status == 'pending' else tag
            continue
        sources = tuple(dict.fromkeys(previous.source_event_ids + tag.source_event_ids))
        merged[tag.canonical] = Tag(
            tag.kind, tag.canonical, tag.value,
            max(previous.confidence, tag.confidence), sources,
            "pending" if "pending" in (previous.status, tag.status) else previous.status,
            tag.role or previous.role,
            tag.label or previous.label,
        )
    return list(merged.values())


def keywords_from_text(text: str) -> set[str]:
    # Chinese runs and latin/number runs provide a predictable lexical baseline.
    terms = set(re.findall(r"[\u3400-\u9fff]{2,}|[A-Za-z0-9][A-Za-z0-9_.-]{1,}", _clean_text(text).lower()))
    expanded = set(terms)
    for term in terms:
        if re.fullmatch(r"[\u3400-\u9fff]+", term):
            expanded.update(term[i:i+2] for i in range(len(term)-1))
    return {term for term in expanded if term not in WIDE_KEYWORDS}


def resource_digest(content: bytes) -> str:
    return hashlib.sha1(content).hexdigest()
