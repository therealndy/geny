import 'package:flutter_test/flutter_test.dart';
import 'package:app/brain/services/thought_loop_service.dart';

void main() {
  group('ThoughtLoopService', () {
    final svc = ThoughtLoopService();

    test('reflect returns a non-empty list for valid input', () async {
      final out = await svc.reflect('How are you?');
      expect(out, isA<List<String>>());
      expect(out, isNotEmpty);
    });

    test('reflect throws on empty input', () async {
      expect(() => svc.reflect(''), throwsArgumentError);
    });
  });
}
