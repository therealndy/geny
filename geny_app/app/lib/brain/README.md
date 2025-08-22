Jenny Brain v1 - Flutter brain modules

This directory contains starting scaffolding for the Jenny Brain (v1) agent.

Planned modules:
- perception
- memory (uses Hive)
- persona
- metacognition (thought loop)
- planner
- safety
- messenger
- simulator

Use `scripts/setup_jenny.sh` from the repo root to run `flutter pub get` in the Flutter project: `./scripts/setup_jenny.sh geny_app/app`

Next steps:
- Add Provider wiring and Service locators under lib/brain
- Implement Persona + Planner + ThoughtLoop skeletons
- Add unit tests under test/ for each module
