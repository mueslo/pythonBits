# -*- coding: utf-8 -*-
import pythonbits.submission as submission
import pythonbits.bb as bb
import pytest


def test_attribute_logic():
    s = submission.Submission(fieldname='somevalue', title='overrides_render')
    with pytest.raises(submission.SubmissionAttributeError):
        s['nonexistent_attribute']

    assert s['fieldname'] == 'somevalue'
    assert s['title'] == 'overrides_render'


# title, path, correct_specifier
tv_names = [(None, 'some.series.s02e11.avi', ('some series', 2, 11)),
            (None, 'another series s04e02.mkv', ('another series', 4, 2)),
            (None, 'A.Series.S10.BluRay', ('A Series', 10, None)),
            (None, 'different.format.4x12.WEB-DL.DTS.MUESLo.mkv',
             ('different format', 4, 12)),
            ("Yet Another Video Submission", 'yavs.s04e03.mkv',
             ("Yet Another Video Submission", 4, 3)),
            ("Firefly S02", 'Firefly.S01E03.mkv', ("Firefly", 2, None)),
            ('Ramen Brothers Season 4', None, ('Ramen Brothers', 4, None)),
            ('Ramen Brothers S04', None, ('Ramen Brothers', 4, None)),
            ('Ramen Brothers 4', "filename", None),
            ('Ramen Brothers 4', "rb.s01e02.avi", ('Ramen Brothers 4', 1, 2)),
            ]


@pytest.mark.parametrize("title,path,specifier", tv_names)
def test_tv_specifier(title, path, specifier):
    s = bb.VideoSubmission(path=path, title_arg=title)
    assert s['tv_specifier'] == specifier


def test_proper():
    tracks = {'general': "",
              'video': "",
              'audio': "",
              'text': ["sub", "title"]}

    s = bb.VideoSubmission(
        path=("Some.Awesome.Show.S26E12.REPACK."
              "With.A.Show.Title.720p.WEB-DL.AAC2.0.H.264-pontifex.mkv"),
        title_arg=None,
        scene=True,
        tracks=tracks)

    assert s['additional'][0] == 'PROPER'


normalise_pairs = [
    (u"Basic Feature", "basic.feature"),
    (u"Name O'Comment-Doublename", "name.o.comment.doublename"),
    (u"François and Влади́мир like Ümläutß",
     "francois.and.vladimir.like.umlautss"),
    (u"Blarb Børgen Ålpotef", "blarb.borgen.alpotef"),
]


@pytest.mark.parametrize("input, correct", normalise_pairs)
def test_normalise_tags(input, correct):
    assert bb.format_tag(input) == correct
