from pythonbits import scene, bb
from unittest.mock import patch, Mock, call
import pytest

import json
import os
import pickle
import contextlib
import logbook

# Silence guessit
import logging
logging.getLogger('rebulk.rebulk').setLevel(logging.INFO)
logging.getLogger('rebulk.rules').setLevel(logging.INFO)
logging.getLogger('rebulk.processors').setLevel(logging.INFO)


def mock_response(text):
    return Mock(text=text, json=lambda: json.loads(text))

def mock_html(body):
    return ('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">'
            '<html xmlns="http://www.w3.org/1999/xhtml">'
            '<body>%s</body>'
            '</html>') % (body,)


@patch('pythonbits.scene._yield_file_info')
@patch('pythonbits.scene._check_dir')
def test_check_integrity_expects_APIError_from_check_dir(mock_check_dir, mock_yield_file_info):
    mock_check_dir.side_effect = scene.APIError('Owie!')
    mock_yield_file_info.return_value = ()
    cb = Mock()
    assert scene.check_integrity('path/to/Foo.S01.x264-ABC', on_error=cb) is None
    assert mock_check_dir.call_args_list == [call('path/to/Foo.S01.x264-ABC')]
    assert mock_yield_file_info.call_args_list == []
    assert [repr(arg) for arg in cb.call_args_list] == [repr(call('Foo.S01.x264-ABC', scene.APIError('Owie!')))]

@patch('pythonbits.scene._yield_file_info')
@patch('pythonbits.scene._check_dir')
def test_check_integrity_expects_APIError_from_yield_file_info_with_file_release(mock_check_dir, mock_yield_file_info):
    mock_check_dir.return_value = None
    mock_yield_file_info.side_effect = scene.APIError('Ooophff!')
    cb = Mock()
    assert scene.check_integrity('path/to/Foo.S01E02.x264-ABC.mkv', on_error=cb) is None
    assert mock_check_dir.call_args_list == []
    assert mock_yield_file_info.call_args_list == [call('path/to/Foo.S01E02.x264-ABC.mkv')]
    assert [repr(arg) for arg in cb.call_args_list] == [repr(call('Foo.S01E02.x264-ABC.mkv', scene.APIError('Ooophff!')))]

@patch('pythonbits.scene._yield_file_info')
@patch('pythonbits.scene._check_dir')
def test_check_integrity_expects_APIError_from_yield_file_info_with_directory_release(mock_check_dir, mock_yield_file_info):
    mock_check_dir.return_value = None
    mock_yield_file_info.side_effect = scene.APIError('Ooophff!')
    cb = Mock()
    assert scene.check_integrity('path/to/Foo.S01.x264-ABC', on_error=cb) is None
    assert mock_check_dir.call_args_list == [call('path/to/Foo.S01.x264-ABC')]
    assert mock_yield_file_info.call_args_list == [call('path/to/Foo.S01.x264-ABC')]
    assert [repr(arg) for arg in cb.call_args_list] == [repr(call('Foo.S01.x264-ABC', scene.APIError('Ooophff!')))]

@patch('pythonbits.scene._yield_file_info')
@patch('pythonbits.scene._check_dir')
def test_check_integrity_expects_SceneError_from_check_dir(mock_check_dir, mock_yield_file_info):
    mock_check_dir.side_effect = scene.SceneError('Nooo!')
    mock_yield_file_info.return_value = ()
    cb = Mock()
    assert scene.check_integrity('path/to/Foo.S01.x264-ABC', on_error=cb) is True
    assert mock_check_dir.call_args_list == [call('path/to/Foo.S01.x264-ABC')]
    assert mock_yield_file_info.call_args_list == [call('path/to/Foo.S01.x264-ABC')]
    assert [repr(arg) for arg in cb.call_args_list] == [repr(call('Foo.S01.x264-ABC', scene.SceneError('Nooo!')))]

@patch('pythonbits.scene._check_dir')
@patch('pythonbits.scene._check_file')
@patch('pythonbits.scene._yield_file_info')
def test_check_integrity_expects_SceneError_from_check_file(mock_yield_file_info, mock_check_file, mock_check_dir):
    mock_check_file.side_effect = scene.SceneError('Argh!')
    infos = ({'release_name': 'Foo.S01.x264-ABC', 'filename': 'Foo.S01E01.x264-ABC.mkv', 'size': 123, 'crc': '1234ABCD'},
             {'release_name': 'Foo.S01.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': 234, 'crc': 'ABCD1234'})
    mock_yield_file_info.return_value = infos
    cb = Mock()
    assert scene.check_integrity('path/to/Foo.S01.x264-ABC', on_error=cb) is True
    assert mock_check_dir.call_args_list == [call('path/to/Foo.S01.x264-ABC')]
    assert mock_yield_file_info.call_args_list == [call('path/to/Foo.S01.x264-ABC')]
    assert mock_check_file.call_args_list == [
        call('Foo.S01.x264-ABC/Foo.S01E01.x264-ABC.mkv', 'path/to/Foo.S01.x264-ABC/Foo.S01E01.x264-ABC.mkv', infos[0]),
        call('Foo.S01.x264-ABC/Foo.S01E02.x264-ABC.mkv', 'path/to/Foo.S01.x264-ABC/Foo.S01E02.x264-ABC.mkv', infos[1])]
    assert [repr(arg) for arg in cb.call_args_list] == [repr(call('Foo.S01.x264-ABC/Foo.S01E01.x264-ABC.mkv',
                                                                  scene.SceneError('Argh!'))),
                                                        repr(call('Foo.S01.x264-ABC/Foo.S01E02.x264-ABC.mkv',
                                                                  scene.SceneError('Argh!')))]

@patch('pythonbits.scene._check_dir')
@patch('pythonbits.scene._check_file')
@patch('pythonbits.scene._yield_file_info')
def test_check_integrity_calls_check_file_correctly_for_directory_release(mock_yield_file_info, mock_check_file, mock_check_dir):
    infos = ({'release_name': 'Foo.S01.x264-ABC', 'filename': 'Foo.S01E01.x264-ABC.mkv', 'size': 123, 'crc': '1234ABCD'},
             {'release_name': 'Foo.S01.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': 234, 'crc': 'ABCD1234'})
    mock_yield_file_info.return_value = infos
    cb = Mock()
    assert scene.check_integrity('path/to/Foo.S01.x264-ABC', on_error=cb) is False
    assert mock_check_dir.call_args_list == [call('path/to/Foo.S01.x264-ABC')]
    assert mock_yield_file_info.call_args_list == [call('path/to/Foo.S01.x264-ABC')]
    assert mock_check_file.call_args_list == [
        call('Foo.S01.x264-ABC/Foo.S01E01.x264-ABC.mkv', 'path/to/Foo.S01.x264-ABC/Foo.S01E01.x264-ABC.mkv', infos[0]),
        call('Foo.S01.x264-ABC/Foo.S01E02.x264-ABC.mkv', 'path/to/Foo.S01.x264-ABC/Foo.S01E02.x264-ABC.mkv', infos[1])]
    assert [repr(arg) for arg in cb.call_args_list] == []

@patch('pythonbits.scene._check_dir')
@patch('pythonbits.scene._check_file')
@patch('pythonbits.scene._yield_file_info')
def test_check_integrity_calls_check_file_correctly_for_file_release(mock_yield_file_info, mock_check_file, mock_check_dir):
    infos = ({'release_name': 'Foo.S01E02.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': 123, 'crc': '1234ABCD'},)
    mock_yield_file_info.return_value = infos
    cb = Mock()
    assert scene.check_integrity('path/to/Foo.S01E02.x264-ABC.mkv', on_error=cb) is False
    assert mock_check_dir.call_args_list == []
    assert mock_check_file.call_args_list == [call('Foo.S01E02.x264-ABC.mkv', 'path/to/Foo.S01E02.x264-ABC.mkv', infos[0])]
    assert mock_yield_file_info.call_args_list == [call('path/to/Foo.S01E02.x264-ABC.mkv')]
    assert [repr(arg) for arg in cb.call_args_list] == []


@patch('pythonbits.scene.search')
@patch('pythonbits.scene._guessit')
def test_release_names_returns_no_results_if_no_release_group(mock_guessit, mock_search):
    mock_guessit.return_value = {'title': 'The Foo', 'season': 1, 'episode': 2}
    assert scene.release_names('path/to/The.Foo.S01E02.x264.mkv') == []
    assert mock_guessit.call_args_list == [call('path/to/The.Foo.S01E02.x264.mkv')]
    assert mock_search.call_args_list == []

@patch('pythonbits.scene.search')
@patch('pythonbits.scene._guessit')
def test_release_names_returns_no_results_if_no_title(mock_guessit, mock_search):
    mock_guessit.return_value = {'release_group': 'ABC', 'season': 1, 'episode': 2}
    assert scene.release_names('path/to/S01E02.x264-ABC.mkv') == []
    assert mock_guessit.call_args_list == [call('path/to/S01E02.x264-ABC.mkv')]
    assert mock_search.call_args_list == []

@patch('pythonbits.scene.search')
@patch('pythonbits.scene._guessit')
def test_release_names_finds_something_on_first_try(mock_guessit, mock_search):
    mock_guessit.return_value = {'title': 'The Foo', 'release_group': 'ABC', 'season': 1, 'episode': 2}
    mock_search.return_value = ['The.Foo.S01E02.x264-ABC.mkv']
    assert scene.release_names('path/to/The.Foo.S01E02.x264-ABC.mkv') == mock_search.return_value
    assert mock_guessit.call_args_list == [call('path/to/The.Foo.S01E02.x264-ABC.mkv')]
    assert mock_search.call_args_list == [call(mock_guessit.return_value)]

@patch('pythonbits.scene.search')
@patch('pythonbits.scene._guessit')
def test_release_names_finds_looks_for_season_release_on_second_try(mock_guessit, mock_search):
    mock_guessit.return_value = {'title': 'The Foo', 'release_group': 'ABC', 'season': 1, 'episode': 2}
    mock_search.side_effect = ([], ['The.Foo.S01.x264-ABC.mkv'])
    assert scene.release_names('path/to/The.Foo.S01E02.x264-ABC.mkv') == ['The.Foo.S01.x264-ABC.mkv']
    assert mock_guessit.call_args_list == [call('path/to/The.Foo.S01E02.x264-ABC.mkv')]
    assert mock_search.call_args_list == [
        call(mock_guessit.return_value),
        call({'title': 'The Foo', 'release_group': 'ABC', 'season': 1})]


def test_check_file_on_nonscene_file_release():
    info = {'release_name': None, 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': None, 'crc': None}
    assert scene._check_file('Foo.S01E02.x264-ABC.mkv', 'path/to/Foo.S01E02.x264-ABC.mkv', info) is None

def test_check_file_on_nonscene_directory_release():
    info = {'release_name': None, 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': None, 'crc': None}
    assert scene._check_file('Foo.S01.x264-ABC/Foo.S01E02.x264-ABC.mkv', 'path/to/Foo.S01.x264-ABC/Foo.S01E02.x264-ABC.mkv', info) is None

def test_check_file_reports_wrong_filename_in_file_release_of_original_file_release():
    info = {'release_name': 'Foo.S01E02.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': 123, 'crc': '1234ABCD'}
    msg = r'^Foo.S01E02.x264-ABC.mkv was renamed to Foo S01E02 x264-ABC.mkv$'
    with pytest.raises(scene.SceneError, match=msg):
        scene._check_file('Foo S01E02 x264-ABC.mkv', 'path/to/Foo S01E02 x264-ABC.mkv', info)

def test_check_file_reports_wrong_dirname_in_directory_release_of_original_directory_release():
    info = {'release_name': 'Foo.S01.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': 123, 'crc': '1234ABCD'}
    msg = r'^Foo.S01.x264-ABC/Foo.S01E02.x264-ABC.mkv was renamed to Foo S01 x264-ABC/Foo.S01E02.x264-ABC.mkv$'
    with pytest.raises(scene.SceneError, match=msg):
        scene._check_file('Foo S01 x264-ABC/Foo.S01E02.x264-ABC.mkv', 'path/to/Foo S01 x264-ABC/Foo.S01E02.x264-ABC.mkv', info)

@patch('pythonbits.scene._path_exists', Mock(return_value=True))
@patch('pythonbits.scene._path_getsize', Mock(return_value=123))
def test_check_file_ignores_dirname_in_directory_release_of_original_file_release():
    info = {'release_name': 'Foo.S01E02.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': 123, 'crc': '1234ABCD'}
    assert scene._check_file('Foo S01 x264/Foo.S01E02.x264-ABC.mkv', 'path/to/Foo S01 x264/Foo.S01E02.x264-ABC.mkv', info) is True

@patch('pythonbits.scene._path_exists', Mock(return_value=True))
@patch('pythonbits.scene._path_getsize', Mock(return_value=123))
def test_check_file_ignores_dirname_in_file_release_of_original_directory_release():
    info = {'release_name': 'Foo.S01.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': 123, 'crc': '1234ABCD'}
    assert scene._check_file('Foo.S01E02.x264-ABC.mkv', 'path/to/Foo.S01E02.x264-ABC.mkv', info) is True

@patch('pythonbits.scene._path_exists', Mock(return_value=True))
@patch('pythonbits.scene._path_getsize')
def test_check_file_finds_wrong_filesize(mock_getsize):
    mock_getsize.return_value = 124
    info = {'release_name': 'Foo.S01E02.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': 123, 'crc': '12345678'}
    with pytest.raises(scene.SceneError, match=r'^Foo.S01E02.x264-ABC.mkv: Wrong size: 124 instead of 123 bytes$'):
        scene._check_file('Foo.S01E02.x264-ABC.mkv', 'path/to/Foo.S01E02.x264-ABC.mkv', info)
    assert mock_getsize.call_args_list == [call('path/to/Foo.S01E02.x264-ABC.mkv')]

@patch('pythonbits.scene._path_exists', Mock(return_value=True))
@patch('pythonbits.scene._path_getsize')
def test_check_file_finds_unmodified_release(mock_getsize):
    mock_getsize.return_value = 123
    info = {'release_name': 'Foo.S01E02.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': 123, 'crc': '12345678'}
    assert scene._check_file('Foo.S01E02.x264-ABC.mkv', 'path/to/Foo.S01E02.x264-ABC.mkv', info) is True
    assert mock_getsize.call_args_list == [call('path/to/Foo.S01E02.x264-ABC.mkv')]


@patch('pythonbits.scene.get_details')
def test_check_dir_finds_wrong_dirname(mock_get_details):
    mock_get_details.return_value = (
        'Foo.S01.x264-ABC',
        {'Foo.S01E01.x264-ABC.mkv': {'release_name': 'Foo.S01.x264-ABC', 'filename': 'Foo.S01E01.x264-ABC.mkv', 'size': 123, 'crc': '12345678'},
         'Foo.S01E02.x264-ABC.mkv': {'release_name': 'Foo.S01.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': 234, 'crc': 'ABCD1234'}})
    with pytest.raises(scene.SceneError, match=r'^Foo.S01.x264-ABC was renamed to Foo S01 x264-ABC$'):
        scene._check_dir('path/to/Foo S01 x264-ABC')

@patch('pythonbits.scene.get_details')
def test_check_dir_finds_correct_dirname(mock_get_details):
    mock_get_details.return_value = (
        'Foo.S01.x264-ABC',
        {'Foo.S01E01.x264-ABC.mkv': {'release_name': 'Foo.S01.x264-ABC', 'filename': 'Foo.S01E01.x264-ABC.mkv', 'size': 123, 'crc': '12345678'},
         'Foo.S01E02.x264-ABC.mkv': {'release_name': 'Foo.S01.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': 234, 'crc': 'ABCD1234'}})
    assert scene._check_dir('path/to/Foo.S01.x264-ABC') is True

@patch('pythonbits.scene.get_details')
def test_check_dir_fails_to_connect(mock_get_details):
    mock_get_details.side_effect = scene.APIError()
    assert scene._check_dir('path/to/Foo.S01.x264-ABC') is None


@patch('pythonbits.scene._get')
def test_get_details_fails_to_connect(mock_get):
    mock_get.side_effect = scene.APIError('Something went wrong')
    with pytest.raises(scene.APIError, match='^Something went wrong$'):
        scene.get_details('path/to/foo.txt')
    assert mock_get.call_args_list == [call('api/details/foo')]


@patch('pythonbits.scene._get')
def test_get_details_finds_release(mock_get):
    mock_get.return_value = mock_response(json.dumps({'name': 'Foo',
                                                      'archived-files': [{'name': 'Foo.png',
                                                                          'size': 123,
                                                                          'crc': '1234ABCD'}]}))
    assert scene.get_details('path/to/foo.txt') == ('Foo', {'Foo.png': {'release_name': 'Foo',
                                                                        'filename': 'Foo.png',
                                                                        'size': 123,
                                                                        'crc': '1234ABCD'}})
    assert mock_get.call_args_list == [call('api/details/foo')]

@patch('pythonbits.scene._get')
def test_get_details_is_redirected_to_correct_web_page(mock_get):
    mock_get.side_effect = (mock_response(mock_html('<input id="release-name" value="Foo-Bar" />')),
                            mock_response(json.dumps({'name': 'Foo',
                                                      'archived-files': [{'name': 'Foo.png',
                                                                          'size': 123,
                                                                          'crc': '1234ABCD'}]})))
    assert scene.get_details('foo') == ('Foo', {'Foo.png': {'release_name': 'Foo',
                                                            'filename': 'Foo.png',
                                                            'size': 123,
                                                            'crc': '1234ABCD'}})
    assert mock_get.call_args_list == [call('api/details/foo'),
                                       call('api/details/Foo-Bar')]

@patch('pythonbits.scene._get')
def test_get_details_finds_nothing(mock_get):
    mock_get.return_value = mock_response('')
    assert scene.get_details('foo') == ('', {})
    assert mock_get.call_args_list == [call('api/details/foo')]


@patch('pythonbits.scene._get')
def test_search_fails_to_connect(mock_get):
    mock_get.side_effect = scene.APIError()
    guess = {'title': 'Foo Bar Baz'}
    assert scene.search(guess) == []
    assert mock_get.call_args_list == [call('api/search/Foo/Bar/Baz')]

@patch('pythonbits.scene._get')
def test_search_for_movie(mock_get):
    mock_get.return_value = mock_response(
        json.dumps({'results': [{'release': 'The Foo, the Bar and the Bazzy'},
                                {'release': 'Foo Bar goes to Baz'}]}))
    guess = {'title': 'Foo Bar Baz',
             'type': 'movie',
             'year': 2005,
             'release_group': 'TEHFOO'}
    assert scene.search(guess) == ['The Foo, the Bar and the Bazzy',
                                   'Foo Bar goes to Baz']
    assert mock_get.call_args_list == [call('api/search/Foo/Bar/Baz/group:TEHFOO/2005')]

@patch('pythonbits.scene._get')
def test_search_for_episode(mock_get):
    mock_get.return_value = mock_response(
        json.dumps({'results': [{'release': 'The Foo, the Bar and the Bazzy'},
                                {'release': 'Foo Bar goes to Baz'}]}))
    guess = {'title': 'Foo Bar Baz',
             'type': 'episode',
             'season': 3, 'episode': 5,
             'release_group': 'TEHFOO'}
    assert scene.search(guess) == ['The Foo, the Bar and the Bazzy',
                                   'Foo Bar goes to Baz']
    assert mock_get.call_args_list == [call('api/search/Foo/Bar/Baz/group:TEHFOO/S03E05')]

@patch('pythonbits.scene._get')
def test_search_for_season(mock_get):
    mock_get.return_value = mock_response(
        json.dumps({'results': [{'release': 'The Foo, the Bar and the Bazzy'},
                                {'release': 'Foo Bar goes to Baz'}]}))
    guess = {'title': 'Foo Bar Baz',
             'type': 'episode',
             'season': 3,
             'release_group': 'TEHFOO'}
    assert scene.search(guess) == ['The Foo, the Bar and the Bazzy',
                                   'Foo Bar goes to Baz']
    assert mock_get.call_args_list == [call('api/search/Foo/Bar/Baz/group:TEHFOO/S03')]


@patch('pythonbits.scene.get_details')
def test_yield_file_info_for_season_release_of_original_season_release(mock_get_details):
    mock_get_details.return_value = (
        'Foo.S01',
        {'Foo.S01E01.mkv': {'release_name': 'Foo.S01', 'filename': 'Foo.S01E01.mkv', 'size': 123, 'crc': '12345678'},
         'Foo.S01E02.mkv': {'release_name': 'Foo.S01', 'filename': 'Foo.S01E02.mkv', 'size': 234, 'crc': 'ABCD1234'}})
    infos = tuple(scene._yield_file_info('path/to/Foo.S01'))
    assert infos == ({'release_name': 'Foo.S01', 'filename': 'Foo.S01E01.mkv', 'size': 123, 'crc': '12345678'},
                     {'release_name': 'Foo.S01', 'filename': 'Foo.S01E02.mkv', 'size': 234, 'crc': 'ABCD1234'})

@patch('pythonbits.scene.get_details')
def test_yield_file_info_for_episode_release_of_original_episode_release(mock_get_details):
    mock_get_details.return_value = (
        'Foo.S01E01',
        {'Foo.S01E01.mkv': {'release_name': 'Foo.S01E01', 'filename': 'Foo.S01E01.mkv', 'size': 123, 'crc': '12345678'}})
    infos = tuple(scene._yield_file_info('path/to/Foo.S01E01.mkv'))
    assert infos == ({'release_name': 'Foo.S01E01', 'filename': 'Foo.S01E01.mkv', 'size': 123, 'crc': '12345678'},)

@patch('pythonbits.scene._os_listdir')
@patch('pythonbits.scene.get_details')
def test_yield_file_info_for_season_release_of_original_episode_release(mock_get_details, mock_listdir):
    mock_get_details.side_effect = (
        ('', {}),
        ('Foo.S01E01.x264-ABC',
         {'Foo.S01E01.x264-ABC.mkv': {'release_name': 'Foo.S01E01.x264-ABC', 'filename': 'Foo.S01E01.x264-ABC.mkv',
                                 'size': 123, 'crc': '12345678'}}),
        ('Foo.S01E02.x264-ABC',
         {'Foo.S01E02.x264-ABC.mkv': {'release_name': 'Foo.S01E02.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv',
                                 'size': 234, 'crc': 'ABCD1234'}}),
        ('', {}),
    )
    mock_listdir.return_value = ['Foo.S01E01.x264-ABC.mkv', 'Foo.S01E02.x264-ABC.mkv', 'unknown file']
    infos = tuple(scene._yield_file_info('path/to/Foo.S01.x264-ABC'))
    assert infos == ({'release_name': 'Foo.S01E01.x264-ABC', 'filename': 'Foo.S01E01.x264-ABC.mkv', 'size': 123, 'crc': '12345678'},
                     {'release_name': 'Foo.S01E02.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': 234, 'crc': 'ABCD1234'},
                     {'release_name': None, 'filename': 'unknown file', 'size': None, 'crc': None})
    assert mock_listdir.call_args_list == [call('path/to/Foo.S01.x264-ABC')]
    assert mock_get_details.call_args_list == [call('path/to/Foo.S01.x264-ABC'),
                                               call('Foo.S01E01.x264-ABC.mkv'),
                                               call('Foo.S01E02.x264-ABC.mkv'),
                                               call('unknown file')]

@patch('pythonbits.scene._guessit')
@patch('pythonbits.scene.search')
@patch('pythonbits.scene.get_details')
def test_yield_file_info_for_episode_release_of_original_season_release_with_enough_information(
        mock_get_details, mock_search, mock_guessit):
    mock_get_details.side_effect = (
        ('', {}),
        ('Foo.S01.x264-ABC',
         {'Foo.S01E01.x264-ABC.mkv': {'release_name': 'Foo.S01.x264-ABC', 'filename': 'Foo.S01E01.x264-ABC.mkv',
                                 'size': 123, 'crc': '12345678'},
          'Foo.S01E02.x264-ABC.mkv': {'release_name': 'Foo.S01.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv',
                                 'size': 234, 'crc': 'ABCD1234'}})
    )
    mock_guessit.return_value = {'release_group': 'TEHFOO', 'season': 1, 'episode': 2}
    mock_search.return_value = ['Foo.S01.x264-ABC']
    infos = tuple(scene._yield_file_info('path/to/Foo.S01E02.x264-ABC.mkv'))
    assert infos == ({'release_name': 'Foo.S01.x264-ABC', 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': 234, 'crc': 'ABCD1234'},)
    assert mock_get_details.call_args_list == [call('path/to/Foo.S01E02.x264-ABC.mkv'), call('Foo.S01.x264-ABC')]
    assert mock_guessit.called_with('path/to/Foo.S01E02.x264-ABC.mkv')
    assert mock_search.call_args_list == [call({'release_group': 'TEHFOO', 'season': 1})]

@patch('pythonbits.scene._guessit')
@patch('pythonbits.scene.search')
@patch('pythonbits.scene.get_details')
def test_yield_file_info_for_episode_release_of_original_season_release_with_enough_information_no_retry(
        mock_get_details, mock_search, mock_guessit):
    mock_get_details.return_value = ('', {})
    mock_guessit.return_value = {'release_group': 'TEHFOO', 'season': 1}
    infos = tuple(scene._yield_file_info('path/to/Foo.S01E02.x264-ABC.mkv'))
    assert infos == ({'release_name': None, 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': None, 'crc': None},)
    assert mock_get_details.call_args_list == [call('path/to/Foo.S01E02.x264-ABC.mkv')]
    assert mock_guessit.call_args_list == [call('path/to/Foo.S01E02.x264-ABC.mkv')]
    assert mock_search.call_args_list == []

@patch('pythonbits.scene._guessit')
@patch('pythonbits.scene.search')
@patch('pythonbits.scene.get_details')
def test_yield_file_info_for_episode_release_of_original_season_release_with_enough_information_no_search_results(
        mock_get_details, mock_search, mock_guessit):
    mock_get_details.return_value = ('', {})
    mock_guessit.return_value = {'release_group': 'TEHFOO', 'season': 1, 'episode': 2}
    mock_search.return_value = []
    infos = tuple(scene._yield_file_info('path/to/Foo.S01E02.x264-ABC.mkv'))
    assert infos == ({'release_name': None, 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': None, 'crc': None},)
    assert mock_get_details.call_args_list == [call('path/to/Foo.S01E02.x264-ABC.mkv')]
    assert mock_guessit.call_args_list == [call('path/to/Foo.S01E02.x264-ABC.mkv')]
    assert mock_search.call_args_list == [call({'release_group': 'TEHFOO', 'season': 1})]

@patch('pythonbits.scene._guessit')
@patch('pythonbits.scene.search')
@patch('pythonbits.scene.get_details')
def test_yield_file_info_for_episode_release_of_original_season_release_with_enough_information_no_group(
        mock_get_details, mock_search, mock_guessit):
    mock_get_details.return_value = ('', {})
    mock_guessit.return_value = {'season': 1, 'episode': 2}
    mock_search.return_value = []
    infos = tuple(scene._yield_file_info('path/to/Foo.S01E02.x264-ABC.mkv'))
    assert infos == ({'release_name': None, 'filename': 'Foo.S01E02.x264-ABC.mkv', 'size': None, 'crc': None},)
    assert mock_get_details.call_args_list == [call('path/to/Foo.S01E02.x264-ABC.mkv')]
    assert mock_guessit.call_args_list == [call('path/to/Foo.S01E02.x264-ABC.mkv')]
    assert mock_search.call_args_list == []


### Integration tests

# The first item is the release name, all following items are file (name, size) tuples. If
# there is only one item, it's a single-file release. File size of directories is ignored.
scene_releases = (
    # Movie in release name directory
    (('Walk.the.Line.Extended.Cut.2005.1080p.BluRay.x264-HD1080', -1),
     ('Walk.the.Line.Extended.Cut.2005.1080p.BluRay.x264-HD1080/hd1080-wtl.mkv', 11743374939)),

    # Release name is identical to name of only file + extension
    (('12.Rounds.Reloaded.2013.1080p.BluRay.x264-ROVERS.mkv', 7037061105),),

    # Release name is identical to name of only file + extension in lower case
    (('side.effects.2013.720p.bluray.x264-sparks.mkv', 4690527189),),

    # Same as above but in directory with proper release name
    (('Side.Effects.2013.720p.BluRay.x264-SPARKS', -1),
     ('Side.Effects.2013.720p.BluRay.x264-SPARKS/side.effects.2013.720p.bluray.x264-sparks.mkv', 4690527189),),

    # Single episode release
    (('Fawlty.Towers.S01E01.1080p.BluRay.x264-SHORTBREHD.mkv', 2342662389),),

    # Season pack of single episode releases
    (('Fawlty.Towers.S01.1080p.BluRay.x264-SHORTBREHD', -1),
     ('Fawlty.Towers.S01.1080p.BluRay.x264-SHORTBREHD/Fawlty.Towers.S01E01.1080p.BluRay.x264-SHORTBREHD.mkv', 2342662389),
     ('Fawlty.Towers.S01.1080p.BluRay.x264-SHORTBREHD/Fawlty.Towers.S01E02.1080p.BluRay.x264-SHORTBREHD.mkv', 2342806335),
     ('Fawlty.Towers.S01.1080p.BluRay.x264-SHORTBREHD/Fawlty.Towers.S01E03.1080p.BluRay.x264-SHORTBREHD.mkv', 2838653040),
     ('Fawlty.Towers.S01.1080p.BluRay.x264-SHORTBREHD/Fawlty.Towers.S01E04.1080p.BluRay.x264-SHORTBREHD.mkv', 2343647191),
     ('Fawlty.Towers.S01.1080p.BluRay.x264-SHORTBREHD/Fawlty.Towers.S01E05.1080p.BluRay.x264-SHORTBREHD.mkv', 2342958161),
     ('Fawlty.Towers.S01.1080p.BluRay.x264-SHORTBREHD/Fawlty.Towers.S01E06.1080p.BluRay.x264-SHORTBREHD.mkv', 2342527200)),

    # Season pack release
    (('Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT', -1),
     ('Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01.Jonathan.Amess.Brooklyn.720p.BluRay.x264-iNGOT.mkv', 518652629),
     ('Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01.Making.of.720p.BluRay.x264-iNGOT.mkv', 779447228),
     ('Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01E03.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv', 30779540),
     ('Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01E04.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv', 138052914),
     ('Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01E08.Deleted.Scene.1.720p.BluRay.x264-iNGOT.mkv', 68498554),
     ('Bored.to.Death.S01.EXTRAS.720p.BluRay.x264-iNGOT/Bored.to.Death.S01E08.Deleted.Scene.2.720p.BluRay.x264-iNGOT.mkv', 45583011)),

    # Single episode from season pack release
    (('Bored.to.Death.S01E03.Deleted.Scene.720p.BluRay.x264-iNGOT.mkv', 30779540),),
)

non_scene_releases = (
    ('Rampart.2011.1080p.Bluray.DD5.1.x264-DON.mkv', 123),
    ('La.Bamba.1987.LE.Bluray.1080p.DTS-HD.x264-Grym.mkv', 123),
    ('Damnation.S01.720p.AMZN.WEB-DL.DDP5.1.H.264-AJP69', 123),
    ('Damnation.S01E03.One.Penny.720p.AMZN.WEB-DL.DD+5.1.H.264-AJP69.mkv', 123),
    ('The Film Without a Group (1984).mkv', 123),
)

capture_requests = False
real_scene_get = scene._get
capture_dir = os.path.join(os.path.dirname(__file__), 'scene_responses')

def capture_request(path):
    filepath = os.path.join(capture_dir, path.replace('/', '_') + '.pickle')
    if not capture_requests and os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            return pickle.loads(f.read())
    else:
        response = real_scene_get(path)
        if not os.path.exists(capture_dir):
            os.mkdir(capture_dir)
        with open(filepath, 'wb') as f:
            f.write(pickle.dumps(response))
        return response

@contextlib.contextmanager
def mock_files(*filespecs, path_prefix=''):
    def mock_exists(path):
        for path_,size in filespecs:
            if os.path.join(path_prefix, path_) == path:
                return True
        return False

    def mock_getsize(path):
        for path_,size in filespecs:
            if os.path.join(path_prefix, path_) == path:
                return size
        raise FileNotFoundError(path)

    exists_p = patch('pythonbits.scene._path_exists', mock_exists)
    filesize_p = patch('pythonbits.scene._path_getsize', mock_getsize)
    exists_p.start()
    filesize_p.start()
    yield
    exists_p.stop()
    filesize_p.stop()

@pytest.mark.parametrize('content', scene_releases, ids=(fs[0][0] for fs in scene_releases))
@patch('pythonbits.scene._get', capture_request)
@patch('pythonbits.bb.prompt_yesno')
@patch('pythonbits.scene._os_listdir')
def test_detection_of_unmodified_scene_release(mock_listdir, mock_prompt_yesno, content):
    release_name = content[0][0]
    mock_listdir.return_value = [os.path.basename(fs[0]) for fs in content[1:]]
    s = bb.VideoSubmission(path='path/to/' + release_name)
    with mock_files(*content, path_prefix='path/to'):
        assert s['scene'] is True
    assert mock_prompt_yesno.call_args_list == []

@pytest.mark.parametrize('content', scene_releases, ids=(fs[0][0] for fs in scene_releases))
@patch('pythonbits.scene._get', capture_request)
@patch('sys.exit')
@patch('pythonbits.bb.prompt_yesno')
@patch('pythonbits.scene._os_listdir')
def test_detection_of_scene_release_with_wrong_file_size(mock_listdir, mock_prompt_yesno, mock_exit, content):
    mock_prompt_yesno.return_value = False
    mock_exit.return_value = '<some exit code>'
    mock_listdir.return_value = [os.path.basename(fs[0]) for fs in content[1:]]
    release_name = content[0][0]
    modified_content = ((relpath, size-1) for relpath,size in content)
    with mock_files(*modified_content, path_prefix='path/to'):
        # User wants to abort
        mock_prompt_yesno.side_effect = (True,)
        assert bb.VideoSubmission(path='path/to/' + release_name)['scene'] is '<some exit code>'
        assert mock_prompt_yesno.call_args_list == [call('Abort?', default=True)]
        assert mock_exit.call_args_list == [call(1)]
        mock_prompt_yesno.reset_mock()
        mock_exit.reset_mock()

        # User wants to submit anyway but not as scene
        mock_prompt_yesno.side_effect = (False, False)
        assert bb.VideoSubmission(path='path/to/' + release_name)['scene'] is False
        assert mock_prompt_yesno.call_args_list == [call('Abort?', default=True),
                                                    call('Is this a scene release?', default=False)]
        assert mock_exit.call_args_list == []
        mock_prompt_yesno.reset_mock()
        mock_exit.reset_mock()

        # User wants to submit anyway and insists on scene release
        mock_prompt_yesno.side_effect = (False, True)
        assert bb.VideoSubmission(path='path/to/' + release_name)['scene'] is True
        assert mock_prompt_yesno.call_args_list == [call('Abort?', default=True),
                                                    call('Is this a scene release?', default=False)]
        assert mock_exit.call_args_list == []

@pytest.mark.parametrize('content', scene_releases, ids=(fs[0][0] for fs in scene_releases))
@patch('pythonbits.scene._get', capture_request)
@patch('sys.exit')
@patch('pythonbits.bb.prompt_yesno')
@patch('pythonbits.scene._os_listdir')
def test_detection_of_scene_release_with_wrong_release_name(mock_listdir, mock_prompt_yesno, mock_exit, content):
    mock_prompt_yesno.return_value = False
    mock_exit.return_value = '<some exit code>'
    mock_listdir.return_value = [os.path.basename(fs[0]) for fs in content[1:]]
    correct_release_name = content[0][0]
    wrong_release_name = correct_release_name.lower().replace('.', ' ', 1)
    with mock_files(*content, path_prefix='path/to'):
        # User wants to abort
        mock_prompt_yesno.side_effect = (True,)
        assert bb.VideoSubmission(path='path/to/' + wrong_release_name)['scene'] is '<some exit code>'
        assert mock_prompt_yesno.call_args_list == [call('Abort?', default=True)]
        assert mock_exit.call_args_list == [call(1)]
        mock_prompt_yesno.reset_mock()
        mock_exit.reset_mock()

        # User wants to submit anyway but not as scene
        mock_prompt_yesno.side_effect = (False, False)
        assert bb.VideoSubmission(path='path/to/' + wrong_release_name)['scene'] is False
        assert mock_prompt_yesno.call_args_list == [call('Abort?', default=True),
                                                    call('Is this a scene release?', default=False)]
        assert mock_exit.call_args_list == []
        mock_prompt_yesno.reset_mock()
        mock_exit.reset_mock()

        # User wants to submit anyway and insists on scene release
        mock_prompt_yesno.side_effect = (False, True)
        assert bb.VideoSubmission(path='path/to/' + wrong_release_name)['scene'] is True
        assert mock_prompt_yesno.call_args_list == [call('Abort?', default=True),
                                                    call('Is this a scene release?', default=False)]
        assert mock_exit.call_args_list == []

@pytest.mark.parametrize('content', non_scene_releases, ids=(fs[0] for fs in non_scene_releases))
@patch('pythonbits.scene._get', capture_request)
@patch('sys.exit')
@patch('pythonbits.bb.prompt_yesno')
@patch('pythonbits.scene._os_listdir')
def test_detection_of_non_scene_release(mock_listdir, mock_prompt_yesno, mock_exit, content):
    release_name = content[0]
    s = bb.VideoSubmission(path='path/to/' + release_name)
    with mock_files(*content, path_prefix='path/to'):
        assert s['scene'] is False
    assert mock_prompt_yesno.call_args_list == []

@patch('pythonbits.scene._get', capture_request)
@patch('sys.exit')
@patch('pythonbits.bb.prompt_yesno')
def test_workaround_for_group_in_front(mock_prompt_yesno, mock_exit):
    mock_prompt_yesno.return_value = False
    mock_exit.return_value = '<some exit code>'
    correct_release_name = 'The.Omega.Man.1971.1080p.BluRay.x264-VOA'
    wrong_release_name = 'voa-the_omega_man_x264_bluray.mkv'
    with mock_files((wrong_release_name, 123), path_prefix='path/to'):
        mock_prompt_yesno.side_effect = (True,)
        assert bb.VideoSubmission(path='path/to/' + wrong_release_name)['scene'] is '<some exit code>'
        assert mock_prompt_yesno.call_args_list == [call('Abort?', default=True)]
        assert mock_exit.call_args_list == [call(1)]
