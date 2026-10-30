"""Spoken replies in Punjabi and English for Vaari Voice Booking (Step V3).

All Punjabi text is marked with TODO(punjabi-review) for native speaker verification.
Each reply includes both Punjabi and simple English text alongside audio metadata.
"""

from typing import Any, Dict

REPLIES: Dict[str, Dict[str, str]] = {
    "greeting": {
        "pa": "ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ ਜੀ, ਮੈਂ ਵਾਰੀ ਦਾ ਆਟੋਮੇਟਿਡ ਬੁਕਿੰਗ ਸਿਸਟਮ ਹਾਂ। ਮੈਂ ਤੁਹਾਡੀ ਮਸ਼ੀਨ ਬੁੱਕ ਕਰਨ ਵਿੱਚ ਮਦਦ ਕਰਾਂਗਾ।",  # TODO(punjabi-review): native speaker check
        "en": "Sat Sri Akal, I am Vaari's automated booking assistant. I will help you book your farm equipment.",
    },
    "consent": {
        "pa": "ਤੁਹਾਡੀ ਆਵਾਜ਼ ਇਸ ਕੰਪਿਊਟਰ 'ਤੇ ਲਿਖਤ ਵਿੱਚ ਬਦਲੀ ਜਾਵੇਗੀ ਅਤੇ ਫਿਰ ਮਿਟਾ ਦਿੱਤੀ ਜਾਵੇਗੀ। ਅਸੀਂ ਸਿਰਫ਼ ਤੁਹਾਡੇ ਬੁਕਿੰਗ ਵੇਰਵੇ ਰੱਖਾਂਗੇ।",  # TODO(punjabi-review): native speaker check
        "en": "Your voice is converted to text on this computer and then deleted; we only keep the booking details.",
    },
    "ask_phone": {
        "pa": "ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ ਦਸ ਅੰਕਾਂ ਦਾ ਮੋਬਾਈਲ ਨੰਬਰ ਦੱਸੋ ਜੀ।",  # TODO(punjabi-review): native speaker check
        "en": "Please tell me your 10-digit mobile phone number.",
    },
    "ask_village": {
        "pa": "ਤੁਹਾਡੇ ਪਿੰਡ ਦਾ ਕੀ ਨਾਮ ਹੈ ਜੀ?",  # TODO(punjabi-review): native speaker check
        "en": "What is the name of your village?",
    },
    "ask_acres": {
        "pa": "ਤੁਹਾਡੇ ਕੋਲ ਵਾਹੁਣ ਜਾਂ ਕਟਾਈ ਲਈ ਕਿੰਨੇ ਏਕੜ ਜ਼ਮੀਨ ਹੈ ਜੀ?",  # TODO(punjabi-review): native speaker check
        "en": "How many acres of land do you need the machine for?",
    },
    "ask_machine": {
        "pa": "ਤੁਹਾਨੂੰ ਕਿਹੜੀ ਮਸ਼ੀਨ ਚਾਹੀਦੀ ਹੈ, ਜਿਵੇਂ ਸੁਪਰ ਸੀਡਰ ਜਾਂ ਹੈਪੀ ਸੀਡਰ?",  # TODO(punjabi-review): native speaker check
        "en": "Which machine do you need, such as Super Seeder or Happy Seeder?",
    },
    "ask_harvest_date": {
        "pa": "ਤੁਹਾਨੂੰ ਮਸ਼ੀਨ ਕਿਸ ਤਾਰੀਖ਼ ਨੂੰ ਚਾਹੀਦੀ ਹੈ ਜਾਂ ਤੁਹਾਡੀ ਫ਼ਸਲ ਕਦੋਂ ਤੱਕ ਕੱਟੀ ਜਾਵੇਗੀ?",  # TODO(punjabi-review): native speaker check
        "en": "On what date do you need the machine, or when will your harvest be ready?",
    },
    "did_not_understand": {
        "pa": "ਮਾਫ਼ ਕਰਨਾ ਜੀ, ਮੈਂ ਠੀਕ ਤਰ੍ਹਾਂ ਸਮਝ ਨਹੀਂ ਸਕਿਆ। ਕਿਰਪਾ ਕਰਕੇ ਦੁਬਾਰਾ ਬੋਲੋ ਜੀ।",  # TODO(punjabi-review): native speaker check
        "en": "Sorry, I could not understand that clearly. Please speak again.",
    },
    "summary_intro": {
        "pa": "ਮੈਂ ਤੁਹਾਡੀ ਬੁਕਿੰਗ ਦੀਆਂ ਵਿਸ਼ੇਸ਼ਤਾਵਾਂ ਸਕਰੀਨ 'ਤੇ ਦਿਖਾ ਰਿਹਾ ਹਾਂ, ਕਿਰਪਾ ਕਰਕੇ ਜਾਂਚੋ।",  # TODO(punjabi-review): native speaker check
        "en": "I am showing your booking details on the screen, please check them.",
    },
    "ask_confirm": {
        "pa": "ਕੀ ਇਹ ਸਾਰੇ ਵੇਰਵੇ ਸਹੀ ਹਨ? ਕਿਰਪਾ ਕਰਕੇ ਹਾਂ ਜਾਂ ਨਹੀਂ ਕਹੋ।",  # TODO(punjabi-review): native speaker check
        "en": "Are all these details correct? Please say yes or no.",
    },
    "confirmed_with_date": {
        "pa": "ਧੰਨਵਾਦ ਜੀ! ਤੁਹਾਡੀ ਬੁਕਿੰਗ ਪੱਕੀ ਹੋ ਗਈ ਹੈ। ਮਸ਼ੀਨ ਤੁਹਾਡੇ ਦਿੱਤੇ ਸਮੇਂ ਅਨੁਸਾਰ ਆਵੇਗੀ।",  # TODO(punjabi-review): native speaker check
        "en": "Thank you! Your booking is confirmed. The machine is scheduled to arrive on your requested date.",
    },
    "confirmed_needs_info": {
        "pa": "ਤੁਹਾਡੀ ਬੇਨਤੀ ਦਰਜ ਕਰ ਲਈ ਗਈ ਹੈ। ਕੇਂਦਰ ਦਾ ਕਰਮਚਾਰੀ ਤੁਹਾਨੂੰ ਫ਼ੋਨ ਕਰਕੇ ਬਾਕੀ ਵੇਰਵੇ ਲਵੇਗਾ।",  # TODO(punjabi-review): native speaker check
        "en": "Your request has been registered. The custom hiring centre will call you to finalize the remaining details.",
    },
    "no_slot_will_miss": {
        "pa": "ਅਫ਼ਸੋਸ ਹੈ ਜੀ, ਉਸ ਸਮੇਂ ਲਈ ਕੋਈ ਮਸ਼ੀਨ ਉਪਲਬਧ ਨਹੀਂ ਹੈ। ਅਸੀਂ ਤੁਹਾਨੂੰ ਉਡੀਕ ਸੂਚੀ ਵਿੱਚ ਰੱਖ ਲਿਆ ਹੈ ਅਤੇ ਜਲਦੀ ਸੰਪਰਕ ਕਰਾਂਗੇ।",  # TODO(punjabi-review): native speaker check
        "en": "We regret that no machine slot is available for that date. We have recorded your request and the centre will contact you.",
    },
    "cancelled": {
        "pa": "ਠੀਕ ਹੈ ਜੀ, ਇਹ ਬੁਕਿੰਗ ਰੱਦ ਕਰ ਦਿੱਤੀ ਗਈ ਹੈ।",  # TODO(punjabi-review): native speaker check
        "en": "Understood, this booking has been cancelled.",
    },
    "will_call_you": {
        "pa": "ਕੋਈ ਗੱਲ ਨਹੀਂ ਜੀ, ਸਾਡਾ ਕੇਂਦਰ ਤੁਹਾਨੂੰ ਜਲਦੀ ਹੀ ਫ਼ੋਨ ਕਰੇਗਾ।",  # TODO(punjabi-review): native speaker check
        "en": "No worries, our custom hiring centre will call you shortly.",
    },
    "service_down": {
        "pa": "ਆਵਾਜ਼ ਸੇਵਾ ਫਿਲਹਾਲ ਉਪਲਬਧ ਨਹੀਂ ਹੈ, ਕਿਰਪਾ ਕਰਕੇ ਫ਼ਾਰਮ ਭਰ ਕੇ ਬੁੱਕ ਕਰੋ।",  # TODO(punjabi-review): native speaker check
        "en": "Voice service is currently unavailable. Please use the form to type your booking instead.",
    },
}


def get_reply(key: str) -> Dict[str, Any]:
    """Retrieve text and metadata for a prompt key."""
    if key not in REPLIES:
        return {
            "key": key,
            "text_pa": "",
            "text_en": "",
            "audio_url": f"/api/voice/reply/{key}.wav",
        }
    item = REPLIES[key]
    return {
        "key": key,
        "text_pa": item["pa"],
        "text_en": item["en"],
        "audio_url": f"/api/voice/reply/{key}.wav",
    }
