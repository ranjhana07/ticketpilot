from ticketpilot.triage.sentiment import score_text


def test_angry_message_is_negative_and_urgent():
    result = score_text("This is unacceptable! Production is down and we are blocked, fix it NOW!!")
    assert result.label == "negative"
    assert result.urgency > 0.6


def test_polite_message_is_positive_with_low_urgency():
    result = score_text("Thanks so much, the new board view is great. No rush on the feature idea.")
    assert result.label == "positive"
    assert result.urgency < 0.2


def test_negation_flips_positive_words():
    assert score_text("this is not great").score < 0


def test_neutral_question():
    result = score_text("What are your support hours?")
    assert result.label == "neutral"
    assert result.urgency == 0.0


def test_scores_are_bounded():
    result = score_text("terrible awful worst scam stolen " * 20)
    assert -1.0 <= result.score <= 1.0
