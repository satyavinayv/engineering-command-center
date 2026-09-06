from app.services.reviewer_detection import classify_comment

MR = {
    "author": {"username": "alice"},
    "reviewers": [{"username": "bob"}, {"username": "carol"}],
}


def test_system_comment():
    note = {"system": True, "author": {"username": "bob"}}
    assert classify_comment(note, MR) == "SYSTEM_COMMENT"


def test_author_comment():
    note = {"system": False, "author": {"username": "alice"}}
    assert classify_comment(note, MR) == "AUTHOR_COMMENT"


def test_reviewer_comment():
    note = {"system": False, "author": {"username": "bob"}}
    assert classify_comment(note, MR) == "REVIEWER_COMMENT"


def test_general_comment_from_uninvolved_user():
    note = {"system": False, "author": {"username": "dave"}}
    assert classify_comment(note, MR) == "GENERAL_COMMENT"


def test_bot_comment_by_bot_flag():
    note = {"system": False, "author": {"username": "ci-runner", "bot": True}}
    assert classify_comment(note, MR) == "BOT_COMMENT"


def test_bot_comment_by_username_heuristic():
    note = {"system": False, "author": {"username": "dependabot"}}
    assert classify_comment(note, MR) == "BOT_COMMENT"


def test_reviewer_takes_precedence_over_general_when_also_a_reviewer():
    note = {"system": False, "author": {"username": "carol"}}
    assert classify_comment(note, MR) == "REVIEWER_COMMENT"
