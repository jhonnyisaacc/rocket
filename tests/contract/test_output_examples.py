from scripts.output_examples import generate


def test_review_examples_have_intended_presentation(tmp_path):
    examples = generate(tmp_path)
    assert len(examples) == 11
    for name, row in examples.items():
        assert not row['payload']['execution_enabled']
        assert row['mode'] == 'REPLAY'
        if name == 'watch-silent':
            assert row['presentation']['silent']
        elif name == 'shorts-no-setup':
            assert row['presentation'] == {'market_result': False, 'silent': False, 'diagnostic_only': False}
        else:
            assert row['presentation']['market_result'], name
