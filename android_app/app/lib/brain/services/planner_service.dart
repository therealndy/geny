// Minimal PlannerService stub

class PlannerService {
  PlannerService();

  Future<String> createPlan(String goal) async {
    // Very small placeholder plan
    await Future.delayed(Duration(milliseconds: 50));
    return 'Plan for "$goal": 1) Clarify the goal. 2) Break into steps. 3) Execute step 1.';
  }
}
