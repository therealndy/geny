import 'package:flutter/material.dart';
import '../services/memory_service.dart';
import '../services/persona_service.dart';
import '../services/planner_service.dart';
import '../services/thought_loop_service.dart';
import '../services/safety_service.dart';
import '../../shared/models/core.dart';

/// Central provider that exposes brain services to the widget tree.
class BrainProvider extends ChangeNotifier {
  final MemoryService memoryService;
  final PersonaService personaService;
  final PlannerService plannerService;
  final ThoughtLoopService thoughtLoopService;
  final SafetyService safetyService;

  BrainProvider({
    required this.memoryService,
    required this.personaService,
  required this.plannerService,
  required this.thoughtLoopService,
  required this.safetyService,
  });

  /// Initialize all services (e.g., open Hive boxes)
  Future<void> init() async {
    await memoryService.init();
  // persona, planner, thoughtLoop and safety might have async init later
  }

  // Example action that delegates to planner
  Future<String> plan(String goal) async {
    final plan = await plannerService.createPlan(goal);
    // Enforce safety on planner's output before returning
    final safe = await safetyService.enforce(plan);
    notifyListeners();
    return safe;
  }

  Future<List<String>> reflect(String input, {int lastN = 5}) async {
    // Get last N memories (safely) to pass into the thought loop
  final List<MemoryItem> all = memoryService.getAll();
  final List<MemoryItem> recent = lastN <= 0 ? <MemoryItem>[] : all.reversed.take(lastN).toList().cast<MemoryItem>();
  return await thoughtLoopService.reflect(input, recentMemories: recent);
  }

  Future<String> enforceSafety(String candidate) async {
    return await safetyService.enforce(candidate);
  }
}
