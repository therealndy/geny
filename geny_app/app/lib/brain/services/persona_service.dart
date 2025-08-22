// Minimal PersonaService stub

class PersonaService {
  final String name;
  final String briefDescription;

  PersonaService({this.name = 'Jenny', this.briefDescription = 'Curious and helpful assistant.'});

  String systemPrompt() {
    return 'You are $name. $briefDescription';
  }
}
