"""The voice script: every clip the voice booking flow can play.

One clip = one id + the exact sentence spoken for it, in Punjabi, Hindi and
English. The generator (`scripts/make_voice_clips.py`) turns this list into
audio files under `web/public/audio/<pa|hi|en>/`, and the engine (`app/voice/understand.py`) answers
with lists of these ids, so the two can never drift apart.

Clip id rules (the frontend relies on them):
  prompt/<key>        fixed sentences (questions, retries, outcomes)
  digit/<0-9>         single digits, for reading back a phone number
  village/<slug>      a village name
  machine/<service>   a machine name
  acres/<x100>        an acreage, e.g. acres/550 = "ਸਾਢੇ ਪੰਜ ਏਕੜ"
  date/<MM-DD>        a calendar date, e.g. date/11-15 = "ਪੰਦਰਾਂ ਨਵੰਬਰ"
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.voice.lexicon import (
    MACHINE_NAMES_HI,
    MACHINES,
    MONTH_WORDS,
    MONTHS_HI,
    NUMBER_WORDS,
    NUMBER_WORDS_HI,
    VILLAGES_PA,
    VillageEntry,
    guru_to_deva,
)

# key -> (Punjabi, English). The Punjabi line is what the voice says.
# Written as one breath each: few commas, so the voice does not pause mid-line.
PROMPTS: dict[str, tuple[str, str]] = {
    "welcome": (
        "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ! ਵਾਰੀ ਵਿੱਚ ਤੁਹਾਡਾ ਸਵਾਗਤ ਹੈ। ਬੱਸ ਪੰਜ ਸਵਾਲਾਂ ਵਿੱਚ ਤੁਹਾਡੀ ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ ਬੁੱਕ ਹੋ ਜਾਵੇਗੀ।",
        "Sat Sri Akal! Welcome to Vaari. Five quick questions and your machine turn is booked.",
    ),
    # Questions, one per step.
    "ask_phone": (
        "ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ ਦਸ ਅੰਕਾਂ ਦਾ ਮੋਬਾਈਲ ਨੰਬਰ ਦੱਸੋ ਜੀ।",
        "Please tell me your 10-digit mobile number.",
    ),
    "ask_village": (
        "ਤੁਹਾਡਾ ਖੇਤ ਕਿਹੜੇ ਪਿੰਡ ਵਿੱਚ ਹੈ ਜੀ? ਪਿੰਡ ਦਾ ਨਾਂ ਦੱਸੋ।",
        "Which village is your field in? Say the village name.",
    ),
    "ask_acres": (
        "ਕਿੰਨੇ ਏਕੜ ਵਿੱਚ ਕੰਮ ਕਰਵਾਉਣਾ ਹੈ ਜੀ? ਜਿਵੇਂ ਪੰਜ ਏਕੜ ਜਾਂ ਸਾਢੇ ਤਿੰਨ ਏਕੜ।",
        "How many acres need the machine? For example 5 acres or 3 and a half acres.",
    ),
    "ask_machine": (
        "ਤੁਹਾਨੂੰ ਕਿਹੜੀ ਮਸ਼ੀਨ ਚਾਹੀਦੀ ਹੈ ਜੀ? ਸੁਪਰ ਸੀਡਰ ਹੈਪੀ ਸੀਡਰ ਬੇਲਰ ਜਾਂ ਮਲਚਰ?",
        "Which machine do you need? Super Seeder, Happy Seeder, Baler or Mulcher?",
    ),
    "ask_date": (
        "ਝੋਨੇ ਦੀ ਕਟਾਈ ਕਦੋਂ ਹੋਈ ਹੈ ਜਾਂ ਕਦੋਂ ਹੋਣੀ ਹੈ ਜੀ? ਜਿਵੇਂ ਅੱਜ ਕੱਲ੍ਹ ਜਾਂ ਪੰਦਰਾਂ ਨਵੰਬਰ। ਜੇ ਪਤਾ ਨਹੀਂ ਤਾਂ ਕਹੋ ਪਤਾ ਨਹੀਂ।",
        "When was or when will the paddy be harvested? For example today, tomorrow or 15 November. If you don't know, say 'don't know'.",
    ),
    "ask_consent": (
        "ਤੁਹਾਡਾ ਨੰਬਰ ਤੇ ਖੇਤ ਦੀ ਜਾਣਕਾਰੀ ਸਿਰਫ਼ ਮਸ਼ੀਨ ਦੀ ਵਾਰੀ ਅਤੇ ਕੰਮ ਦੇ ਰਿਕਾਰਡ ਲਈ ਵਰਤੀ ਜਾਵੇਗੀ। ਕੀ ਬੁਕਿੰਗ ਪੱਕੀ ਕਰ ਦੇਈਏ ਜੀ?",
        "Your number and field details are used only for the machine turn and the work record. Shall we confirm the booking?",
    ),
    # Read-back pieces.
    "rb_phone": ("ਤੁਹਾਡਾ ਨੰਬਰ ਹੈ", "Your number is"),
    "confirm_q": ("ਕੀ ਇਹ ਠੀਕ ਹੈ ਜੀ?", "Is this correct?"),
    "rel_today": ("ਅੱਜ", "Today"),
    "rel_yesterday": ("ਬੀਤਿਆ ਕੱਲ੍ਹ", "Yesterday"),
    "rel_tomorrow": ("ਆਉਣ ਵਾਲਾ ਕੱਲ੍ਹ", "Tomorrow"),
    "date_not_yet": ("ਕਟਾਈ ਦੀ ਤਾਰੀਖ਼ ਹਾਲੇ ਪੱਕੀ ਨਹੀਂ।", "Harvest date not fixed yet."),
    "frac_sava": ("ਸਵਾ", "and a quarter"),
    "frac_saadhe": ("ਸਾਢੇ", "and a half"),
    "frac_paune": ("ਪੌਣੇ", "less a quarter"),
    "and_quarter": ("ਅਤੇ ਚੌਥਾਈ", "and a quarter"),
    "and_half": ("ਅਤੇ ਅੱਧਾ", "and a half"),
    "and_three_quarters": ("ਅਤੇ ਪੌਣਾ", "and three quarters"),
    "about": ("ਲਗਭਗ", "about"),
    "ok_next": ("ਠੀਕ ਹੈ ਜੀ।", "Okay."),
    # Retries.
    "retry_generic": ("ਮਾਫ਼ ਕਰਨਾ ਜੀ ਗੱਲ ਸਮਝ ਨਹੀਂ ਆਈ। ਇੱਕ ਵਾਰ ਫਿਰ ਬੋਲੋ ਜੀ।", "Sorry, I did not get that. Please say it again."),
    "no_speech": ("ਕੋਈ ਆਵਾਜ਼ ਨਹੀਂ ਆਈ ਜੀ। ਮਾਈਕ ਦਬਾ ਕੇ ਫਿਰ ਬੋਲੋ।", "I heard nothing. Tap the mic and speak again."),
    "phone_short": ("ਨੰਬਰ ਪੂਰਾ ਨਹੀਂ ਆਇਆ ਜੀ। ਦਸੇ ਅੰਕ ਹੌਲੀ ਹੌਲੀ ਦੁਬਾਰਾ ਬੋਲੋ।", "The number is incomplete. Say all ten digits slowly."),
    "phone_continue": ("ਠੀਕ ਹੈ ਜੀ। ਹੁਣ ਬਾਕੀ ਅੰਕ ਬੋਲੋ।", "Okay. Now say the remaining digits."),
    "phone_long": ("ਨੰਬਰ ਵਿੱਚ ਦਸ ਤੋਂ ਵੱਧ ਅੰਕ ਆ ਗਏ ਜੀ। ਸਿਰਫ਼ ਦਸ ਅੰਕ ਦੁਬਾਰਾ ਬੋਲੋ।", "That has more than ten digits. Say just the ten digits again."),
    "phone_start": ("ਮੋਬਾਈਲ ਨੰਬਰ ਛੇ ਸੱਤ ਅੱਠ ਜਾਂ ਨੌਂ ਨਾਲ ਸ਼ੁਰੂ ਹੁੰਦਾ ਹੈ ਜੀ। ਨੰਬਰ ਦੁਬਾਰਾ ਬੋਲੋ।", "A mobile number starts with 6, 7, 8 or 9. Say it again."),
    "village_unknown": ("ਇਹ ਪਿੰਡ ਸੂਚੀ ਵਿੱਚ ਨਹੀਂ ਮਿਲਿਆ ਜੀ। ਨਾਂ ਦੁਬਾਰਾ ਬੋਲੋ ਜਾਂ ਹੇਠਾਂ ਸੂਚੀ ਵਿੱਚੋਂ ਚੁਣੋ।", "That village is not on the list. Say it again or pick from the list below."),
    "acres_unknown": ("ਏਕੜ ਸਮਝ ਨਹੀਂ ਆਏ ਜੀ। ਜਿਵੇਂ ਬੋਲੋ ਪੰਜ ਏਕੜ।", "I did not get the acres. Say, for example, 5 acres."),
    "acres_range": ("ਏਕੜ ਚੌਥਾਈ ਤੋਂ ਦੋ ਸੌ ਦੇ ਵਿੱਚ ਹੋਣੇ ਚਾਹੀਦੇ ਹਨ ਜੀ। ਦੁਬਾਰਾ ਦੱਸੋ।", "Acres must be between a quarter and 200. Please say again."),
    "machine_unknown": ("ਮਸ਼ੀਨ ਦਾ ਨਾਂ ਸਮਝ ਨਹੀਂ ਆਇਆ ਜੀ। ਸੁਪਰ ਸੀਡਰ ਹੈਪੀ ਸੀਡਰ ਬੇਲਰ ਜਾਂ ਮਲਚਰ ਵਿੱਚੋਂ ਇੱਕ ਬੋਲੋ।", "I did not get the machine. Say Super Seeder, Happy Seeder, Baler or Mulcher."),
    "machine_which_seeder": ("ਸੁਪਰ ਸੀਡਰ ਚਾਹੀਦਾ ਹੈ ਜਾਂ ਹੈਪੀ ਸੀਡਰ ਜੀ?", "Super Seeder or Happy Seeder?"),
    "date_unknown": ("ਤਾਰੀਖ਼ ਸਮਝ ਨਹੀਂ ਆਈ ਜੀ। ਜਿਵੇਂ ਬੋਲੋ ਅੱਜ ਕੱਲ੍ਹ ਜਾਂ ਪੰਦਰਾਂ ਨਵੰਬਰ।", "I did not get the date. Say today, tomorrow or 15 November."),
    "date_range": ("ਇਹ ਤਾਰੀਖ਼ ਬਹੁਤ ਦੂਰ ਹੈ ਜੀ। ਦੋ ਮਹੀਨਿਆਂ ਦੇ ਅੰਦਰ ਦੀ ਤਾਰੀਖ਼ ਦੱਸੋ।", "That date is too far. Give a date within two months."),
    "date_which_kal": ("ਬੀਤਿਆ ਕੱਲ੍ਹ ਜਾਂ ਆਉਣ ਵਾਲਾ ਕੱਲ੍ਹ ਜੀ?", "Yesterday or tomorrow?"),
    "confirm_unknown": ("ਹਾਂ ਜਾਂ ਨਹੀਂ ਵਿੱਚ ਜਵਾਬ ਦਿਓ ਜੀ।", "Please answer yes or no."),
    "say_again": ("ਠੀਕ ਹੈ ਜੀ ਫਿਰ ਤੋਂ ਦੱਸੋ।", "Okay, tell me again."),
    "mic_off": ("ਮਾਈਕ ਬੰਦ ਹੈ ਜੀ। ਤੁਸੀਂ ਹੇਠਾਂ ਲਿਖ ਕੇ ਵੀ ਜਵਾਬ ਦੇ ਸਕਦੇ ਹੋ।", "The mic is off. You can type your answer below."),
    # After a few answers that were not understood: keep going, kindly.
    "keep_trying": ("ਕੋਈ ਗੱਲ ਨਹੀਂ ਜੀ। ਹੌਲੀ ਹੌਲੀ ਸਾਫ਼ ਬੋਲੋ ਜਾਂ ਹੇਠਾਂ ਚੁਣ ਲਓ।", "No problem. Speak slowly and clearly, or choose below."),
    "paused": ("ਮੈਂ ਰੁਕ ਗਿਆ ਹਾਂ ਜੀ। ਜਦੋਂ ਤਿਆਰ ਹੋਵੋ ਮਾਈਕ ਦਬਾ ਕੇ ਬੋਲੋ।", "I have paused. Tap the mic when you are ready."),
    # Outcomes after saving.
    "done_sched_pre": ("ਤੁਹਾਡੀ ਵਾਰੀ ਲੱਗ ਗਈ ਹੈ ਜੀ। ਮਸ਼ੀਨ", "Your turn is booked. The machine will come to your field on"),
    "done_sched_post": ("ਨੂੰ ਤੁਹਾਡੇ ਖੇਤ ਆਵੇਗੀ। ਧੰਨਵਾਦ ਜੀ।", "Thank you."),
    "done_open": ("ਤੁਹਾਡੀ ਬੇਨਤੀ ਦਰਜ ਹੋ ਗਈ ਹੈ ਜੀ। ਵਾਰੀ ਲੱਗਣ ਤੇ ਸੈਂਟਰ ਤੋਂ ਤੁਹਾਨੂੰ ਦੱਸਿਆ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ।", "Your request is saved. The centre will tell you when your turn is fixed. Thank you."),
    "done_needs_info": ("ਤੁਹਾਡੀ ਬੇਨਤੀ ਦਰਜ ਹੋ ਗਈ ਹੈ ਜੀ। ਕਟਾਈ ਦੀ ਤਾਰੀਖ਼ ਪੱਕੀ ਹੋਣ ਤੇ ਵਾਰੀ ਲੱਗੇਗੀ। ਧੰਨਵਾਦ ਜੀ।", "Your request is saved. The turn is fixed once the harvest date is known. Thank you."),
    "done_will_miss": ("ਤੁਹਾਡੀ ਬੇਨਤੀ ਦਰਜ ਹੋ ਗਈ ਹੈ ਜੀ ਪਰ ਹਾਲੇ ਸਮੇਂ ਸਿਰ ਮਸ਼ੀਨ ਖ਼ਾਲੀ ਨਹੀਂ ਹੈ। ਸੈਂਟਰ ਵਾਲੇ ਤੁਹਾਡੇ ਨਾਲ ਜਲਦੀ ਗੱਲ ਕਰਨਗੇ।", "Your request is saved, but no machine is free in time yet. The centre will call you soon."),
    "submit_failed": ("ਮਾਫ਼ ਕਰਨਾ ਜੀ ਬੁਕਿੰਗ ਸੇਵ ਨਹੀਂ ਹੋਈ। ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ ਜਾਂ ਸੈਂਟਰ ਤੇ ਗੱਲ ਕਰੋ।", "Sorry, the booking was not saved. Try again or talk to the centre."),
    "booking_cancelled": ("ਠੀਕ ਹੈ ਜੀ ਬੁਕਿੰਗ ਨਹੀਂ ਕੀਤੀ। ਕੋਈ ਜਾਣਕਾਰੀ ਬਦਲਣੀ ਹੋਵੇ ਤਾਂ ਉੱਪਰੋਂ ਚੁਣੋ।", "Okay, nothing was booked. Pick any step above to change it."),
}

# key -> Hindi. Same keys as PROMPTS (checked by the tests). Hindi reads back like Punjabi
# ("सवा पाँच", "साढ़े पाँच", "पौने छह"), so the Punjabi-only pieces are used for Hindi too.
PROMPTS_HI: dict[str, str] = {
    "welcome": "नमस्ते जी! वारी में आपका स्वागत है। बस पाँच सवालों में आपकी मशीन की बारी बुक हो जाएगी।",
    "ask_phone": "कृपया अपना दस अंकों का मोबाइल नंबर बताइए जी।",
    "ask_village": "आपका खेत किस गाँव में है जी? गाँव का नाम बताइए।",
    "ask_acres": "कितने एकड़ में काम करवाना है जी? जैसे पाँच एकड़ या साढ़े तीन एकड़।",
    "ask_machine": "आपको कौन सी मशीन चाहिए जी? सुपर सीडर हैप्पी सीडर बेलर या मल्चर?",
    "ask_date": "धान की कटाई कब हुई है या कब होगी जी? जैसे आज कल या पंद्रह नवंबर। अगर पता नहीं तो कहिए पता नहीं।",
    "ask_consent": "आपका नंबर और खेत की जानकारी सिर्फ़ मशीन की बारी और काम के रिकॉर्ड के लिए इस्तेमाल होगी। क्या बुकिंग पक्की कर दें जी?",
    "rb_phone": "आपका नंबर है",
    "confirm_q": "क्या यह सही है जी?",
    "rel_today": "आज",
    "rel_yesterday": "बीता हुआ कल",
    "rel_tomorrow": "आने वाला कल",
    "date_not_yet": "कटाई की तारीख़ अभी तय नहीं।",
    "frac_sava": "सवा",
    "frac_saadhe": "साढ़े",
    "frac_paune": "पौने",
    "and_quarter": "और चौथाई",
    "and_half": "और आधा",
    "and_three_quarters": "और पौना",
    "about": "लगभग",
    "ok_next": "ठीक है जी।",
    "retry_generic": "माफ़ कीजिए जी बात समझ नहीं आई। एक बार फिर बोलिए।",
    "no_speech": "कोई आवाज़ नहीं आई जी। माइक दबाकर फिर बोलिए।",
    "phone_short": "नंबर पूरा नहीं आया जी। दसों अंक धीरे धीरे दोबारा बोलिए।",
    "phone_continue": "ठीक है जी। अब बाकी अंक बोलिए।",
    "phone_long": "नंबर में दस से ज़्यादा अंक आ गए जी। सिर्फ़ दस अंक दोबारा बोलिए।",
    "phone_start": "मोबाइल नंबर छह सात आठ या नौ से शुरू होता है जी। नंबर दोबारा बोलिए।",
    "village_unknown": "यह गाँव सूची में नहीं मिला जी। नाम दोबारा बोलिए या नीचे सूची में से चुनिए।",
    "acres_unknown": "एकड़ समझ नहीं आए जी। जैसे बोलिए पाँच एकड़।",
    "acres_range": "एकड़ चौथाई से दो सौ के बीच होने चाहिए जी। दोबारा बताइए।",
    "machine_unknown": "मशीन का नाम समझ नहीं आया जी। सुपर सीडर हैप्पी सीडर बेलर या मल्चर में से एक बोलिए।",
    "machine_which_seeder": "सुपर सीडर चाहिए या हैप्पी सीडर जी?",
    "date_unknown": "तारीख़ समझ नहीं आई जी। जैसे बोलिए आज कल या पंद्रह नवंबर।",
    "date_range": "यह तारीख़ बहुत दूर है जी। दो महीने के अंदर की तारीख़ बताइए।",
    "date_which_kal": "बीता हुआ कल या आने वाला कल जी?",
    "confirm_unknown": "हाँ या नहीं में जवाब दीजिए जी।",
    "say_again": "ठीक है जी फिर से बताइए।",
    "mic_off": "माइक बंद है जी। आप नीचे लिखकर भी जवाब दे सकते हैं।",
    "keep_trying": "कोई बात नहीं जी। धीरे धीरे साफ़ बोलिए या नीचे से चुन लीजिए।",
    "paused": "मैं रुक गया हूँ जी। जब तैयार हों माइक दबाकर बोलिए।",
    "done_sched_pre": "आपकी बारी लग गई है जी। मशीन",
    "done_sched_post": "को आपके खेत आएगी। धन्यवाद जी।",
    "done_open": "आपका अनुरोध दर्ज हो गया है जी। बारी लगने पर सेंटर से आपको बताया जाएगा। धन्यवाद जी।",
    "done_needs_info": "आपका अनुरोध दर्ज हो गया है जी। कटाई की तारीख़ तय होने पर बारी लगेगी। धन्यवाद जी।",
    "done_will_miss": "आपका अनुरोध दर्ज हो गया है जी पर अभी समय पर मशीन ख़ाली नहीं है। सेंटर वाले आपसे जल्दी बात करेंगे।",
    "submit_failed": "माफ़ कीजिए जी बुकिंग सेव नहीं हुई। दोबारा कोशिश कीजिए या सेंटर पर बात कीजिए।",
    "booking_cancelled": "ठीक है जी बुकिंग नहीं की। कोई जानकारी बदलनी हो तो ऊपर से चुनिए।",
}

# Pieces that only make sense in one language (word order differs).
PA_ONLY_PROMPTS = {"frac_sava", "frac_saadhe", "frac_paune"}
EN_ONLY_PROMPTS = {"and_quarter", "and_half", "and_three_quarters"}

LANGS: tuple[str, ...] = ("pa", "hi", "en")

STEPS: tuple[str, ...] = ("phone", "village", "acres", "machine", "date")

STEP_TITLES: dict[str, tuple[str, str]] = {
    "phone": ("ਫ਼ੋਨ", "Phone"),
    "village": ("ਪਿੰਡ", "Village"),
    "acres": ("ਏਕੜ", "Acres"),
    "machine": ("ਮਸ਼ੀਨ", "Machine"),
    "date": ("ਤਾਰੀਖ਼", "Date"),
}

STEP_TITLES_HI: dict[str, str] = {"phone": "फ़ोन", "village": "गाँव", "acres": "एकड़", "machine": "मशीन", "date": "तारीख़"}

# What to type, shown under the mic.
STEP_HINTS: dict[str, tuple[str, str]] = {
    "phone": ("ਮੋਬਾਈਲ ਨੰਬਰ (ਜਿਵੇਂ 9876543210)", "Mobile number (e.g. 9876543210)"),
    "village": ("ਪਿੰਡ ਦਾ ਨਾਂ", "Village name"),
    "acres": ("ਏਕੜ (ਜਿਵੇਂ 5 ਜਾਂ ਸਾਢੇ 3)", "Acres (e.g. 5 or 3.5)"),
    "machine": ("ਮਸ਼ੀਨ ਚੁਣੋ", "Choose a machine"),
    "date": ("ਕਟਾਈ ਦੀ ਤਾਰੀਖ਼", "Harvest date"),
}

STEP_HINTS_HI: dict[str, str] = {
    "phone": "मोबाइल नंबर (जैसे 9876543210)",
    "village": "गाँव का नाम",
    "acres": "एकड़ (जैसे 5 या साढ़े 3)",
    "machine": "मशीन चुनिए",
    "date": "कटाई की तारीख़",
}


def prompt_text(key: str, lang: str) -> str:
    pa, en = PROMPTS[key]
    return en if lang == "en" else PROMPTS_HI[key] if lang == "hi" else pa


# The acreages that get a whole clip of their own (best prosody):
#   every quarter up to 30, every half up to 99.5, every whole number up to 200.
# Anything else is read as a prefix clip + whole-number clip ("ਸਵਾ" + "45 ਏਕੜ").
ACRES_MAX_X100 = 20000
ACRES_MIN_X100 = 25


@dataclass(frozen=True)
class Clip:
    id: str
    text: str


def number_words(n: int) -> str:
    """0..200 as spoken Punjabi."""
    if n < 0 or n > 200:
        raise ValueError(f"number out of range: {n}")
    if n <= 100:
        return NUMBER_WORDS[n][0]
    if n == 200:
        return "ਦੋ ਸੌ"
    return f"ਇੱਕ ਸੌ {NUMBER_WORDS[n - 100][0]}"


def number_words_hi(n: int) -> str:
    """0..200 as spoken Hindi."""
    if n < 0 or n > 200:
        raise ValueError(f"number out of range: {n}")
    if n <= 100:
        return NUMBER_WORDS_HI[n][0]
    if n == 200:
        return "दो सौ"
    return f"एक सौ {NUMBER_WORDS_HI[n - 100][0]}"


def acres_has_own_clip(x100: int) -> bool:
    if x100 < ACRES_MIN_X100 or x100 > ACRES_MAX_X100:
        return False
    if x100 % 25:
        return False
    if x100 <= 3000:
        return True
    if x100 <= 9950 and x100 % 50 == 0:
        return True
    return x100 % 100 == 0


def acres_words(x100: int) -> str:
    """Spoken Punjabi for an acreage that has its own clip (quarter steps)."""
    whole, part = divmod(x100, 100)
    special = {25: "ਚੌਥਾਈ ਏਕੜ", 50: "ਅੱਧਾ ਏਕੜ", 75: "ਪੌਣਾ ਏਕੜ", 125: "ਸਵਾ ਏਕੜ", 150: "ਡੇਢ ਏਕੜ", 250: "ਢਾਈ ਏਕੜ"}
    if x100 in special:
        return special[x100]
    if part == 0:
        return f"{number_words(whole)} ਏਕੜ"
    if part == 25:
        return f"ਸਵਾ {number_words(whole)} ਏਕੜ"
    if part == 50:
        return f"ਸਾਢੇ {number_words(whole)} ਏਕੜ"
    if part == 75:
        return f"ਪੌਣੇ {number_words(whole + 1)} ਏਕੜ"
    raise ValueError(f"acres not on a quarter step: {x100}")


def acres_words_hi(x100: int) -> str:
    """Spoken Hindi for an acreage that has its own clip (quarter steps)."""
    whole, part = divmod(x100, 100)
    special = {25: "चौथाई एकड़", 50: "आधा एकड़", 75: "पौना एकड़", 125: "सवा एकड़", 150: "डेढ़ एकड़", 250: "ढाई एकड़"}
    if x100 in special:
        return special[x100]
    if part == 0:
        return f"{number_words_hi(whole)} एकड़"
    if part == 25:
        return f"सवा {number_words_hi(whole)} एकड़"
    if part == 50:
        return f"साढ़े {number_words_hi(whole)} एकड़"
    if part == 75:
        return f"पौने {number_words_hi(whole + 1)} एकड़"
    raise ValueError(f"acres not on a quarter step: {x100}")


def acres_words_en(x100: int) -> str:
    """Spoken English for an acreage that has its own clip (quarter steps)."""
    whole, part = divmod(x100, 100)
    special = {25: "a quarter acre", 50: "half an acre", 75: "three quarters of an acre", 100: "one acre"}
    if x100 in special:
        return special[x100]
    if part == 0:
        return f"{whole} acres"
    frac = {25: "and a quarter", 50: "and a half", 75: "and three quarter"}[part]
    return f"{whole} {frac} acres"


def acres_clips(x100: int, lang: str = "pa") -> list[str]:
    """Clip ids that read an acreage aloud. Values off the quarter grid use the nearest quarter."""
    q = int(round(x100 / 25.0)) * 25
    q = max(ACRES_MIN_X100, min(ACRES_MAX_X100, q))
    if acres_has_own_clip(q):
        return [f"acres/{q}"]
    whole, part = divmod(q, 100)
    if lang == "en":
        # "45 acres" + "and a quarter"
        tail = {25: "and_quarter", 50: "and_half", 75: "and_three_quarters"}[part]
        return [f"acres/{whole * 100}", f"prompt/{tail}"]
    if part == 25:
        return ["prompt/frac_sava", f"acres/{whole * 100}"]
    if part == 50:
        return ["prompt/frac_saadhe", f"acres/{whole * 100}"]
    # part == 75
    return ["prompt/frac_paune", f"acres/{(whole + 1) * 100}"]


def date_words(month: int, day: int) -> str:
    day_word = "ਪਹਿਲੀ" if day == 1 else number_words(day)
    return f"{day_word} {MONTH_WORDS[month][0]}"


def date_words_hi(month: int, day: int) -> str:
    day_word = "पहली" if day == 1 else number_words_hi(day)
    return f"{day_word} {MONTHS_HI[month]}"


def ordinal_en(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


EN_MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
EN_DIGITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def date_words_en(month: int, day: int) -> str:
    return f"{ordinal_en(day)} {EN_MONTHS[month]}"


def date_clip(month: int, day: int) -> str:
    return f"date/{month:02d}-{day:02d}"


def village_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return slug or "village"


def village_clip(name: str) -> str:
    return f"village/{village_slug(name)}"


def village_words(entry: VillageEntry) -> str:
    return entry.name_pa if entry.name_pa.startswith("ਪਿੰਡ") else f"ਪਿੰਡ {entry.name_pa}"


def village_words_hi(entry: VillageEntry) -> str:
    name = guru_to_deva(entry.name_pa) if entry.name_pa else entry.name
    return name if name.startswith("पिंड") else f"गाँव {name}"


def machine_clip(service_type: str) -> str:
    return f"machine/{service_type}"


def build_clips(villages: list[VillageEntry] | None = None, lang: str = "pa") -> list[Clip]:
    """Every clip the flow can play in one language, in a stable order. Same ids in every language."""
    if lang not in LANGS:
        raise ValueError(f"unknown language: {lang}")
    en, hi = lang == "en", lang == "hi"
    skip = PA_ONLY_PROMPTS if en else EN_ONLY_PROMPTS
    clips: list[Clip] = [Clip(f"prompt/{k}", prompt_text(k, lang)) for k in PROMPTS if k not in skip]
    clips += [
        Clip(f"digit/{d}", EN_DIGITS[d] if en else NUMBER_WORDS_HI[d][0] if hi else NUMBER_WORDS[d][0])
        for d in range(10)
    ]
    for entry in villages if villages is not None else list(VILLAGES_PA):
        text = entry.name if en else village_words_hi(entry) if hi else village_words(entry)
        clips.append(Clip(village_clip(entry.name), text))
    clips += [
        Clip(machine_clip(m.id), m.name_en if en else MACHINE_NAMES_HI[m.id] if hi else m.name_pa) for m in MACHINES
    ]
    clips += [
        Clip(f"acres/{x}", acres_words_en(x) if en else acres_words_hi(x) if hi else acres_words(x))
        for x in range(ACRES_MIN_X100, ACRES_MAX_X100 + 1, 25)
        if acres_has_own_clip(x)
    ]
    days_in_month = {1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
    for month, days in days_in_month.items():
        for day in range(1, days + 1):
            text = date_words_en(month, day) if en else date_words_hi(month, day) if hi else date_words(month, day)
            clips.append(Clip(date_clip(month, day), text))
    return clips
