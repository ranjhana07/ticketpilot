from ticketpilot.triage.language import detect_language


def test_english():
    assert detect_language("Please refund the charge on my order, it was a mistake").language == "en"


def test_spanish():
    assert detect_language("No puedo iniciar sesión y no me llega el correo para restablecer la contraseña").language == "es"


def test_french():
    assert detect_language("Je voudrais résilier mon abonnement avant le prochain renouvellement").language == "fr"


def test_german():
    assert detect_language("Ich möchte mein Abonnement vor der nächsten Verlängerung kündigen").language == "de"


def test_empty_text_falls_back_to_default():
    result = detect_language("1234 !!!")
    assert result.language == "en" and result.confidence == 0.0
