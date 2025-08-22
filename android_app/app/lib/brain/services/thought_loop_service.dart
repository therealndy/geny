// Minimal ThoughtLoop (metacognition) service

import '../../shared/models/core.dart';

class ThoughtLoopService {
  ThoughtLoopService();

  /// Reflect on an input thought or recent interaction and return a list of
  /// observations/actions the brain may take.
  ///
  /// Argument [input] is required and must be a non-empty string.
  /// Optionally takes [recentMemories] to produce memory-aware reflections.
  Future<List<String>> reflect(String input, {List<MemoryItem>? recentMemories}) async {
    if (input.trim().isEmpty) {
      throw ArgumentError('input must be a non-empty string');
    }
    // Placeholder: simple tokenization + lightweight reflections
    await Future.delayed(const Duration(milliseconds: 30));
    final reflections = <String>[];
    reflections.add('Noticed input length: ${input.length}');
    if (input.length < 20) {
      reflections.add('Input is short — ask a clarifying question');
    }
    if (input.contains('?')) {
      reflections.add('User asked a question — prioritize answering');
    }
    if (recentMemories != null && recentMemories.isNotEmpty) {
      reflections.add('Referenced ${recentMemories.length} recent memory/items');
      // produce a tiny summary of memory types and timestamps
      final types = <String>{};
      for (var m in recentMemories) {
        types.add(m.type.toString().split('.').last);
      }
      final oldest = recentMemories.last.timestamp;
      final newest = recentMemories.first.timestamp;
      reflections.add(
        'Memory summary: types=${types.join(',')}, newest=${newest.toIso8601String()}, oldest=${oldest.toIso8601String()}',
      );
    }
    reflections.add('Proposed next action: summarize and ask for more details');
    return reflections;
  }
}
