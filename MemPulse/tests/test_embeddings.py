"""Real-model integration checks; set MEMPULSE_TEST_MODEL to enable ONNX cases."""
import json
import math
import os
import pytest
from mempulse.embeddings import EmbeddingInputError, OnnxEncoder, model_assets
from mempulse.service import TopicFacade
from mempulse.demo_scenarios import seed_rich_demo

@pytest.fixture(scope='module')
def encoder():
    root = os.environ.get('MEMPULSE_TEST_MODEL')
    if not root:
        pytest.skip('MEMPULSE_TEST_MODEL is not set')
    return OnnxEncoder(root)

def test_manifest_mismatch_fails_before_model_loading(tmp_path):
    root = tmp_path / 'encoder'
    root.mkdir()
    (root / 'model-fp32.onnx').write_bytes(b'incorrect model')
    (root / 'tokenizer.json').write_text('{}')
    (root / 'tide_config.json').write_text('{}')
    (tmp_path / 'manifest.json').write_text(json.dumps({'files': {'encoder/model-fp32.onnx': {'sha256': '0'*64, 'bytes': 15}}}))
    with pytest.raises(ValueError, match='manifest mismatch'):
        model_assets(tmp_path)

def test_rich_demo_is_idempotent_and_keeps_sources(tmp_path):
    service = TopicFacade(tmp_path / 'demo.db')
    first = seed_rich_demo(service)
    second = seed_rich_demo(service)
    assert first['events_created'] == 144
    assert second['events_created'] == 0 and second['events_already_present'] == 144
    assert len(service.list_topics()['topics']) == 36
    assert all(service.restore(topic_id=tid)['events'] for tid in first['topic_ids'].values())
    service.store.close()

def test_real_encoder_normalizes_and_matches_batch(encoder):
    queries = ['夜班清洁那部分水量该放在哪个时段？', '继续处理设备的验收说明']
    batch = encoder.encode_batch(queries, query=True)
    for text, vector in zip(queries, batch):
        assert len(vector) == 768 and all(math.isfinite(x) for x in vector)
        assert math.isclose(sum(x*x for x in vector), 1, abs_tol=1e-5)
        alone = encoder.encode_query(text)
        assert sum(a*b for a, b in zip(alone, vector)) > 0.9999
    document = encoder(queries[0])
    assert max(abs(a-b) for a,b in zip(document, batch[0])) > 1e-5

def test_real_encoder_refuses_empty_and_overlong_complete_inputs(encoder):
    before = encoder.inference_calls
    for query in ['', '   ', '保留完整的客户和项目身份信息' * 80]:
        with pytest.raises(EmbeddingInputError):
            encoder.encode_query(query)
    assert encoder.inference_calls == before

def test_real_model_routes_only_explicit_bindings_and_falls_back(encoder, tmp_path):
    service = TopicFacade(tmp_path / 'real.db', embed=encoder, model_rev=encoder.revision)
    topic = service.ingest({'content': '澄海园区夜间保洁水量按二十二点至六点计入夜间，不计入生产。', 'metadata': {'force_new': True}})['topic_id']
    before = len(service.list_topics()['topics'])
    found = service.search('night shift cleaning water consumption')
    assert found['backend'] == 'topic_first_tide'
    assert any(row['topic_id'] == topic for row in found['results'])
    assert found['route']['route'] == 'AMBIGUOUS' and found['route']['topic_id'] is None
    assert len(service.list_topics()['topics']) == before
    resumed = service.ingest({'content': '主管确认上述时段，等待归档。', 'topic_id': topic})
    assert resumed['route'] == 'RESUME' and resumed['topic_id'] == topic
    long_query = '保留完整的客户和项目身份信息' * 80
    fallback = service.search(long_query)
    assert fallback['backend'] == 'topic_first_fts'
    assert fallback['route']['embedding_fallback']
    saved = service.ingest({'content': long_query, 'metadata': {'force_new': True}})
    assert service.store.get_event(saved['event_id']).content == long_query
    assert service.store.get_topic(saved['topic_id']).vector is None
    service.forget(target_type='topic', target_id=topic)
    assert all(row['topic_id'] != topic for row in service.search('night shift cleaning water consumption')['results'])
    service.store.close()


def test_explicit_long_identity_does_not_fabricate_a_vector_tag(encoder, tmp_path):
    service=TopicFacade(tmp_path/'long-identity.db',embed=encoder,model_rev=encoder.revision)
    topic=service.core.create_topic(user_id='default',title='长目标',goal='保留完整的目标边界与来源信息' * 90)
    result=service.ingest({'content':'用户确认当前任务范围。','topic_id':topic.topic_id})
    saved=service.store.get_topic(topic.topic_id)
    assert saved.vector is None
    assert 'vector' in saved.metadata['missing_tag_kinds']
    assert not any(tag['kind']=='vector' for tag in result['tags'])
    service.store.close()
