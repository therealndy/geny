// Minimal MemoryService stub for Jenny Brain v1

import 'dart:async';

import 'package:hive/hive.dart';
import '../../shared/models/core.dart';

class MemoryService {
  final String boxName;
  Box? _box;

  MemoryService({this.boxName = 'jenny_memory'});

  Future<void> init() async {
    // The caller must have initialized Hive and registered adapters if needed.
    _box = await Hive.openBox(boxName);
  }

  Future<void> saveMemory(MemoryItem item) async {
    if (_box == null) throw StateError('MemoryService not initialized');
    await _box!.put(item.id, item.toJson());
  }

  List<MemoryItem> getAll() {
    if (_box == null) return [];
    return _box!.values.map((e) => MemoryItem.fromJson(Map<String, dynamic>.from(e))).toList();
  }
}
