from bot.handlers.dictionary import dictionary_translation_text
from bot.keyboards import clamp_dictionary_page, dictionary_kb


class MockRow:
    def __init__(self, data):
        self._data = data

    def keys(self):
        return self._data.keys()

    def __getitem__(self, key):
        return self._data[key]


def test_dictionary_keyboard_uses_two_columns_and_navigation():
    words = [{'id': index, 'english': f'word-{index}'} for index in range(1, 11)]

    markup = dictionary_kb(words, page=0, total_items=25)

    assert len(markup.inline_keyboard) == 7
    assert [button.text for button in markup.inline_keyboard[0]] == ['word-1', 'word-2']
    assert [button.text for button in markup.inline_keyboard[4]] == ['word-9', 'word-10']
    assert [button.text for button in markup.inline_keyboard[5]] == ['⬅️ Oldingi', '1/3', 'Keyingi ➡️']
    assert markup.inline_keyboard[5][0].callback_data == 'dict:p:0'
    assert markup.inline_keyboard[5][2].callback_data == 'dict:p:1'
    assert markup.inline_keyboard[6][0].callback_data == 'back_main'


def test_clamp_dictionary_page_bounds():
    assert clamp_dictionary_page(-1, total_items=25) == 0
    assert clamp_dictionary_page(99, total_items=25) == 2
    assert clamp_dictionary_page(1, total_items=25) == 1
    assert clamp_dictionary_page(5, total_items=0) == 0


def test_dictionary_keyboard_truncates_long_labels_but_keeps_callback_id():
    words = [{'id': 42, 'english': 'a-very-long-dictionary-word-label'}]

    markup = dictionary_kb(words, page=0, total_items=1)

    assert markup.inline_keyboard[0][0].text == 'a-very-long-dictionary…'
    assert markup.inline_keyboard[0][0].callback_data == 'dict:w:42:0'


def test_dictionary_translation_text_includes_category():
    word = MockRow({
        'english': 'positive',
        'uzbek': 'musbat',
        'category': 'Number Types',
    })

    assert dictionary_translation_text(word) == 'positive — musbat\nKategoriya: Number Types'
