import json

from mempulse.desktop import load_model_config


def test_bundled_fp32_is_relative_and_does_not_write_user_settings(tmp_path):
    bundle = tmp_path / 'application/mempulse/models/tide'
    (bundle / 'encoder').mkdir(parents=True)
    (bundle / 'encoder/model-fp32.onnx').touch()
    user = tmp_path / 'user'
    user.mkdir()
    assert load_model_config(user, bundle) == {'model_dir': str(bundle), 'precision': 'fp32'}
    assert not (user / 'model.json').exists()


def test_user_model_configuration_wins_over_bundled_default(tmp_path):
    config = {'model_dir': '/explicit/model', 'precision': 'fp32'}
    (tmp_path / 'model.json').write_text(json.dumps(config))
    assert load_model_config(tmp_path, tmp_path / 'bundled') == config


def test_source_and_legacy_packages_keep_unconfigured_behavior(tmp_path):
    assert load_model_config(tmp_path) is None
    assert load_model_config(tmp_path, tmp_path / 'missing') is None
