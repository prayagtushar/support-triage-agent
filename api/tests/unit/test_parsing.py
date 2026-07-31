from app.llm.parsing import extract_json_object


def test_plain_object_passes_through():
    assert extract_json_object('{"intent": "billing"}') == '{"intent": "billing"}'


def test_strips_json_fence():
    raw = '```json\n{"intent": "refund"}\n```'
    assert extract_json_object(raw) == '{"intent": "refund"}'


def test_strips_bare_fence():
    assert extract_json_object('```\n{"a": 1}\n```') == '{"a": 1}'


def test_strips_reasoning_preamble():
    raw = '<think>the user is asking about money</think>\n{"intent": "billing"}'
    assert extract_json_object(raw) == '{"intent": "billing"}'


def test_drops_prose_either_side():
    raw = 'Here is the classification:\n{"intent": "how_to"}\nHope that helps.'
    assert extract_json_object(raw) == '{"intent": "how_to"}'


def test_handles_nested_objects():
    raw = 'noise {"a": {"b": {"c": 1}}} trailing'
    assert extract_json_object(raw) == '{"a": {"b": {"c": 1}}}'


def test_braces_inside_strings_do_not_end_the_object():
    raw = '{"note": "use {{Order Number}} here"}'
    assert extract_json_object(raw) == raw


def test_escaped_quote_does_not_end_the_string():
    raw = '{"note": "he said \\"hi\\" loudly"}'
    assert extract_json_object(raw) == raw


def test_returns_input_when_no_object_present():
    assert extract_json_object("sorry, I cannot do that") == "sorry, I cannot do that"
