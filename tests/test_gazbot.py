# -*- coding: utf-8 -*-
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gazbot import sanitize_html, safe_join, parse_from_address, parse_addresses


# --- sanitize_html -------------------------------------------------------

def test_sanitize_removes_script_and_content():
    out = sanitize_html('<script>fetch("file:///etc/passwd")</script>Hello')
    assert 'script' not in out.lower()
    assert 'fetch' not in out
    assert 'Hello' in out


def test_sanitize_strips_event_handlers():
    out = sanitize_html('<img src=x onerror="alert(1)">')
    assert 'onerror' not in out.lower()


@pytest.mark.parametrize('scheme', ['javascript', 'vbscript', 'file', 'data'])
def test_sanitize_neutralises_dangerous_schemes(scheme):
    out = sanitize_html('<a href="{}:evil">x</a>'.format(scheme))
    assert scheme + ':' not in out.lower()
    assert 'blocked:' in out


def test_sanitize_removes_iframe_and_meta():
    out = sanitize_html('<iframe src="http://evil"></iframe><meta charset="iso-8859-1">ok')
    assert 'iframe' not in out.lower()
    assert 'meta' not in out.lower()
    assert 'ok' in out


def test_sanitize_preserves_ordinary_markup():
    src = '<b>bonjour</b> <a href="https://ok.com">lien</a> <img src="cid:logo">'
    out = sanitize_html(src)
    assert '<b>bonjour</b>' in out
    assert 'https://ok.com' in out
    assert 'cid:logo' in out


def test_sanitize_handles_empty():
    assert sanitize_html('') == ''
    assert sanitize_html(None) is None


# --- safe_join -----------------------------------------------------------

def test_safe_join_normal_filename(tmp_path):
    result = safe_join(str(tmp_path), 'photo.jpg')
    assert result == os.path.join(str(tmp_path), 'photo.jpg')


def test_safe_join_strips_directories(tmp_path):
    # A path with separators is reduced to its basename, staying inside dir.
    result = safe_join(str(tmp_path), '../../etc/passwd')
    assert result == os.path.join(str(tmp_path), 'passwd')


def test_safe_join_absolute_path(tmp_path):
    result = safe_join(str(tmp_path), '/etc/passwd')
    assert result == os.path.join(str(tmp_path), 'passwd')


@pytest.mark.parametrize('bad', ['', '.', '..', '/', None])
def test_safe_join_rejects_empty_or_dots(tmp_path, bad):
    assert safe_join(str(tmp_path), bad) is None


# --- parse_from_address --------------------------------------------------

def test_parse_from_display_name():
    assert parse_from_address('Alice <ALICE@Example.com>') == 'alice@example.com'


def test_parse_from_bare_address():
    assert parse_from_address('bob@example.com') == 'bob@example.com'


def test_parse_from_encoded_word():
    # RFC2047-encoded display name must not break address extraction.
    raw = '=?utf-8?q?Ren=C3=A9?= <rene@example.com>'
    assert parse_from_address(raw) == 'rene@example.com'


def test_parse_from_empty():
    assert parse_from_address('') == ''


# --- parse_addresses -----------------------------------------------------

def test_parse_addresses_basic():
    lines = ['alice@example.com,alice.work@example.com:Alice', 'bob@example.com:Bob']
    result = parse_addresses(lines)
    assert result == {
        'Alice': ['alice@example.com', 'alice.work@example.com'],
        'Bob': ['bob@example.com'],
    }


def test_parse_addresses_ignores_blank_and_malformed():
    lines = ['', '   ', 'no-separator-here', 'carol@example.com:Carol']
    result = parse_addresses(lines)
    assert result == {'Carol': ['carol@example.com']}


def test_parse_addresses_name_with_colon_uses_last_separator():
    # rsplit means a ':' inside addresses side is fine; name is the final field.
    result = parse_addresses(['a@x.com:Group A'])
    assert result == {'Group A': ['a@x.com']}
