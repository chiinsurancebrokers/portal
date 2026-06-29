"""
HAL Engine — CHI Insurance Portal v2
Anthropic Claude integration | AI brain for all portal activities
"""
import os, json, requests
from datetime import datetime

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"

CHI_SYSTEM_CONTEXT = """Είσαι ο HAL — AI ασφαλιστικός σύμβουλος της CHI Insurance Brokers.
Ο Χρήστος Ιατρόπουλος είναι ο μεσίτης (τηλ. 6975900189). Χρησιμοποιείς ελληνικά ΕΚΤΟΣ αν ο χρήστης γράψει αγγλικά.
Είσαι ειδικός σε ασφαλιστικά προϊόντα: αυτοκίνητο, ζωή, υγεία, περιουσία, ταξίδι, κατοικίδια, επιχείρηση.
Δίνεις σαφείς, επαγγελματικές απαντήσεις. Ποτέ δεν αποκαλύπτεις εμπιστευτικά οικονομικά στοιχεία
εκτός αν ζητηθούν ρητά από εξουσιοδοτημένο χρήστη.
CHI Insurance Brokers | Αθήνα | info@chiinsurancebrokers.com"""

def _call_api(messages: list, system: str = CHI_SYSTEM_CONTEXT, max_tokens: int = 1500) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "⚠️ HAL δεν είναι διαθέσιμος. Ρυθμίστε το ANTHROPIC_API_KEY στο Railway."
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    try:
        r = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data["content"][0]["text"]
    except requests.exceptions.Timeout:
        return "⚠️ HAL timeout. Δοκιμάστε ξανά."
    except Exception as e:
        return f"⚠️ HAL error: {str(e)[:200]}"


def explain_policy(policy_data: dict, client_name: str = "") -> str:
    """Explain a policy in plain language. Max 1500 tokens."""
    prompt = f"""Εξήγησε αυτό το ασφαλιστήριο συμβόλαιο με απλά λόγια στον ασφαλισμένο.
Όνομα ασφαλισμένου: {client_name}
Στοιχεία συμβολαίου:
{json.dumps(policy_data, ensure_ascii=False, indent=2)}

Ανάλυσε:
1. Τι καλύπτει
2. Τι ΔΕΝ καλύπτει (εξαιρέσεις)
3. Πότε λήγει και τι πρέπει να γίνει
4. Πώς να υποβάλει αξίωση αν χρειαστεί
5. Μια σύντομη σύσταση

Γράψε σε φιλικό, κατανοητό ύφος. Μέγιστο 400 λέξεις."""
    return _call_api([{"role": "user", "content": prompt}], max_tokens=1500)


def draft_renewal_email(client_data: dict, policy_data: dict, days_left: int) -> dict:
    """Generate a HAL renewal email. Returns {subject, body_html}."""
    lang = "ελληνικά" if any(ord(c) > 127 for c in client_data.get("name", "")) else "αγγλικά"
    prompt = f"""Γράψε επαγγελματικό email ανανέωσης ασφαλιστηρίου σε {lang}.
Αποστολέας: CHI Insurance Brokers (info@chiinsurancebrokers.com)
Παραλήπτης: {client_data.get('name')} ({client_data.get('email')})
Συμβόλαιο: {policy_data.get('policy_type')} | {policy_data.get('provider')}
Αριθμός: {policy_data.get('policy_number', 'N/A')}
Ασφάλιστρο: €{policy_data.get('premium', 0):.2f}
Λήξη σε: {days_left} ημέρες ({policy_data.get('expiration_date')})

Το email πρέπει:
- Να είναι ζεστό αλλά επαγγελματικό
- Να τονίζει τη σημασία της ανανέωσης
- Να αναφέρει επικοινωνία: 210-XXXXXXX | info@chiinsurancebrokers.com
- HTML format με καλή μορφοποίηση

Απάντησε ΜΟΝ με JSON: {{"subject": "...", "body_html": "..."}}"""
    raw = _call_api([{"role": "user", "content": prompt}], max_tokens=1200)
    try:
        # Strip markdown fences if present
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        return json.loads(clean.strip())
    except Exception:
        return {
            "subject": f"Ανανέωση Ασφαλιστηρίου — {policy_data.get('policy_type','')}",
            "body_html": f"<p>Αγαπητέ/ή {client_data.get('name')},<br>Το ασφαλιστήριό σας λήγει σε {days_left} ημέρες. Επικοινωνήστε μαζί μας.<br><br>CHI Insurance Brokers</p>"
        }


def analyze_document(content: str, doc_type: str = "unknown") -> str:
    """AI analysis of a scanned/uploaded document."""
    prompt = f"""Ανάλυσε αυτό το έγγραφο ασφαλείας και εξήγησε τα βασικά στοιχεία.
Τύπος εγγράφου: {doc_type}
Περιεχόμενο:
{content[:3000]}

Εξήγησε:
1. Τι είδους έγγραφο είναι
2. Τα κύρια στοιχεία (ημερομηνίες, ποσά, συμβαλλόμενοι)
3. Σημαντικές παρατηρήσεις ή δράσεις που απαιτούνται
4. Συνοπτική αξιολόγηση"""
    return _call_api([{"role": "user", "content": prompt}], max_tokens=1000)


def commission_insights(data: dict) -> str:
    """Strategic commission analysis for back office."""
    prompt = f"""Ανάλυσε τα στοιχεία προμηθειών της CHI Insurance και δώσε στρατηγικές συστάσεις.
Δεδομένα:
{json.dumps(data, ensure_ascii=False, indent=2)}

Ανάλυσε:
1. Ποιος πάροχος είναι πιο κερδοφόρος (ανά τομέα)
2. Τάσεις στις προμήθειες (ανά μήνα)
3. Ευκαιρίες upselling ανά τομέα
4. Στρατηγικές συστάσεις για μεγιστοποίηση εσόδων
5. Red flags ή ανησυχίες

Γράψε επαγγελματική ανάλυση, ελληνικά, μέγιστο 300 λέξεις."""
    return _call_api([{"role": "user", "content": prompt}], max_tokens=1000)


def upsell_opportunities(client_data: dict, policies: list) -> str:
    """Strategic upsell recommendations for a client."""
    prompt = f"""Ανάλυσε τον πελάτη και τα συμβόλαιά του και πρότεινε ευκαιρίες upselling/cross-selling.
Πελάτης: {client_data.get('name')} | {client_data.get('profession','')} | {client_data.get('city','')}
Υπάρχοντα συμβόλαια:
{json.dumps(policies, ensure_ascii=False, indent=2)}

Πρότεινε:
1. Επιπλέον καλύψεις που λείπουν
2. Αναβαθμίσεις υπαρχόντων συμβολαίων  
3. Νέα προϊόντα κατάλληλα για το προφίλ του
4. Εκτιμώμενη πρόσθετη αξία (σε €)
5. Χρονισμός προσέγγισης (πότε να μιλήσεις)

Σύντομη, actionable ανάλυση (max 250 λέξεις)."""
    return _call_api([{"role": "user", "content": prompt}], max_tokens=800)


def lixiario_insights(month_data: list, month: int, year: int) -> str:
    """Analyze monthly expiry list and prioritize renewals."""
    month_names = ["","Ιανουάριος","Φεβρουάριος","Μάρτιος","Απρίλιος","Μάιος","Ιούνιος",
                   "Ιούλιος","Αύγουστος","Σεπτέμβριος","Οκτώβριος","Νοέμβριος","Δεκέμβριος"]
    prompt = f"""Ανάλυσε τις ανανεώσεις {month_names[month]} {year} και δώσε στρατηγικές προτεραιότητες.
Ληξιάριο {month}/{year}:
{json.dumps(month_data, ensure_ascii=False, indent=2)}

Ανάλυσε:
1. Συνολικά ασφάλιστρα προς ανανέωση
2. Ποια πρέπει να σταλούν ΠΡΩΤΑ (ποιοι πελάτες)
3. Ποια έχουν ρίσκο να φύγουν σε ανταγωνιστή
4. Συνολική εκτιμώμενη αξία αν ανανεωθούν όλα
5. Σύσταση για προσέγγιση (email vs τηλέφωνο)"""
    return _call_api([{"role": "user", "content": prompt}], max_tokens=800)


def chat(messages: list, context: str = "") -> str:
    """General HAL chat with optional context."""
    system = CHI_SYSTEM_CONTEXT
    if context:
        system += (f"\n\nΠΡΑΓΜΑΤΙΚΑ ΣΤΟΙΧΕΙΑ ΠΕΛΑΤΗ ΚΑΙ ΣΥΜΒΟΛΑΙΩΝ ΤΟΥ:\n{context}\n\n"
                    "Χρησιμοποίησε ΜΟΝΟ αυτά τα στοιχεία όταν απαντάς για συγκεκριμένα ποσά, "
                    "ημερομηνίες, αριθμούς συμβολαίου ή καλύψεις. Αν κάτι δεν αναφέρεται εδώ, "
                    "πες καθαρά ότι δεν είναι καταχωρημένο στο σύστημα και πρότεινε επικοινωνία "
                    "με τον μεσίτη — μην το επινοείς.")
    return _call_api(messages, system=system, max_tokens=1500)

# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENT INTELLIGENCE — AI-powered extraction & auto-registration
# ══════════════════════════════════════════════════════════════════════════════

import base64

EXTRACTION_SYSTEM = """Είσαι ειδικός εξαγωγής δεδομένων από ασφαλιστικά έντυπα για την CHI Insurance Brokers.
Αναλύεις έγγραφα και επιστρέφεις ΜΟΝΟ έγκυρο JSON — χωρίς markdown, χωρίς εξηγήσεις.
Αν κάποιο πεδίο δεν υπάρχει στο έγγραφο, βάλε null.
Ποσά ΠΑΝΤΑ ως αριθμοί (όχι string). Ημερομηνίες ως YYYY-MM-DD."""

def _call_vision_api(image_b64: str, media_type: str, prompt: str, max_tokens: int = 2000) -> str:
    """Call Claude API with image input."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return '{"error": "No API key"}'
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": EXTRACTION_SYSTEM,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": prompt}
            ]
        }]
    }
    try:
        r = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=90)
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    except Exception as e:
        return f'{{"error": "{str(e)[:100]}"}}'


def classify_document(content: str, filename: str = "") -> dict:
    """Identify document type and extract all data. Returns structured dict."""
    prompt = f"""Αναλύεις αυτό το ασφαλιστικό έγγραφο: "{filename}"

Περιεχόμενο:
{content[:4000]}

Πρώτα αναγνώρισε τον ΤΥΠΟ εγγράφου:
- "commission_statement" = Κατάσταση Προμηθειών από ασφαλιστική εταιρεία
- "policy" = Ασφαλιστήριο Συμβόλαιο (νέο ή ανανέωση)
- "payment_receipt" = Απόδειξη / Τιμολόγιο πληρωμής ασφαλίστρου
- "claim" = Αξίωση / Βλάβη / Claim
- "client_email" = Αλληλογραφία / Αίτημα πελάτη
- "unknown" = Άγνωστο

Μετά εξήγαγε τα δεδομένα ανάλογα με τον τύπο.

Επίστρεψε JSON:
{{
  "doc_type": "...",
  "confidence": 0.95,
  "data": {{
    // Για commission_statement:
    "provider_name": null,
    "period_month": null,
    "period_year": null,
    "total_premium": null,
    "commission_rate": null,
    "commission_amount": null,

    // Για policy:
    "client_name": null,
    "client_tax_id": null,
    "client_phone": null,
    "client_mobile": null,
    "policy_number": null,
    "policy_type": null,
    "sector": null,
    "provider": null,
    "premium": null,
    "start_date": null,
    "expiration_date": null,
    "license_plate": null,
    "payment_code": null,
    "agent_code": null,

    // Για payment_receipt:
    "client_name": null,
    "policy_number": null,
    "amount_paid": null,
    "payment_date": null,
    "receipt_number": null,

    // Για claim:
    "client_name": null,
    "policy_number": null,
    "claim_number": null,
    "description": null,
    "claim_amount": null,
    "incident_date": null,

    // Για client_email:
    "client_name": null,
    "client_email": null,
    "subject": null,
    "description": null,
    "priority": null,
    "policy_number": null
  }},
  "summary": "Σύντομη περιγραφή τι βρέθηκε",
  "warnings": []
}}"""
    raw = _call_api([{"role": "user", "content": prompt}],
                    system=EXTRACTION_SYSTEM, max_tokens=2000)
    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:])
            if clean.endswith("```"):
                clean = clean[:-3]
        return json.loads(clean.strip())
    except Exception:
        return {"doc_type": "unknown", "confidence": 0, "data": {}, "summary": raw[:200], "warnings": ["Parse error"]}


def classify_document_image(image_b64: str, media_type: str, filename: str = "") -> dict:
    """Classify and extract from image/scanned PDF using Vision API."""
    prompt = f"""Αναλύεις αυτή την εικόνα ασφαλιστικού εγγράφου: "{filename}"

Αναγνώρισε τον τύπο και εξήγαγε όλα τα δεδομένα.
Επίστρεψε ΜΟΝΟ JSON στη μορφή:
{{
  "doc_type": "commission_statement|policy|payment_receipt|claim|client_email|unknown",
  "confidence": 0.0-1.0,
  "data": {{
    "provider_name": null, "period_month": null, "period_year": null,
    "total_premium": null, "commission_rate": null, "commission_amount": null,
    "client_name": null, "client_tax_id": null, "client_phone": null,
    "policy_number": null, "policy_type": null, "sector": null, "provider": null,
    "premium": null, "start_date": null, "expiration_date": null,
    "license_plate": null, "payment_code": null, "agent_code": null,
    "amount_paid": null, "payment_date": null, "receipt_number": null,
    "claim_number": null, "description": null, "claim_amount": null,
    "incident_date": null, "subject": null, "priority": null
  }},
  "summary": "...",
  "warnings": []
}}"""
    raw = _call_vision_api(image_b64, media_type, prompt, max_tokens=2000)
    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:])
            if clean.endswith("```"):
                clean = clean[:-3]
        return json.loads(clean.strip())
    except Exception:
        return {"doc_type": "unknown", "confidence": 0, "data": {}, "summary": raw[:200], "warnings": ["Parse error"]}
