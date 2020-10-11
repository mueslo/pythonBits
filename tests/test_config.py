import pytest
from unittest import mock

import pythonbits.config as config
c = config.config

c.register('Foo', 'bar', 'bar?')
c.register('Foo', 'bar2', 'bar2?')
c.register('Foo', 'bar3', 'bar3?', ask=True)
c.register('Foo', 'bar4', 'bar4?', ask=True)
c.register('Foo', 'ham', 'ham?')
c.register('Foo', 'eggs', 'eggs?')


def test_get():
    # todo: atomic tests with fresh config file

    # registered option, present in config file
    assert c.get('Foo', 'bar') == 'baz'
    assert c.get('Foo', 'bar', 'bar_default') == 'baz'
    with mock.patch('builtins.input', lambda q: 'some_input'):
        assert c.get('Foo', 'ham') == 'some_input'

    # registered option, present in config file, but empty
    assert c.get('Foo', 'bar2', 'bar2_default') == 'bar2_default'
    with mock.patch('builtins.input', lambda q: 'bar2_input'):
        assert c.get('Foo', 'bar2') == 'bar2_input'
    # assert c.get('Foo', 'bar2') == 'bar2_input' # see todo: non-mocked _write

    # registered option, not present in config file, ask=True
    assert c.get('Foo', 'bar3', 'bar3_default') == 'bar3_default'
    with mock.patch('builtins.input', side_effect=['bar3_input', 'y']) as m:
        assert c.get('Foo', 'bar3') == 'bar3_input'
        with pytest.raises(StopIteration):  # make sure all consumed
            next(m.side_effect)
    assert c.get('Foo', 'bar3') == 'bar3_input'

    # lifecycle test: registered option, not present, ask=True
    assert c.get('Foo', 'bar4', 'bar4_default') == 'bar4_default'
    with mock.patch('builtins.input', side_effect=['bar4_input', 'n']) as m:
        assert c.get('Foo', 'bar4') == 'bar4_input'
        with pytest.raises(StopIteration):  # make sure all consumed
            next(m.side_effect)
    assert c.get('Foo', 'bar4', 'bar4_default2') == 'bar4_default2'
    with mock.patch('builtins.input', side_effect=['bar4_input2', 'nr']) as m:
        assert c.get('Foo', 'bar4') == 'bar4_input2'
        with pytest.raises(StopIteration):  # make sure all consumed
            next(m.side_effect)
    assert c.get('Foo', 'bar4', 'bar4_default3') == 'bar4_default3'
    with mock.patch('builtins.input', side_effect=['bar4_input3']) as m:
        assert c.get('Foo', 'bar4') == 'bar4_input3'
        with pytest.raises(StopIteration):  # make sure all consumed
            next(m.side_effect)

    # unregistered option, present in config file, but empty
    assert c.get('Foo', 'spam', 'spam_default') == 'spam_default'
    with pytest.raises(config.UnregisteredOption):
        c.get('Foo', 'spam')

    # unregistered option, present in config file
    assert c.get('Foo', 'spam2') == 'spam2_value'
    assert c.get('Foo', 'spam2', 'spam2_default') == 'spam2_value'

    # unregistered option, not present in config file
    assert c.get('Foo', 'spam3', 'spam3_default') == 'spam3_default'
    with pytest.raises(config.UnregisteredOption):
        c.get('Foo', 'spam3')

    # registered option, not present in config file
    assert c.get('Foo', 'eggs', default='default_input') == 'default_input'

    with mock.patch('builtins.input', lambda q: 'more_input'):
        assert c.get('Foo', 'eggs') == 'more_input'

    assert c.get('Foo', 'eggs') == 'more_input'
