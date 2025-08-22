import 'package:flutter/material.dart';
import '../services/memory_service.dart';
import '../services/persona_service.dart';
import '../services/planner_service.dart';

/// Central provider that exposes brain services to the widget tree.
class BrainProvider extends ChangeNotifier {
  final MemoryService memoryService;
  final PersonaService personaService;
  final PlannerService plannerService;

  BrainProvider({
    required this.memoryService,
    required this.personaService,
    required this.plannerService,
  });

  /// Initialize all services (e.g., open Hive boxes)
  Future<void> init() async {
    await memoryService.init();
    // persona and planner might have async init later
  }

  // Example action that delegates to planner
  Future<String> plan(String goal) async {
    final plan = await plannerService.createPlan(goal);
    notifyListeners();
    return plan;
  }
}
