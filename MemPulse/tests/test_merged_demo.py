from mempulse.desktop_seed import seed_desktop
from mempulse.demo_scenarios import seed_rich_demo
from mempulse.merged_demo import merged_cases, merged_questions, merge_preview, seed_merged_demo
from mempulse.service import TopicFacade


def test_curated_corpus_preserves_all_sources_and_only_merges_same_identity():
    cases=merged_cases()
    events=[event for case in cases for event in case['events']]
    assert len(cases)==53
    assert len(events)==len({event['event_id'] for event in events})==284
    assert len({event['metadata']['source_event_id'] for event in events})==284
    kylin=next(case for case in cases if case['id']=='kylin_package')
    assert len(kylin['events'])==14
    assert len(merged_questions())==192
    for event in events:
        assert 'self' not in [person['id'] for person in event['person_refs']]
        for evidence in event['metadata']['keyword_evidence']:
            assert evidence['quote'] == event['content']


def test_merge_archives_only_known_wholly_synthetic_topics_and_is_idempotent(tmp_path):
    service=TopicFacade(tmp_path/'demo.db')
    seed_desktop(service)
    old=seed_rich_demo(service)
    assert len(service.list_topics()['topics'])==42
    mixed=old['topic_ids']['chenghai:delivery']
    service.ingest({'content':'用户实际补充的审批记录，必须保留。','topic_id':mixed})
    protected=service._topic(mixed).to_dict()
    preview=merge_preview(service)
    assert len(preview['archive_topics'])==41
    first=seed_merged_demo(service)
    assert first['events_created']==284
    assert first['archived_topics']==41
    assert service._topic(mixed).to_dict()==protected
    assert len(service.list_topics()['topics'])==54
    assert service.store.get_event('desktop-demo:kylin:0').content != '[FORGOTTEN]'
    second=seed_merged_demo(service)
    assert second['events_created']==0 and second['archived_topics']==0
    assert len(service.list_topics()['topics'])==54
    result=service.search('澄海园区接口鉴权失败')
    assert not any(service.store.get_topic(event['topic_id']).state=='archived' for event in result['results'])
    service.store.close()


def test_curated_import_does_not_resurrect_forgotten_source_events(tmp_path):
    service=TopicFacade(tmp_path/'forget.db')
    seed_desktop(service)
    source='desktop-demo:network:1'
    service.forget('event',source)
    seed_merged_demo(service)
    assert service.store.get_event('demo:v4:'+source) is None
    service.store.close()
