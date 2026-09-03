from app.voice.speech import sentences


def test_incomplete_text_is_all_tail():
    ready, tail = sentences("I am still writing this")
    assert ready == []
    assert tail == "I am still writing this"


def test_a_finished_sentence_is_speakable_and_the_rest_is_held():
    ready, tail = sentences(
        "Your refund was issued on the third of July and should arrive shortly. It ca"
    )
    assert ready == ["Your refund was issued on the third of July and should arrive shortly."]
    assert tail == "It ca"


def test_short_openers_are_merged_rather_than_spoken_alone():
    # "Hi there." on its own costs a full TTS round trip and buys a moment of audio.
    ready, tail = sentences("Hi there. I have checked your order and it left the warehouse. And")
    assert ready == ["Hi there. I have checked your order and it left the warehouse."]
    assert tail == "And"


def test_devanagari_danda_ends_a_sentence():
    ready, _ = sentences("आपका ऑर्डर कल भेज दिया गया था और अब रास्ते में है। अगला")
    assert ready == ["आपका ऑर्डर कल भेज दिया गया था और अब रास्ते में है।"]


def test_nothing_is_dropped_between_the_spoken_pieces_and_the_tail():
    text = "One two three four five. Six seven eight nine ten. Eleven twelve"
    ready, tail = sentences(text)
    # The whole point: what gets spoken plus what is still buffered is the input.
    assert " ".join([*ready, tail]) == text
