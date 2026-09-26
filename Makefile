.PHONY: up down logs consume smoke test config

up:
	@if [ -f compose.yml ]; then docker compose up -d --build; else echo "compose.yml is not available yet (Phase 1)."; fi

down:
	@if [ -f compose.yml ]; then docker compose down -v; else echo "compose.yml is not available yet (Phase 1)."; fi

logs:
	@if [ -f compose.yml ]; then docker compose logs -f bridge dummy_pub; else echo "compose.yml is not available yet (Phase 1)."; fi

consume:
	@if [ -f compose.yml ]; then docker compose exec kafka kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic telemetry.raw.imu --from-beginning; else echo "compose.yml is not available yet (Phase 1)."; fi

smoke:
	@if [ -f scripts/smoke_test.sh ]; then bash scripts/smoke_test.sh; else echo "scripts/smoke_test.sh is not available yet (Phase 1)."; fi

test:
	@if [ -d common/telemetry_schema/tests ]; then python3 -m pytest common/telemetry_schema/tests; else echo "Common schema tests are not available yet (Phase 1)."; fi

config:
	@if [ -f compose.yml ]; then docker compose config; else echo "compose.yml is not available yet; docker compose config will run after Phase 1 adds it."; fi
