import 'package:flutter_test/flutter_test.dart';
import 'package:app/brain/services/persona_service.dart';
import 'package:app/brain/services/planner_service.dart';

void main() {
  test('persona systemPrompt contains name', () {
    final p = PersonaService(name: 'Jenny', briefDescription: 'Helpful.');
    expect(p.systemPrompt(), contains('Jenny'));
  });

  test('planner returns a plan', () async {
    final planner = PlannerService();
    final plan = await planner.createPlan('Test goal');
    expect(plan, contains('Plan for'));
  });
}
