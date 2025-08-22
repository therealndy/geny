import 'package:flutter_test/flutter_test.dart';
import 'package:app/brain/services/thought_loop_service.dart';
import 'package:app/shared/models/core.dart';

void main() {
  group('ThoughtLoop with memories', () {
    final svc = ThoughtLoopService();

    test('reflect summarizes recent memories', () async {
      final now = DateTime.now();
      final mems = [
        MemoryItem(
          id: '1',
          type: MemoryType.episodic,
          content: 'first',
          timestamp: now.subtract(Duration(minutes: 5)),
        ),
        MemoryItem(
          id: '2',
          type: MemoryType.semantic,
          content: 'second',
          timestamp: now.subtract(Duration(minutes: 1)),
        ),
      ];

      final out = await svc.reflect('Check memories', recentMemories: mems);
      expect(out.any((s) => s.startsWith('Memory summary:')), isTrue);
    });
  });
}
