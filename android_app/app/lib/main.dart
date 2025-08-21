import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

// Change this to your Render backend URL
const String backendBaseUrl = 'https://geny-1.onrender.com';

void main() {
  runApp(const GenyApp());
}

class GenyApp extends StatelessWidget {
  const GenyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Geny Chat',
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: Color(0xFF181A20),
        colorScheme: ColorScheme.dark(
          primary: Color(0xFF7F5AF0),
          secondary: Color(0xFF2CB67D),
          background: Color(0xFF181A20),
          surface: Color(0xFF181A20),
        ),
        textTheme: const TextTheme(
          bodyLarge: TextStyle(color: Colors.white, fontSize: 18),
          bodyMedium: TextStyle(color: Colors.white70, fontSize: 16),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Color(0xFF181A20),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(24),
            borderSide: BorderSide.none,
          ),
        ),
      ),
      home: const ChatScreen(),
    );
  }
}




class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> with SingleTickerProviderStateMixin {
  final List<_ChatMessage> _messages = [
    _ChatMessage(
      text: "Hi! I'm Geny. Ask me anything—I'll always try to give you a fresh, thoughtful answer. I love exploring new ideas and never repeat myself!",
      isGeny: true,
    ),
  ];
  final TextEditingController _controller = TextEditingController();
  bool _isWaiting = false;
  late TabController _tabController;

  bool _backendOk = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 5, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _sendMessage() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    setState(() {
      _messages.add(_ChatMessage(text: text, isGeny: false));
      _controller.clear();
      _isWaiting = true;
      _postToBackend(text);
    });
  }

  Future<void> _postToBackend(String text) async {
    try {
      final uri = Uri.parse('$backendBaseUrl/chat');
      final res = await http.post(uri, headers: {'Content-Type': 'application/json'}, body: jsonEncode({'message': text}));
      if (res.statusCode == 200) {
        final body = jsonDecode(res.body);
        final reply = body['reply'] ?? '[null]';
        setState(() {
          _messages.add(_ChatMessage(text: reply, isGeny: true));
          _isWaiting = false;
          _backendOk = true;
        });
      } else {
        setState(() {
          _messages.add(_ChatMessage(text: '[backend error ${res.statusCode}]', isGeny: true));
          _isWaiting = false;
          _backendOk = false;
        });
      }
    } catch (e) {
      setState(() {
        _messages.add(_ChatMessage(text: '[network error] $e', isGeny: true));
        _isWaiting = false;
        _backendOk = false;
      });
    }
  }

  Widget _buildChatTab() {
    return Column(
      children: [
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
            itemCount: _messages.length,
            itemBuilder: (context, index) {
              final msg = _messages[index];
              return Align(
                alignment: msg.isGeny ? Alignment.centerLeft : Alignment.centerRight,
                child: Container(
                  margin: EdgeInsets.only(
                    top: 6,
                    bottom: 6,
                    left: msg.isGeny ? 0 : 48,
                    right: msg.isGeny ? 48 : 0,
                  ),
                  padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 18),
                  decoration: BoxDecoration(
                    color: msg.isGeny
                        ? Theme.of(context).colorScheme.surface
                        : Theme.of(context).colorScheme.primary.withOpacity(0.8),
                    borderRadius: BorderRadius.circular(22),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.08),
                        blurRadius: 8,
                        offset: Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Text(
                    msg.text,
                    style: TextStyle(
                      color: msg.isGeny ? Colors.white : Colors.white,
                      fontSize: 16,
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        if (_isWaiting)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.start,
              children: const [
                SizedBox(width: 16),
                Text('Geny is typing...', style: TextStyle(color: Colors.white70)),
              ],
            ),
          ),
        Padding(
          padding: const EdgeInsets.fromLTRB(8, 0, 8, 16),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  enabled: !_isWaiting,
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(
                    hintText: 'Type a message...',
                    hintStyle: TextStyle(color: Colors.white54),
                    contentPadding: EdgeInsets.symmetric(
                        vertical: 14, horizontal: 20),
                  ),
                  onSubmitted: (_) => _sendMessage(),
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                icon: const Icon(Icons.send, color: Color(0xFF7F5AF0)),
                onPressed: _sendMessage,
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildInfoTab(String tab) {
    switch (tab) {
      case 'Story':
        return LifeTab();
      case 'Age':
        return AgeTab();
      case 'Status':
        return StatusTab();
      case 'Contact':
        return RelationsTab();
      default:
        return Center(child: Text('Unknown tab'));
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 5,
      child: Scaffold(
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          title: Row(
            children: [
              CircleAvatar(
                backgroundImage: AssetImage('assets/images/geny_avatar.png'),
                radius: 20,
                backgroundColor: Colors.grey[800],
              ),
              const SizedBox(width: 12),
              const Text('Geny', style: TextStyle(fontWeight: FontWeight.bold)),
            ],
          ),
          bottom: TabBar(
            controller: _tabController,
            tabs: const [
              Tab(text: 'Chat'),
              Tab(text: 'Story'),
              Tab(text: 'Age'),
              Tab(text: 'Status'),
              Tab(text: 'Contact'),
            ],
          ),
        ),

        body: TabBarView(
          controller: _tabController,
          children: [
            _buildChatTab(),
            _buildInfoTab('Story'),
            _buildInfoTab('Age'),
            _buildInfoTab('Status'),
            _buildInfoTab('Contact'),
          ],
        ),
      ),
    );
  }
}


// Livshistoria-tab
class LifeTab extends StatefulWidget {
  @override
  State<LifeTab> createState() => _LifeTabState();
}

class _LifeTabState extends State<LifeTab> {
  String? summary;
  List<String>? events;
  bool loading = false;
  String? error;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() { loading = true; error = null; });
    try {
      final uri = Uri.parse('$backendBaseUrl/life');
      final res = await http.get(uri);
      if (res.statusCode == 200) {
        final body = jsonDecode(res.body);
        setState(() {
          summary = body['summary'] ?? '';
          events = (body['events'] as List<dynamic>?)?.cast<String>() ?? [];
          loading = false;
        });
      } else {
        setState(() { error = 'Backend error (${res.statusCode})'; loading = false; });
      }
    } catch (e) {
      setState(() { error = 'Network error: $e'; loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Text('Life Story', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Colors.white)),
            const SizedBox(height: 12),
            if (loading)
              const CircularProgressIndicator()
            else if (error != null)
              Text(error!, style: TextStyle(color: Colors.red, fontSize: 16))
            else ...[
              if (summary != null)
                Text(summary!, style: TextStyle(fontSize: 16, color: Colors.white70)),
              const SizedBox(height: 16),
              if (events != null && events!.isNotEmpty) ...[
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text('Recent events:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
                ),
                const SizedBox(height: 8),
                ...events!.map((e) => ListTile(
                  leading: Icon(Icons.bolt, color: Colors.purpleAccent),
                  title: Text(e, style: TextStyle(color: Colors.white)),
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                )),
              ]
            ],
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: loading ? null : _fetch,
              child: const Text('Refresh'),
            ),
          ],
        ),
      ),
    );
  }
}

// Ålder-tab
class AgeTab extends StatefulWidget {
  @override
  State<AgeTab> createState() => _AgeTabState();
}

class _AgeTabState extends State<AgeTab> {
  Map<String, dynamic>? age;
  bool loading = false;
  String? error;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() { loading = true; error = null; });
    try {
      final uri = Uri.parse('$backendBaseUrl/age');
      final res = await http.get(uri);
      if (res.statusCode == 200) {
        setState(() {
          age = jsonDecode(res.body);
          loading = false;
        });
      } else {
        setState(() { error = 'Backend error (${res.statusCode})'; loading = false; });
      }
    } catch (e) {
      setState(() { error = 'Network error: $e'; loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('Age', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Colors.white)),
            const SizedBox(height: 16),
            if (loading)
              const CircularProgressIndicator()
            else if (error != null)
              Text(error!, style: TextStyle(color: Colors.red, fontSize: 16))
            else if (age != null) ...[
              Text('Geny was created:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
              const SizedBox(height: 8),
              Text(age!["created"]?.toString() ?? '', style: TextStyle(fontSize: 18, color: Colors.white70)),
              const SizedBox(height: 12),
              Text('Geny is:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
              const SizedBox(height: 8),
              Text(age!["age"]?.toString() ?? '', style: TextStyle(fontSize: 18, color: Colors.white70)),
            ],
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: loading ? null : _fetch,
              child: const Text('Refresh'),
            ),
          ],
        ),
      ),
    );
  }
}

// Status-tab
class StatusTab extends StatefulWidget {
  @override
  State<StatusTab> createState() => _StatusTabState();
}

class _StatusTabState extends State<StatusTab> {
  Map<String, dynamic>? status;
  bool loading = false;
  String? error;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() { loading = true; error = null; });
    try {
      final uri = Uri.parse('$backendBaseUrl/status');
      final res = await http.get(uri);
      if (res.statusCode == 200) {
        setState(() {
          status = jsonDecode(res.body);
          loading = false;
        });
      } else {
        setState(() { error = 'Backend error (${res.statusCode})'; loading = false; });
      }
    } catch (e) {
      setState(() { error = 'Network error: $e'; loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('Status', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Colors.white)),
            const SizedBox(height: 16),
            if (loading)
              const CircularProgressIndicator()
            else if (error != null)
              Text(error!, style: TextStyle(color: Colors.red, fontSize: 16))
            else if (status != null) ...[
              Text('Activity:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
              const SizedBox(height: 8),
              Text(status!["activity"] ?? '', style: TextStyle(fontSize: 18, color: Colors.white70)),
              const SizedBox(height: 12),
              Text('Mood:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
              const SizedBox(height: 8),
              Text(status!["mood"] ?? '', style: TextStyle(fontSize: 18, color: Colors.white70)),
            ],
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: loading ? null : _fetch,
              child: const Text('Refresh'),
            ),
          ],
        ),
      ),
    );
  }
}

// Relationer-tab
class RelationsTab extends StatefulWidget {
  @override
  State<RelationsTab> createState() => _RelationsTabState();
}

class _RelationsTabState extends State<RelationsTab> {
  List<dynamic>? relations;
  bool loading = false;
  String? error;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() { loading = true; error = null; });
    try {
      final uri = Uri.parse('$backendBaseUrl/relations');
      final res = await http.get(uri);
      if (res.statusCode == 200) {
        final body = jsonDecode(res.body);
        setState(() {
          relations = body['relations'] as List<dynamic>?;
          loading = false;
        });
      } else {
        setState(() { error = 'Backend error (${res.statusCode})'; loading = false; });
      }
    } catch (e) {
      setState(() { error = 'Network error: $e'; loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Text('Relations', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Colors.white)),
            const SizedBox(height: 16),
            if (loading)
              const CircularProgressIndicator()
            else if (error != null)
              Text(error!, style: TextStyle(color: Colors.red, fontSize: 16))
            else if (relations != null && relations!.isNotEmpty) ...[
              Align(
                alignment: Alignment.centerLeft,
                child: Text('Important relations:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
              ),
              const SizedBox(height: 8),
              ...relations!.map((r) => ListTile(
                leading: Icon(Icons.person, color: Colors.cyanAccent),
                title: Text(r, style: TextStyle(color: Colors.white)),
                dense: true,
                contentPadding: EdgeInsets.zero,
              )),
            ]
            else
              Text('No relations registered.', style: TextStyle(color: Colors.white70)),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: loading ? null : _fetch,
              child: const Text('Refresh'),
            ),
          ],
        ),
      ),
    );
  }
}


class _ChatMessage {
  final String text;
  final bool isGeny;
  _ChatMessage({required this.text, required this.isGeny});
}
