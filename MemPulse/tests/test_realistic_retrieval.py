import pytest

from mempulse.realistic_scenarios import CASES, seed_realistic
from mempulse.service import TopicFacade


@pytest.fixture
def service(tmp_path):
    service = TopicFacade(tmp_path/'scenarios.db')
    seed_realistic(service)
    yield service
    service.store.close()


def test_same_name_people_and_files_require_identity_clarification(service):
    for query in ('王磊之前签过什么？', '验收清单.xlsx 是哪版？'):
        result = service.search(query)
        assert result['needs_clarification']
        assert result['results'] == []


def test_time_filters_use_event_time_and_observed_time_separately(service):
    event = 'sim:v3:lake_access:08'
    occurred = service.search('湖东旧邮件', context={'from_time':'2026-08-30T00:00:00+08:00','to_time':'2026-08-31T00:00:00+08:00'})
    observed = service.search('湖东旧邮件', context={'from_time':'2026-09-10T00:00:00+08:00','to_time':'2026-09-11T00:00:00+08:00','time_axis':'observed_at'})
    assert event in {row['event_id'] for row in occurred['results']}
    assert event in {row['event_id'] for row in observed['results']}


def test_unknown_explicit_person_has_no_borrowed_facts(service):
    result = service.search('签过什么？', context={'person_names':['未登记的来访人']})
    assert result['results'] == [] and result['needs_clarification']


def test_queries_never_create_topics_bindings_or_tags(service):
    before = [topic.to_dict() for topic in service.store.list_topics(service.user_id)]
    for query in ('继续上次那个验收', '王磊上次提醒过什么', '北岸补传如何去重'):
        service.search(query)
    after = [topic.to_dict() for topic in service.store.list_topics(service.user_id)]
    assert before == after


def test_scenarios_are_idempotent_and_have_multiple_sessions(service):
    before = service.list_topics()['topics']
    seed_realistic(service)
    assert len(service.list_topics()['topics']) == len(before) == len(CASES)
    assert sum(len(topic['event_ids']) for topic in before) == 120
    for topic in before:
        events = service.store.list_events(topic['topic_id'])
        assert len({event.metadata['opencode_session_id'] for event in events}) == 4
        assert len({tag['canonical'] for tag in topic['tags'] if tag['kind']=='keyword' and tag['status']=='accepted'}) <= 8
