# Vaari Voice Booking Scripts (5 Evaluation Dialogues)

These 5 dialogues represent realistic Punjabi farmer speech patterns for local voice booking evaluation.
They cover:
1. Standard single-field happy path (Super Seeder)
2. Multi-field single-turn speech (Happy Seeder, explicit date)
3. Background noise / retry and in-sentence correction (acres change)
4. Read-back revision / date adjustment
5. Voluntary cancellation

---

## Dialogue 1: Super Seeder (Standard Happy Path)
* **Goal**: Book a Super Seeder for 2.5 acres in Rampur, harvesting tomorrow.
* **Turns**:
  * **Farmer Turn 1** (Phone): `ਮੇਰਾ ਫੋਨ ਨੰਬਰ 9876543210 ਹੈ ਜੀ`
    * English: "My phone number is 9876543210 sir"
    * Extracted: `phone = "9876543210"`
  * **Farmer Turn 2** (Village): `ਪਿੰਡ ਰਾਮਪੁਰ, ਡਾਕਖਾਨਾ ਵੀ ਓਹੀ`
    * English: "Village Rampur, post office is also the same"
    * Extracted: `village = "Rampur"`
  * **Farmer Turn 3** (Acres): `ਢਾਈ ਏਕੜ ਜ਼ਮੀਨ ਹੈਗੀ ਸਾਡੀ`
    * English: "We have two and a half acres of land"
    * Extracted: `acres = 2.5`
  * **Farmer Turn 4** (Machine): `ਸੁਪਰ ਸੀਡਰ ਭੇਜ ਦਿਓ`
    * English: "Please send a Super Seeder"
    * Extracted: `machine = "Super Seeder"`
  * **Farmer Turn 5** (Date): `ਕੱਲ੍ਹ ਨੂੰ ਵਾਢੀ ਹੋ ਜਾਣੀ ਹੈ`
    * English: "Harvest will be done tomorrow"
    * Extracted: `harvest_date = relative tomorrow`
  * **Farmer Turn 6** (Confirmation): `ਹਾਂਜੀ ਬਿਲਕੁਲ ਠੀਕ ਹੈ`
    * English: "Yes, exactly right"
    * Extracted: `confirmed = true`

---

## Dialogue 2: Happy Seeder (Multi-field Turn + Explicit Date)
* **Goal**: Farmer provides phone, village, acres, machine and explicit date in one turn.
* **Turns**:
  * **Farmer Turn 1**: `ਮੇਰਾ ਨੰਬਰ 9812345678 ਹੈ, ਪਿੰਡ ਕਿਲਾ ਰਾਏਪੁਰ, ਪੰਜ ਏਕੜ ਲਈ ਹੈਪੀ ਸੀਡਰ ਚਾਹੀਦਾ 2 ਨਵੰਬਰ ਨੂੰ`
    * English: "My number is 9812345678, village Kila Raipur, need Happy Seeder for five acres on 2 November"
    * Extracted: `phone = "9812345678"`, `village = "Kila Raipur"`, `acres = 5.0"`, `machine = "Happy Seeder"`, `harvest_date = "2026-11-02"`
  * **Farmer Turn 2** (Confirmation): `ਹਾਂ ਜੀ ਠੀਕ ਹੈ ਬੁੱਕ ਕਰ ਦਿਓ`
    * English: "Yes right, please book it"
    * Extracted: `confirmed = true`

---

## Dialogue 3: Noisy Speech / Retry & In-Sentence Correction
* **Goal**: Unintelligible tractor sound on first turn, clean retry, then self-correction on acres.
* **Turns**:
  * **Farmer Turn 1** (Noise): `ਘੜ ਘੜ... ਆਵਾਜ਼ ਸਾਫ ਨਹੀਂ...`
    * English: "[Tractor rumble... voice not clear]"
    * Extracted: `None` (retry asked)
  * **Farmer Turn 2** (Phone retry): `ਨੰਬਰ ਲਿਖੋ 9888877777`
    * English: "Write down the number 9888877777"
    * Extracted: `phone = "9888877777"`
  * **Farmer Turn 3** (Village): `ਪਿੰਡ ਧਾਂਦਰਾਂ`
    * English: "Village Dhandra"
    * Extracted: `village = "Dhandra"`
  * **Farmer Turn 4** (Acres correction): `ਤਿੰਨ ਏਕੜ... ਨਹੀਂ ਨਹੀਂ ਚਾਰ ਏਕੜ ਕਰ ਦਿਓ`
    * English: "Three acres... no no, make it four acres"
    * Extracted: `acres = 4.0`
  * **Farmer Turn 5** (Machine): `ਸੁਪਰਸੀਡਰ`
    * English: "Super Seeder"
    * Extracted: `machine = "Super Seeder"`
  * **Farmer Turn 6** (Date): `ਪਰਸੋਂ ਨੂੰ`
    * English: "Day after tomorrow"
    * Extracted: `harvest_date = relative day after tomorrow`
  * **Farmer Turn 7** (Confirmation): `ਆਹੋ ਜੀ ਸਹੀ ਹੈ`
    * English: "Yes sir, it is correct"
    * Extracted: `confirmed = true`

---

## Dialogue 4: Read-Back Revision (Date Adjustment)
* **Goal**: Farmer corrects harvest date after read-back summary.
* **Turns**:
  * **Farmer Turn 1** (Phone): `9777766666`
    * Extracted: `phone = "9777766666"`
  * **Farmer Turn 2** (Village): `ਪਿੰਡ ਮਨਸੂਰਾਂ`
    * Extracted: `village = "Mansuran"`
  * **Farmer Turn 3** (Acres): `ਡੇਢ ਏਕੜ`
    * Extracted: `acres = 1.5`
  * **Farmer Turn 4** (Machine): `ਮਲਚਰ`
    * Extracted: `machine = "Mulcher"`
  * **Farmer Turn 5** (Date): `ਕੱਲ੍ਹ ਨੂੰ`
    * Extracted: `harvest_date = relative tomorrow`
  * **Farmer Turn 6** (Revision): `ਨਹੀਂ ਤਾਰੀਖ ਬਦਲ ਦਿਓ, ਸੋਮਵਾਰ ਨੂੰ ਚਾਹੀਦਾ ਹੈ`
    * Extracted: `harvest_date = relative Monday`, `confirmed = false`
  * **Farmer Turn 7** (Confirmation): `ਹਾਂਜੀ ਹੁਣ ਸਹੀ ਹੈ`
    * Extracted: `confirmed = true`

---

## Dialogue 5: Voluntary Cancellation
* **Goal**: Farmer decides not to proceed midway and cancels the session.
* **Turns**:
  * **Farmer Turn 1** (Phone): `9855544433`
    * Extracted: `phone = "9855544433"`
  * **Farmer Turn 2** (Village): `ਪਿੰਡ ਜੋਧਾਂ`
    * Extracted: `village = "Jodhan"`
  * **Farmer Turn 3** (Cancel): `ਨਹੀਂ ਮੈਨੂੰ ਨਹੀਂ ਚਾਹੀਦਾ, ਕੈਂਸਲ ਕਰ ਦਿਓ`
    * English: "No I don't need it, please cancel"
    * Extracted: `cancelled = true`
