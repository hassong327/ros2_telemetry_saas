# ROS 2 Telemetry SaaS

ROS 2 로봇 텔레메트리를 Kafka로 전달하고 처리하는 실험용 저장소입니다. 현재는 Phase 0 저장소 골격이며, 실행 가능한 파이프라인은 Phase 1에서 추가합니다. 설계와 단계별 계획은 [계획서](docs/plan.md), 현재 저장소 적용 방안은 [적용안](docs/repo-application.md)을 참고하세요.

## 요구사항

- Docker Engine과 Docker Compose CLI plugin v2.24 이상
- `make` (호스트에서 Makefile 타깃 실행용)
- Docker context `default` (native Docker Engine). Docker Desktop context에서는 이후 네트워크 실험 결과가 달라질 수 있습니다.

실제로 사용되는 Compose plugin과 Docker context를 다음 명령으로 확인하세요.

```sh
docker compose version
docker context show
```

호스트에 `/opt/ros/humble`이 있더라도 **Humble을 source하지 마세요**. 이 프로젝트의 ROS 버전은 Jazzy이며 ROS 코드는 Jazzy 컨테이너 안에서만 실행합니다.

## 시작하기

```sh
cp -f .env.example .env
make config
```

`.env`의 이미지 placeholder는 이미지 버전 고정 작업에서 실제 태그로 바뀔 예정입니다. 현재 `compose.yml`이 없어 `make config`는 안내 메시지를 출력합니다. Compose 구성이 추가되면 `make config`로 설정을 확인하고 `make up`으로 서비스를 시작할 수 있습니다.

Makefile은 `up`, `down`, `logs`, `consume`, `smoke`, `test`, `config` 타깃을 제공합니다. Phase 1 파일이 아직 없는 타깃은 안내 메시지를 출력합니다. `make down`은 Compose 구성이 있을 때 `docker compose down -v`를 실행하므로 데이터 볼륨도 삭제합니다.
