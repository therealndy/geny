// Core DTOs for Jenny Brain v1

// No Flutter-only APIs required here.

enum MemoryType { episodic, semantic, procedural }

class MemoryItem {
  final String id;
  final MemoryType type;
  final String content;
  final DateTime timestamp;

  MemoryItem({
    required this.id,
    required this.type,
    required this.content,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();

  Map<String, dynamic> toJson() => {
    'id': id,
    'type': type.name,
    'content': content,
    'timestamp': timestamp.toIso8601String(),
  };

  factory MemoryItem.fromJson(Map<String, dynamic> json) {
    final typeStr = json['type'] as String? ?? 'episodic';
    MemoryType parsed = MemoryType.episodic;
    for (var v in MemoryType.values) {
      if (v.name == typeStr) parsed = v;
    }
    return MemoryItem(
      id: json['id'] as String,
      type: parsed,
      content: json['content'] as String,
      timestamp: DateTime.parse(json['timestamp'] as String),
    );
  }
}
