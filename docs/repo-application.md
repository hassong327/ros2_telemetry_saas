# 계획서 v2 → 현재 레포 적용 방안

> 대상: `ros2-saas-plan-revised.md` (이하 "계획서")
> 작성일: 2026-09-26
> 목적: 계획서를 분석해서 **보완할 점**을 정리하고, 빈 레포에서 **Phase 0 → Phase 1을 실제로 어떤 파일/명령으로 시작할지**를 구체화한다.

---

## 1. 현재 상태

### 1.1 레포

| 항목 | 상태 |
|---|---|
| 브랜치 | `main`, **커밋 없음** |
| 파일 | `ros2-saas-plan-revised.md` 1개 (untracked) |
| 레포 이름 | `ros2_telemetry_saas` (계획서 §16의 `ros2-saas/`와 다름 → 레포 루트를 그대로 사용) |

즉 계획서 Phase 0부터 시작하는 상태다.

### 1.2 호스트 환경 (실측)

| 항목 | 값 | 계획서와의 관계 |
|---|---|---|
| OS | Ubuntu 24.04.3, kernel 6.8 | 일치 |
| Docker | Engine 29.2, 기본 context = native (`/var/run/docker.sock`) | 일치. Docker Desktop context도 설치돼 있으니 **`default` context 사용 확인** 필요 (Desktop VM에서는 iptables/tc/route 실험 결과가 달라짐) |
| Compose | v2.39 | `!reset` / `!override` 태그 사용 가능 (§3.1 참고) |
| Python | 3.12 | `ros:jazzy` 컨테이너 Python도 3.12 |
| CPU / RAM | 16 core / 32 GB | Phase 5 한계 추정 기준 |
| 호스트 ROS | `/opt/ros/humble` 존재 | 계획서는 **Jazzy**. 호스트 ROS는 쓰지 않고 **모든 ROS 코드는 컨테이너에서만 실행**한다. 호스트 쉘에서 humble을 source한 채로 작업하면 혼동이 생기므로 주의 |

---

## 2. 계획서 분석

### 2.1 잘 된 점 (그대로 유지)

- Data plane / Control plane 분리와 Phase 순서(flat → network → persistence → anomaly → scale → SaaS → AWS)가 합리적이다.
- Kafka 순서 보장, idempotence ≠ exactly-once, NAT는 routing과 분리 실험 등 흔한 오해를 미리 정정해 두었다.
- 모든 실험을 수치(msg/s, p99, lag)로 기록하는 원칙과 실험 양식(§13)이 있다.
- key = `tenant_id:robot_id` 를 처음부터 쓴다.

### 2.2 보완이 필요한 점

구현에 들어가면 바로 부딪히는 것 위주로 정리했다. **(중요)** 표시는 설계를 바꿔야 하는 항목이다.

#### (중요) A. ROS2 메시지에는 `seq`가 없다

ROS2의 `std_msgs/Header`에는 ROS1과 달리 `seq` 필드가 없다. 계획서의 envelope `seq`와 Phase 4의 "drop → seq gap 탐지"는 **어디서 seq를 얻는지**가 정의되어 있지 않다.

선택지:

| 방식 | 장점 | 단점 |
|---|---|---|
| ① bridge가 stream별로 seq 부여 | 표준 메시지 그대로 사용, Phase 1에 가장 간단 | ROS 구간(publisher → bridge)의 drop이 seq gap으로 안 보임 |
| ② custom msg (`TelemetryImu { uint64 seq; sensor_msgs/Imu data }`) | 소스 기준 gap 탐지 가능, 정석 | ament_cmake 인터페이스 패키지 + colcon build 필요 |
| ③ `header.frame_id`에 seq 인코딩 (`imu_link#123`) | 빌드 없이 소스 seq 확보 | 편법. 실제 로봇 데이터에는 적용 불가 |

**권장:** Phase 1은 ①로 시작하고, Phase 4(drop/reorder 실험) 들어가기 전에 ②로 전환한다. envelope에는 처음부터 `seq_origin: "bridge" | "source"` 같은 필드를 두어 나중에 데이터 의미가 섞이지 않게 한다.

#### (중요) B. `message_id`가 재시작 시 충돌한다

계획서: `message_id = tenant:robot:stream:seq`.
publisher(또는 bridge)가 재시작하면 seq가 0부터 다시 시작하고, DB의 `message_id UNIQUE` 때문에 **새 데이터가 "중복"으로 조용히 버려진다.** 이는 원칙 6(silent drop 금지)에 정면으로 위배된다.

**수정:** seq를 부여하는 주체의 부팅마다 바뀌는 `boot_id`(UUID 또는 시작 시각 ns)를 추가한다.

```text
message_id = {tenant_id}:{robot_id}:{stream}:{boot_id}:{seq}
```

DB unique constraint도 `(tenant_id, robot_id, stream, boot_id, seq)`로 맞춘다.

#### (중요) C. 컨테이너 간 Fast DDS는 Shared Memory 때문에 데이터가 안 올 수 있다

Fast DDS는 같은 호스트라고 판단하면 SHM transport를 쓰려고 한다. 컨테이너별로 `/dev/shm`이 분리돼 있으면 **discovery는 되는데 데이터가 안 오는** 현상이 흔하다. 또한 이 프로젝트는 DDS 트래픽이 네트워크로 흐르는 것을 관찰(§4.6 tcpdump)해야 하므로 SHM은 오히려 방해가 된다.

**수정:** edge 컨테이너 공통 환경변수로 UDP만 쓰도록 고정한다.

```text
RMW_IMPLEMENTATION=rmw_fastrtps_cpp
FASTDDS_BUILTIN_TRANSPORTS=UDPv4
ROS_DOMAIN_ID=42
```

(`FASTDDS_BUILTIN_TRANSPORTS`는 Jazzy에 포함된 Fast DDS 2.x에서 지원. 구현 시 컨테이너 안에서 동작을 한 번 검증한다.)

#### D. `ros:jazzy` 컨테이너에서 pip 설치 (PEP 668)

Ubuntu 24.04 기반 이미지는 시스템 Python에 `pip install`을 막는다. `rclpy`는 시스템 site-packages에 있으므로 다음 중 하나를 쓴다.

```dockerfile
# 권장: rclpy가 보이는 venv
RUN python3 -m venv --system-site-packages /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
ENV PATH=/opt/venv/bin:$PATH
```

#### E. Bridge의 bounded queue는 librdkafka 큐를 먼저 활용

`confluent-kafka`의 `produce()`는 이미 비동기이고 내부에 bounded queue(`queue.buffering.max.messages`, `queue.buffering.max.kbytes`)가 있다. 큐가 차면 `BufferError`를 던진다.

**권장 (Phase 1):**
- ROS callback에서 직렬화 후 바로 `produce()` → `BufferError`면 `bridge_queue_drop_total` 증가
- 별도 스레드에서 `producer.poll(0.1)` 루프로 delivery callback 처리
- `bridge_queue_depth` = `len(producer)`

계획서 §7.1의 별도 Python queue + serializer 스테이지는 **Phase 5에서 disk spool/우선순위 drop이 필요해질 때** 추가한다. 처음부터 두 단계 큐를 두면 병목 위치를 해석하기 어려워진다.

#### F. Compose 파일 분할과 네트워크 교체

§16은 `compose.base.yml` + `compose.network.yml` 오버레이를 제안하지만, Compose는 `networks` 목록을 **병합(합집합)**하므로 Phase 1의 flat network를 오버레이로 "빼는 것"이 기본적으로 안 된다. Phase 2에서 bridge가 flat 네트워크에 계속 붙어 있으면 router를 우회해서 실험이 무효가 된다(계획서 §17 "Docker network 우회" 리스크 그대로).

**수정:** 오버레이에서 `!reset`/`!override`를 사용한다 (Compose v2.24+, 현재 v2.39).

```yaml
# compose/compose.network.yml
services:
  bridge:
    networks: !override
      edge_lan:
        ipv4_address: 192.168.10.10
```

그리고 `scripts/verify_network.sh`에 "bridge 컨테이너가 붙은 네트워크가 정확히 `edge_lan` 하나인가"를 `docker inspect`로 검사하는 항목을 넣는다.

#### G. Phase 2 라우팅에 필요한 권한/설정이 빠져 있다

- router: `cap_add: [NET_ADMIN]`, `sysctls: { net.ipv4.ip_forward: 1 }`
- edge/server 컨테이너에서 `ip route add ... via router`를 하려면 해당 컨테이너에도 `NET_ADMIN`이 필요하다. 앱 컨테이너에 권한을 주기 싫다면 **route 설정 전용 sidecar**(같은 network namespace, `network_mode: service:bridge`)로 분리하는 방법도 있다.
- Docker는 각 서브넷의 `.1`을 gateway로 예약한다. router에 `.254`를 준 계획서 IP는 충돌이 없다.
- `internal: true` 네트워크에서 default route가 어떻게 잡히는지는 Docker 버전별로 다르므로 Phase 2 시작 시 `ip route`로 먼저 확인한다 (계획서 §22 항목과 동일).

#### H. Kafka 이미지 / UI 선택 구체화

| 항목 | 권장 | 이유 |
|---|---|---|
| Kafka | `apache/kafka:<고정 버전>` (공식 이미지, KRaft 전용) | Kafka 4.x부터 ZooKeeper 제거. 벤더 이미지 대비 설정이 문서와 1:1 |
| Kafka UI | `kafbat/kafka-ui:<고정 버전>` | 기존 `provectus/kafka-ui`는 유지보수 중단, kafbat이 후속 fork |
| topic 생성 | `auto.create.topics.enable=false` + init 컨테이너에서 `kafka-topics.sh --create` | 파티션 수를 계획서 §6.2대로 고정. 오타 topic이 자동 생성되는 사고 방지 |

Kafka listener는 Phase 1부터 두 개로 나눈다.

```text
INTERNAL://kafka:9092     # 컨테이너 간 (bridge, processor)
EXTERNAL://localhost:9094 # 호스트에서 kcat/디버깅용
```

Phase 2에서 INTERNAL 광고 주소를 `10.0.0.10:9092`로 바꾸면 edge에서 route 가능한 주소가 되고, 계획서 §4.4 firewall 규칙(9092/9094)과도 맞는다.

#### I. 공용 스키마 모듈이 없다

envelope 생성(bridge)과 검증(processor)이 같은 정의를 써야 하는데 디렉토리 구조에 공용 위치가 없다. ROS 의존성이 없는 순수 Python 패키지로 분리하면 **호스트에서 ROS 없이 pytest**가 가능하다.

```text
common/telemetry_schema/   # envelope dataclass, message_id, 직렬화, 검증
```

#### J. ROS 패키지화는 늦춰도 된다

`dummy_pub`을 처음부터 ament_python 패키지(`package.xml`, `setup.py`, colcon build)로 만들 필요는 없다. `source /opt/ros/jazzy/setup.bash && python3 -m dummy_pub` 로 충분하다. colcon 빌드는 A-②(custom msg)가 필요해지는 시점에 도입한다.

#### K. 기타

- `ros2-saas-plan-revised.md`는 계획서 §16대로 `docs/plan.md`로 옮겨 첫 커밋에 포함한다.
- 계획서 §5.1 IMU 100Hz × 500 robot = 50k msg/s는 Python rclpy 단일 프로세스로는 어렵다. Phase 5 load는 Mode B(1 process = N logical robots)라도 **여러 process로 샤딩**하는 구조를 전제로 한다. 16 core 호스트에서 Kafka/DB/Grafana와 CPU를 나눠 쓰므로, 실험 컨테이너에는 `cpus:` 제한을 걸어 결과를 재현 가능하게 한다.

---

## 3. 레포 적용안

### 3.1 Phase 0~1에서 만들 구조

계획서 §16 전체를 한 번에 만들지 않고, **Phase 1까지 필요한 것만** 만든다. 나머지 디렉토리는 해당 Phase에서 추가한다.

```text
ros2_telemetry_saas/
├── README.md                  # 실행 방법 (make up / make smoke)
├── .gitignore                 # .env, __pycache__, .venv, spool 등
├── .env.example               # 이미지 태그, ROS_DOMAIN_ID, KAFKA 설정
├── Makefile
├── compose.yml                # Phase 1: flat network 단일 파일
├── docs/
│   ├── plan.md                # ← ros2-saas-plan-revised.md 이동
│   ├── repo-application.md    # 이 문서
│   └── experiments/
├── common/
│   └── telemetry_schema/
│       ├── pyproject.toml
│       ├── src/telemetry_schema/
│       │   ├── __init__.py
│       │   └── envelope.py    # Envelope, make_message_id, to_json/from_json, validate
│       └── tests/
│           └── test_envelope.py
├── edge/
│   ├── Dockerfile             # ros:jazzy-<pinned> + venv(--system-site-packages)
│   ├── requirements.txt       # confluent-kafka, prometheus-client
│   ├── dummy_pub/
│   │   └── __main__.py        # robot_001 IMU 100Hz
│   └── bridge/
│       ├── __main__.py        # subscribe → envelope → produce
│       └── metrics.py
├── kafka/
│   └── create-topics.sh       # init 컨테이너에서 실행
└── scripts/
    └── smoke_test.sh
```

- `dummy_pub`과 `bridge`는 같은 edge 이미지 하나를 쓰고 `command`만 다르게 한다 (빌드 시간 절약, 버전 일치).
- `compose.yml`은 Phase 2에서 `compose/compose.base.yml` 등으로 분할한다. 그 전까지는 단일 파일이 디버깅에 유리하다.

### 3.2 `.env.example` 초안

```bash
# 이미지 — latest 금지. 구현 시점에 존재하는 태그로 고정
ROS_IMAGE=ros:jazzy-ros-base-noble
KAFKA_IMAGE=apache/kafka:<pinned>
KAFKA_UI_IMAGE=kafbat/kafka-ui:<pinned>

# ROS / DDS
ROS_DOMAIN_ID=42
RMW_IMPLEMENTATION=rmw_fastrtps_cpp
FASTDDS_BUILTIN_TRANSPORTS=UDPv4

# Identity
TENANT_ID=demo-factory
ROBOT_ID=robot_001

# Kafka
KAFKA_BOOTSTRAP=kafka:9092
```

`ROS_IMAGE`는 날짜가 들어간 digest(`ros@sha256:...`)로 고정하면 더 엄밀하다. `make pin` 같은 타깃으로 현재 digest를 기록해 두는 것을 권장한다.

### 3.3 Envelope v1 (수정안)

계획서 §6.1 대비 변경점: `boot_id`, `seq_origin` 추가, `message_id` 형식 변경.

```json
{
  "schema_version": 1,
  "tenant_id": "demo-factory",
  "robot_id": "robot_001",
  "stream": "imu",
  "boot_id": "01J8Z...",
  "seq": 102934,
  "seq_origin": "bridge",
  "source_ts_ns": 1790000000000000000,
  "bridge_rx_ts_ns": 1790000000000200000,
  "message_id": "demo-factory:robot_001:imu:01J8Z...:102934",
  "payload": { "ax": 0.01, "ay": -0.02, "az": 9.81 }
}
```

- `source_ts_ns` = `msg.header.stamp` (dummy_pub에서 `node.get_clock().now()`로 채움)
- `bridge_rx_ts_ns` = bridge callback 진입 시 `time.time_ns()`
- Kafka key = `tenant_id:robot_id` (계획서 그대로)

### 3.4 Makefile 타깃

```text
make up          # docker compose up -d --build
make down        # docker compose down -v
make logs        # bridge / dummy_pub 로그 follow
make consume     # telemetry.raw.imu 를 console consumer로 tail
make smoke       # scripts/smoke_test.sh
make test        # common/ 단위 테스트 (호스트, ROS 불필요)
make config      # docker compose config (Phase 0 완료 기준)
```

### 3.5 작업 순서와 완료 확인

계획서 §20의 Step 1~7을 레포 작업 단위로 풀었다. 각 단계는 커밋 1개를 목표로 한다.

| # | 작업 | 산출 파일 | 완료 확인 |
|---|---|---|---|
| 1 | 레포 골격 | `.gitignore`, `.env.example`, `README.md`, `Makefile`, `docs/plan.md`(이동) | `git log` 첫 커밋 존재 |
| 2 | Docker 환경 검증 | — | `docker context show` = `default`, `docker run --rm $ROS_IMAGE ros2 topic list` 동작 |
| 3 | 공용 스키마 | `common/telemetry_schema/*` | `make test` 통과 (message_id 형식, boot_id 포함, NaN 거부 등) |
| 4 | edge 이미지 | `edge/Dockerfile`, `edge/requirements.txt` | 컨테이너 안에서 `python -c "import rclpy, confluent_kafka"` 성공 |
| 5 | dummy_pub | `edge/dummy_pub/__main__.py` | `ros2 topic hz /robot_001/imu` ≈ 100Hz (bridge 컨테이너에서 실행 → 컨테이너 간 DDS 확인) |
| 6 | Kafka 단일 broker + topic init | `compose.yml`, `kafka/create-topics.sh` | `kafka-topics.sh --describe`에서 `telemetry.raw.imu` partitions=6 |
| 7 | bridge produce | `edge/bridge/__main__.py` | `make consume`에서 JSON 수신, seq 증가 |
| 8 | bridge metric | `edge/bridge/metrics.py` | `curl bridge:9100/metrics`에 `bridge_*` 6종 노출 |
| 9 | smoke test | `scripts/smoke_test.sh` | up → 10초 대기 → 메시지 N개 이상 확인 → exit 0 |

Phase 1 완료 기준(계획서 §11)에 다음을 추가한다.

- [ ] bridge 재시작 후 `boot_id`가 바뀌고 `message_id` 충돌이 없다
- [ ] Kafka를 `docker compose stop kafka` 했을 때 bridge 메모리가 bounded이고 `bridge_queue_drop_total`이 증가한다
- [ ] Kafka 재기동 후 bridge가 자동 재연결된다

### 3.6 Phase 2 진입 시 할 일 (미리 메모)

1. `compose.yml` → `compose/compose.base.yml` + `compose.network.yml` 분할, 오버레이에 `networks: !override` 사용 (§2.2-F)
2. router 이미지 (`iproute2`(`ip`, `tc`), `iptables`/`nftables`, `tcpdump`, `traceroute`) + `NET_ADMIN`, `ip_forward` (§2.2-G)
3. Kafka INTERNAL advertised listener를 `10.0.0.10:9092`로 변경 (§2.2-H)
4. `scripts/verify_network.sh`: 계획서 §4.8 체크리스트 + "bridge가 붙은 네트워크 = edge_lan 하나" 검사
5. DDS 누출 확인: server_lan 쪽 컨테이너에서 `tcpdump -ni any udp portrange 7400-7600` 결과 0 packet

---

## 4. 결정이 필요한 항목

구현 전에 정해 두면 좋은 것. 괄호 안은 이 문서의 기본 권장값이다.

| 항목 | 선택지 | 권장 |
|---|---|---|
| seq 출처 | bridge / custom msg / frame_id | Phase 1 bridge → Phase 4 전 custom msg |
| boot_id 형식 | UUID4 / ULID / 시작 ns | ULID (정렬 가능, 로그에서 읽기 쉬움) |
| Kafka 버전 | 3.9 / 4.x | 4.x (KRaft 전용, ZooKeeper 개념 학습 불필요) |
| Python 의존성 관리 | requirements.txt / uv | Phase 1은 requirements.txt, 서비스가 늘면 uv |
| CI | 없음 / GitHub Actions | 스키마 단위 테스트 + `docker compose config`만 먼저 |

---

## 5. 요약

1. 계획서의 방향과 Phase 구성은 유지한다.
2. 구현 전에 **seq 출처(A), message_id 충돌(B), Fast DDS SHM(C)** 세 가지는 설계를 수정한다. 셋 다 고치지 않으면 Phase 1~4에서 "데이터가 안 온다" 또는 "데이터가 조용히 사라진다" 형태로 나타난다.
3. 레포는 빈 상태이므로 §3.5의 1~9번을 순서대로 커밋하면 계획서 Phase 0~1이 끝난다.
4. Compose 분할, router 권한, listener 변경은 Phase 2 진입 시 §3.6대로 처리한다.
