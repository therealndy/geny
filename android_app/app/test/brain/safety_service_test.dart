import 'package:flutter_test/flutter_test.dart';
import 'package:app/brain/services/safety_service.dart';

void main() {
  group('SafetyService', () {
    final svc = SafetyService();

    test('enforce returns modified string for unsafe content', () async {
      final out = await svc.enforce('We should kill it');
      expect(out, isA<String>());
      expect(out, contains('[redacted]'));
    });

    test('enforce censors profanity', () async {
      final out = await svc.enforce('That is shit');
      expect(out, contains('[censored]'));
    });

    test('enforce redacts email-like PII', () async {
      final out = await svc.enforce('Contact me at test.user@example.com');
      expect(out, contains('[redacted-email]'));
    });

    test('enforce throws on empty candidate', () async {
      expect(() => svc.enforce(''), throwsArgumentError);
    });
  });
}
