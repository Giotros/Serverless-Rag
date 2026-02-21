# Πολιτική Ασφάλειας Πληροφοριών

**TechCorp Hellas - IT Security Department**
**Έκδοση 3.0 | Ιανουάριος 2026**

---

## 1. Σκοπός

Η παρούσα πολιτική καθορίζει τα μέτρα ασφάλειας πληροφοριών που πρέπει να τηρούνται από όλους τους εργαζόμενους της TechCorp Hellas.

## 2. Πεδίο Εφαρμογής

Η πολιτική αφορά:
- Όλους τους εργαζόμενους (μόνιμους και συμβασιούχους)
- Όλα τα πληροφοριακά συστήματα της εταιρείας
- Όλες τις συσκευές που χρησιμοποιούνται για εργασία

## 3. Διαχείριση Κωδικών Πρόσβασης

### 3.1 Απαιτήσεις Κωδικών

| Χαρακτηριστικό | Απαίτηση |
|----------------|----------|
| Ελάχιστο μήκος | 12 χαρακτήρες |
| Κεφαλαία γράμματα | Τουλάχιστον 1 |
| Πεζά γράμματα | Τουλάχιστον 1 |
| Αριθμοί | Τουλάχιστον 1 |
| Ειδικοί χαρακτήρες | Τουλάχιστον 1 (!@#$%^&*) |
| Αλλαγή κωδικού | Κάθε 90 ημέρες |
| Ιστορικό κωδικών | 10 τελευταίοι δεν επαναχρησιμοποιούνται |

### 3.2 Απαγορεύσεις

- Κοινοποίηση κωδικού σε τρίτους
- Αποθήκευση κωδικών σε plain text
- Χρήση του ίδιου κωδικού σε πολλαπλά συστήματα
- Αυτόματη αποθήκευση κωδικών στο browser

### 3.3 Password Manager

Συνιστάται η χρήση του εταιρικού password manager:
- **1Password Business** (παρέχεται δωρεάν)
- Εγκατάσταση από: apps.techcorp.example.com
- Support: security@techcorp.example.com

## 4. Multi-Factor Authentication (MFA)

### 4.1 Υποχρεωτικό MFA

Το MFA είναι υποχρεωτικό για:
- Πρόσβαση σε email
- VPN σύνδεση
- Cloud εφαρμογές (AWS, GCP, Azure)
- HR systems
- Financial systems

### 4.2 Εγκεκριμένες Μέθοδοι MFA

1. **Microsoft Authenticator** (προτιμώμενο)
2. **Google Authenticator**
3. **Hardware tokens** (για υψηλού κινδύνου συστήματα)

## 5. Πρόσβαση σε Συστήματα

### 5.1 Αρχή Ελάχιστων Προνομίων

Κάθε χρήστης λαμβάνει μόνο τις απαραίτητες πρόσβασης για την εργασία του. Οι πρόσβασες:
- Εγκρίνονται από τον manager
- Επανεξετάζονται τριμηνιαία
- Ανακαλούνται αυτόματα κατά την αποχώρηση

### 5.2 Privileged Access

Για πρόσβαση admin/root:
- Απαιτείται έγκριση Security Team
- Χρήση dedicated admin account
- Logging όλων των ενεργειών
- Χρονικό όριο session: 4 ώρες

## 6. Προστασία Συσκευών

### 6.1 Laptops & Desktops

- Full disk encryption (BitLocker/FileVault)
- Αυτόματο κλείδωμα: 5 λεπτά αδράνειας
- Antivirus: CrowdStrike Falcon (προεγκατεστημένο)
- Automatic updates: Ενεργοποιημένα

### 6.2 Mobile Devices

Για BYOD (Bring Your Own Device):
- Εγκατάσταση MDM (Microsoft Intune)
- PIN/Biometric lock υποχρεωτικό
- Remote wipe capability
- Διαχωρισμός εταιρικών/προσωπικών δεδομένων

### 6.3 Απώλεια Συσκευής

Σε περίπτωση απώλειας/κλοπής:
1. Αναφορά στο IT Help Desk (εντός 1 ώρας)
2. Remote wipe initiation
3. Αλλαγή όλων των κωδικών
4. Αναφορά στην ασφάλεια αν περιέχει ευαίσθητα δεδομένα

## 7. Email Security

### 7.1 Phishing Protection

- Μην κάνετε click σε ύποπτα links
- Επαληθεύστε τον αποστολέα πριν ανοίξετε attachments
- Αναφέρετε ύποπτα emails: phishing@techcorp.example.com
- Ποτέ μην δίνετε credentials μέσω email

### 7.2 Sensitive Data via Email

Για αποστολή ευαίσθητων δεδομένων:
- Χρήση encryption (Outlook: Encrypt button)
- Password-protected attachments
- Επιβεβαίωση παραλήπτη τηλεφωνικά

## 8. Χρήση Internet

### 8.1 Αποδεκτή Χρήση

Επιτρέπεται:
- Πρόσβαση σε εργασιακά sites
- Περιορισμένη προσωπική χρήση (breaks)
- Cloud storage μόνο εγκεκριμένα (OneDrive, S3)

### 8.2 Απαγορευμένη Χρήση

- Torrents και file sharing
- Adult content
- Gambling
- Proxy/VPN bypass
- Unauthorized cloud storage

## 9. Διαχείριση Δεδομένων

### 9.1 Κατηγορίες Δεδομένων

| Κατηγορία | Περιγραφή | Παραδείγματα |
|-----------|-----------|--------------|
| **Δημόσια** | Μπορούν να δημοσιοποιηθούν | Press releases, marketing |
| **Εσωτερικά** | Μόνο για εσωτερική χρήση | Οργανόγραμμα, policies |
| **Εμπιστευτικά** | Περιορισμένη πρόσβαση | Οικονομικά, contracts |
| **Αυστηρά Εμπιστευτικά** | Need-to-know basis | PII, credentials |

### 9.2 Χειρισμός Εμπιστευτικών

- Μην αποθηκεύετε σε USB
- Μην εκτυπώνετε χωρίς λόγο
- Τηρείτε clean desk policy
- Καταστροφή με shredder

## 10. VPN & Remote Access

### 10.1 Χρήση VPN

VPN απαιτείται για:
- Πρόσβαση σε internal systems εκτός γραφείου
- Σύνδεση από public WiFi
- Πρόσβαση σε production servers

### 10.2 VPN Client

- Download: vpn.techcorp.example.com
- Protocol: WireGuard (recommended) ή OpenVPN
- Auto-connect: Ενεργοποιημένο

## 11. Incident Response

### 11.1 Τι Αποτελεί Security Incident

- Unauthorized access
- Malware infection
- Data breach
- Phishing attempt
- Lost/stolen device
- Suspicious activity

### 11.2 Διαδικασία Αναφοράς

1. **Άμεση αναφορά** στο Security Operations Center
   - Email: soc@techcorp.example.com
   - Phone: +30 210 1234599 (24/7)
   - Slack: #security-incidents

2. **Μην προσπαθήσετε** να διορθώσετε μόνοι σας
3. **Διατηρήστε** evidence (screenshots, logs)
4. **Μην κοινοποιήσετε** εκτός εταιρείας

## 12. Εκπαίδευση

### 12.1 Υποχρεωτική Εκπαίδευση

| Εκπαίδευση | Συχνότητα | Διάρκεια |
|------------|-----------|----------|
| Security Awareness | Ετησίως | 2 ώρες |
| Phishing Simulation | Τριμηνιαία | - |
| GDPR | Κατά την πρόσληψη + κάθε 2 έτη | 1 ώρα |
| Role-specific | Ανά ρόλο | Varies |

### 12.2 Πλατφόρμα Εκπαίδευσης

- URL: training.techcorp.example.com
- Deadline notifications: Αυτόματα via email
- Certificates: Διαθέσιμα μετά την ολοκλήρωση

## 13. Compliance

Η πολιτική συμμορφώνεται με:
- GDPR (EU General Data Protection Regulation)
- ISO 27001
- SOC 2 Type II
- PCI DSS (για payment systems)

## 14. Κυρώσεις

Παραβάσεις της πολιτικής μπορεί να επιφέρουν:
- Προειδοποίηση
- Αναστολή πρόσβασης
- Πειθαρχικές ποινές
- Τερματισμό σύμβασης
- Νομικές ενέργειες

## 15. Επικοινωνία

**IT Security Team**
- Email: security@techcorp.example.com
- Phone: +30 210 1234599
- Slack: #it-security

**IT Help Desk**
- Email: helpdesk@techcorp.example.com
- Phone: +30 210 1234500
- Portal: support.techcorp.example.com

---

*Τελευταία ενημέρωση: 10 Ιανουαρίου 2026*
*Επόμενη αναθεώρηση: 10 Ιανουαρίου 2027*
*Υπεύθυνος: Chief Information Security Officer (CISO)*
