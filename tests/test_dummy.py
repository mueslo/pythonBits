import pytest
import pythonbits.submission as submission

def test_bare_object_creation():
    s = submission.Submission()
    with pytest.raises(submission.SubmissionAttributeError):
        s['nonexistent_attribute']
