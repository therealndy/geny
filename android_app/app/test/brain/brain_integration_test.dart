import 'package:flutter_test/flutter_test.dart';
import 'package:app/brain/providers/brain_provider.dart';
import 'package:app/brain/services/memory_service.dart';
import 'package:app/brain/services/persona_service.dart';
import 'package:app/brain/services/planner_service.dart';
import 'package:app/brain/services/safety_service.dart';
import 'package:app/brain/services/thought_loop_service.dart';

class FakePlannerService extends PlannerService {
  @override
  Future<String> createPlan(String goal) async {
    return 'We should kill the old plan for $goal';
  }
}

void main() {
  test('BrainProvider.plan enforces safety on planner output', () async {
    final memory = MemoryService();
    final persona = PersonaService(name: 'Jenny', briefDescription: 'Helpful.');
    final planner = FakePlannerService();
    final thoughtLoop = ThoughtLoopService();
    final safety = SafetyService();

    final provider = BrainProvider(
      memoryService: memory,
      personaService: persona,
      plannerService: planner,
      thoughtLoopService: thoughtLoop,
      safetyService: safety,
    );

    final result = await provider.plan('testing');
    expect(result, isNot(contains('kill')));
    expect(result, contains('[redacted]'));
  });
}
