import pythonbits.submission as submission
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
    s = submission.VideoSubmission(path=path, title_arg=title)
    assert s['tv_specifier'] == specifier
