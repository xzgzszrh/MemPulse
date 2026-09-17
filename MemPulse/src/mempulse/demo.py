"""Explicitly requested synthetic demonstration; never mixed with benchmark results."""


def seed_demo(service):
    cases = [
        ("甲客户交付报告", "acme-delivery", "res:acme-report", "周宁"),
        ("乙客户交付报告", "beta-delivery", "res:beta-report", "周宁"),
        ("桌面网络排障", "network-debug", "res:net-log", "林夏"),
    ]
    result = []
    for title, key, resource, person in cases:
        first = service.ingest(
            {
                "event_id": "demo:" + key,
                "idempotency_key": "demo:" + key,
                "content": title + "：需求梳理完成，下一步核验材料。",
                "topic_title": title,
                "person_refs": [person + "@participant", "self@initiator"],
                "resource_ids": [resource],
                "metadata": {
                    "force_new": True,
                    "synthetic": True,
                    "keywords": [key],
                    "input_files": [resource],
                    "completed_steps": ["需求梳理"],
                    "pending_steps": ["核验材料"],
                    "template_version": "V3",
                },
            }
        )
        result.append(first)
        if first.get("topic_id"):
            service.ingest(
                {
                    "event_id": "demo:" + key + ":follow",
                    "idempotency_key": "demo:" + key + ":follow",
                    "content": "已补充审核记录；待确认最终输出。",
                    "topic_hint": first["topic_id"],
                    "person_refs": [person + "@reviewer"],
                    "resource_ids": [resource],
                    "metadata": {
                        "synthetic": True,
                        "keywords": [key],
                        "pending_steps": ["确认最终输出"],
                    },
                }
            )
    return {"synthetic": True, "topics": result}
