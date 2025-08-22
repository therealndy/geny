// Minimal Safety service enforcing simple rules from the SUPERPROMPT

class SafetyService {
  SafetyService();

  /// Evaluate a candidate output and return a safe, possibly modified output.
  ///
  /// [candidate] is required and must be a non-empty string.
  Future<String> enforce(String candidate) async {
    if (candidate.trim().isEmpty) {
      throw ArgumentError('candidate must be a non-empty string');
    }
    // Very small rule set for demonstration:
    // - Remove personally identifying instructions
    // - Replace explicit negative affect with softened language
    await Future.delayed(const Duration(milliseconds: 20));
    var out = candidate;

    // redact violent verbs
    out = out.replaceAll(RegExp(r'\b(kill|destroy|murder)\b', caseSensitive: false), '[redacted]');

    // soften direct insults
    out = out.replaceAll(RegExp(r'\byou are (stupid|dumb|idiot)\b', caseSensitive: false), 'I hear strong feelings; let\'s reframe.');

    // basic profanity list (expand as needed)
    final profanities = ['shit', 'fuck', 'damn'];
    for (var p in profanities) {
      out = out.replaceAll(
        RegExp('\\b${RegExp.escape(p)}\\b', caseSensitive: false),
        '[censored]',
      );
    }

    // simple PII-ish detection: email-like patterns -> redact
    out = out.replaceAll(RegExp(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b'), '[redacted-email]');

    return out;
  }
}
