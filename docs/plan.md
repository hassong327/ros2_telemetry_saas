# ROS2 Telemetry SaaS — 프로젝트 계획서 v2

> 로봇/엣지의 ROS2 토픽을 사설망(OT/LAN)에서 수집하고, 라우터/방화벽/VPN 경계를 거쳐 Kafka 기반 서버로 전달한 뒤 저장·시각화·이상치 탐지·대규모 트래픽 실험까지 수행하는 학습 프로젝트.
>
> 1차는 **Docker로 로컬에 가상 회사 네트워크와 데이터 파이프라인을 구성**하고, 2차는 **SaaS control plane**을 추가하며, 3차는 **AWS 및 선택적 실물 네트워크 환경**으로 확장한다.

---

## 0. 이 프로젝트를 한 문장으로 정의

이 프로젝트는 단순한 ROS2 → Kafka 브릿지가 아니라 다음 두 부분을 함께 학습하는 프로젝트다.

1. **Data Plane**
   - ROS2 센서 데이터 수집
   - Kafka 전달
   - 스트림 처리
   - 시계열 저장
   - 이상치 탐지
   - 대규모 트래픽/장애 처리

2. **Control Plane**
   - Tenant 등록
   - Robot/Device 등록
   - 인증 정보 발급
   - Tenant별 데이터 격리
   - 대시보드 접근 제어
   - 사용량/상태 조회

> **중요:** 원래 계획만 구현하면 훌륭한 telemetry pipeline이지만, 엄밀한 의미의 SaaS라고 하기에는 부족하다. SaaS 학습을 위해 Phase 6부터 control plane을 명시적으로 추가한다.

---

# 1. 목표

| # | 경험하고 싶은 것 | 이 프로젝트에서 하는 일 | 해당 Phase |
|---|---|---|---|
| 1 | AWS 기반 SaaS 개발 | 로컬 시스템을 AWS VPC/MSK/ECS/RDS 등으로 이전하고 tenant/device 관리 API 구현 | Phase 6~7 |
| 2 | 기업형 사설망 경험 | Docker로 OT망·서버망을 분리하고 라우팅/방화벽/NAT/VPN을 실습 | Phase 2, 8 |
| 3 | Kafka 대규모 트래픽 처리 | 파티션·consumer group·batch·compression·replication·failover 실험 | Phase 1, 5 |
| 4 | 더미 데이터 이상치 처리 | spike/drop/NaN/stuck/reorder/delay/duplicate를 주입하고 탐지·정제 | Phase 4 |
| 5 | 트래픽 폭증 해결 | 가상 로봇 수를 단계적으로 증가시키며 병목 분석·백프레셔·스케일아웃 실험 | Phase 5 |
| 6 | 장애 복구 경험 | 네트워크 단절, Kafka broker 재시작, processor crash, DB 장애를 주입 | Phase 5 |
| 7 | 멀티테넌트 SaaS 구조 | tenant/device registry, 인증, tenant별 데이터 격리 | Phase 6 |

---

## 1.1 이번 프로젝트에서 배우려는 네트워크 개념

이 프로젝트에서 말하는 "기업형 네트워크"를 다음처럼 구체화한다.

- Ethernet / IP 기본
- 서브넷과 라우팅
- Default gateway
- L3 network segmentation
- 방화벽 정책
- NAT / DNAT
- 사설망과 공인망의 차이
- OT(로봇/공장)망과 서버망 분리
- Site-to-Site VPN 개념
- 선택적으로 VLAN
- 장애 환경에서의 지연/손실/대역폭 제한

> Docker bridge network는 실제 스위치/VLAN/물리 NIC를 완전히 재현하는 것은 아니다. Phase 2는 **L3 라우팅·방화벽·NAT 개념 학습용 에뮬레이션**이고, 실제 Ethernet/VLAN/공유기 경험은 Phase 8에서 별도로 수행한다.

---

## 1.2 1차 범위 밖

초기 단계에서는 다음은 하지 않는다.

- 실제 로봇(QCar2) 연결
- Kubernetes 운영
- ML 기반 이상치 탐지
- 프로덕션급 HA 데이터베이스
- 여러 AWS Region
- 완전한 결제 시스템

단, 아래 항목은 **나중으로 미루는 것이지 프로젝트에서 완전히 제외하지 않는다.**

- 실제 공유기 / VLAN / 물리 NIC 실습 → Phase 8
- 인증 / 멀티테넌시 → Phase 6
- TLS / Kafka 인증 → Phase 6~7

---

# 2. 개발 환경

| 항목 | 선택 | 비고 |
|---|---|---|
| OS | Ubuntu 24.04 | Docker 네이티브 실행 |
| ROS2 | Jazzy | `ros:jazzy` 이미지 사용 |
| RMW | Fast DDS | ROS2 기본 RMW, edge LAN 내부에서만 사용 |
| 컨테이너 | Docker Engine + Docker Compose v2 | 모든 이미지 버전 고정 |
| Kafka | Apache Kafka KRaft | ZooKeeper 없이 시작 |
| 언어 | Python 3 | `rclpy`, `confluent-kafka`, FastAPI |
| DB | PostgreSQL + TimescaleDB (로컬) | 시계열 실습용 |
| 시각화 | Grafana | telemetry / anomaly / system metrics |
| Metrics | Prometheus | application / Kafka / host metrics |
| Logs | stdout → Docker logs | 이후 Loki/OpenSearch 선택 |
| Kafka UI | Kafka UI | topic/partition/consumer 상태 확인 |
| 네트워크 도구 | iproute2, iptables/nftables, tc, tcpdump, traceroute | router/debug 컨테이너 |
| 테스트 | pytest + integration test shell scripts | 단계별 자동 검증 |
| IaC | Terraform | AWS Phase부터 사용 |

### 버전 정책

`latest` 태그는 사용하지 않는다.

예:

```text
ROS_IMAGE=ros:jazzy-...
KAFKA_IMAGE=<vendor>:<fixed-version>
POSTGRES_IMAGE=postgres:<fixed-major>
GRAFANA_IMAGE=grafana/grafana:<fixed-version>
```

모든 버전은 `.env` 또는 Compose 변수로 관리한다.

---

# 3. 전체 아키텍처

## 3.1 Local Data Plane

```text
┌──────────────── edge_lan / OT LAN ────────────────┐
│                                                   │
│  dummy robots                                     │
│  /robot_xxx/imu                                   │
│  /robot_xxx/odom                                  │
│  /robot_xxx/battery                               │
│           │                                       │
│           │ DDS / ROS2                            │
│           ▼                                       │
│  ros2_kafka_bridge                                │
│     ├─ bounded memory queue                       │
│     ├─ Kafka producer                             │
│     └─ optional disk spool                        │
└──────────────┬────────────────────────────────────┘
               │
               │ TCP/Kafka only
               ▼
       ┌───────────────┐
       │ router/firewall│
       │ route + NAT    │
       │ tc/netem       │
       └───────┬───────┘
               │
               ▼
┌──────────────── server_lan ───────────────────────┐
│                                                  │
│ Kafka                                            │
│   │                                              │
│   ├── telemetry.raw.*                            │
│   │          │                                   │
│   │          ▼                                   │
│   │      processor                               │
│   │      ├─ validation                           │
│   │      ├─ dedup                                │
│   │      ├─ anomaly detection                    │
│   │      └─ normalization                        │
│   │          │                                   │
│   │          ├─ telemetry.clean                  │
│   │          ├─ telemetry.anomaly                │
│   │          └─ telemetry.dlq                    │
│   │                                              │
│   ▼                                              │
│ TimescaleDB / PostgreSQL                         │
│   │                                              │
│   ▼                                              │
│ Grafana                                          │
│                                                  │
│ Prometheus / Kafka UI                            │
└──────────────────────────────────────────────────┘
```

---

## 3.2 SaaS 확장 후 논리 구조

```text
                    ┌─────────────── SaaS Control Plane ───────────────┐
User / Admin ─────► │ API / Auth                                      │
                    │  ├─ tenants                                     │
                    │  ├─ devices                                     │
                    │  ├─ credentials                                 │
                    │  ├─ dashboard permissions                       │
                    │  └─ usage/status                                │
                    └─────────────────┬────────────────────────────────┘
                                      │
                                      ▼
                         tenant / device metadata DB

                                      │
                                      │ identity / ACL
                                      ▼
┌────────────── Data Plane ──────────────────────────────────────────────┐
│ edge bridge → Kafka → processor → telemetry DB → dashboard            │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 3.3 핵심 설계 원칙

1. ROS2 DDS discovery와 sensor traffic은 edge LAN 내부에 가둔다.
2. 네트워크 경계를 넘는 데이터 프로토콜은 Kafka/TCP로 제한한다.
3. edge와 server는 직접 Docker network를 공유하지 않는다.
4. 라우팅/방화벽 정책을 통과한 트래픽만 허용한다.
5. bridge가 서버 장애 때문에 무한히 메모리를 사용하지 않도록 bounded queue를 둔다.
6. 처리 실패는 silent drop 하지 않고 DLQ 또는 명시적 drop metric으로 남긴다.
7. tenant와 robot identity는 모든 이벤트에 포함한다.
8. 데이터 처리 성능은 반드시 수치로 측정한다.

---

# 4. 네트워크 설계

## 4.1 네트워크

| 네트워크 | 예시 서브넷 | 역할 | 참여 서비스 |
|---|---|---|---|
| `edge_lan` | `192.168.10.0/24` | OT/로봇 사설망 | dummy_pub, bridge, router |
| `server_lan` | `10.0.0.0/24` | 서버 사설망 | Kafka, processor, DB, Grafana, Prometheus, router |
| `wan` | `172.30.0.0/24` | 호스트/외부 접근 경로 | router |

`edge_lan`과 `server_lan`은 `internal: true`로 구성한다.

> Docker의 `internal: true`는 외부 연결을 차단하는 네트워크이므로, 컨테이너 간 라우팅을 실험할 때는 반드시 실제 route table과 router namespace에서 forwarding이 제대로 작동하는지 확인해야 한다.

---

## 4.2 예시 IP

| 컴포넌트 | IP |
|---|---|
| router.edge | `192.168.10.254` |
| router.server | `10.0.0.254` |
| bridge | `192.168.10.10` |
| kafka-1 | `10.0.0.10` |
| grafana | `10.0.0.20` |
| db | `10.0.0.30` |

Kafka 다중 broker 실험에서는 예를 들어:

```text
kafka-1 = 10.0.0.10
kafka-2 = 10.0.0.11
kafka-3 = 10.0.0.12
```

---

## 4.3 라우팅 모드

처음부터 NAT와 routing을 섞지 말고 두 단계로 나눈다.

### Mode A — Pure Routing

```text
edge → router → server
server → router → edge
```

- edge에 `10.0.0.0/24 via 192.168.10.254`
- server 쪽에 `192.168.10.0/24 via 10.0.0.254`
- NAT 없음

이 모드에서 먼저 라우팅을 이해한다.

### Mode B — NAT 포함

edge → server 트래픽에 MASQUERADE/SNAT 적용.

이 모드에서 다음을 확인한다.

- 서버가 원래 robot/bridge source IP를 볼 수 있는가?
- NAT가 observability에 어떤 영향을 주는가?
- stateful firewall의 ESTABLISHED/RELATED가 어떻게 동작하는가?

> NAT는 "라우팅을 위해 필수"가 아니다. 학습 목적상 **라우팅을 먼저 성공시킨 뒤 NAT를 별도 실험**한다.

---

## 4.4 방화벽 정책

초기 정책:

```text
FORWARD default DROP

ALLOW edge_lan -> kafka brokers TCP 9092/9094
ALLOW ESTABLISHED,RELATED
DENY everything else
```

추후 인증/TLS를 사용하면 실제 listener port에 맞춘다.

검증 예:

```bash
# 허용되어야 함
nc -vz 10.0.0.10 9092

# 차단되어야 함
nc -vz 10.0.0.30 5432
```

edge의 bridge는 Kafka에는 접근할 수 있지만 DB에는 직접 접근하지 못하도록 한다.

---

## 4.5 호스트 → Grafana 접근

학습 목적상 두 방법을 구분한다.

### 방법 1 — router port forwarding

```text
host:8080
   ↓
router WAN
   ↓ DNAT
10.0.0.20:3000
```

### 방법 2 — reverse proxy

router에 nginx/HAProxy를 두고 server LAN의 Grafana로 proxy.

초기에는 DNAT를 사용하고, 이후 HTTP/TLS/Auth를 학습할 때 reverse proxy로 바꾼다.

---

## 4.6 ROS2 / DDS 경계

환경 변수:

```text
ROS_DOMAIN_ID=<project-specific-id>
RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

검증:

- edge 내 robot ↔ bridge discovery 가능
- server LAN에서 ROS2 node discovery 불가
- server LAN packet capture에서 RTPS multicast가 보이지 않음

```bash
tcpdump -ni any udp port 7400 or udp portrange 7400-7600
```

---

## 4.7 시간 동기화

지연 시간을 측정하려면 timestamp 의미를 먼저 정의해야 한다.

로컬 Docker 실험은 하나의 host clock을 공유하므로 비교가 쉽다.

실물 장비/AWS로 이동하면:

- NTP/chrony 사용
- 필요하면 PTP 학습
- clock offset을 metric으로 기록

clock sync 없이 서로 다른 머신의 timestamp를 빼서 얻은 latency는 신뢰할 수 없다.

---

## 4.8 네트워크 검증 체크리스트

- [ ] `edge_lan`, `server_lan`이 직접 연결되어 있지 않다.
- [ ] `ip route`로 route가 예상대로 들어가 있다.
- [ ] `traceroute`/`tracepath`가 router를 경유한다.
- [ ] firewall DROP 상태에서 연결이 실패한다.
- [ ] Kafka port만 edge에서 접근 가능하다.
- [ ] DB port는 edge에서 접근 불가능하다.
- [ ] Grafana는 host에서 router를 통해서만 접근된다.
- [ ] RTPS/DDS 트래픽이 server LAN으로 새지 않는다.
- [ ] `tc netem`으로 delay/loss가 실제 적용된다.
- [ ] `tcpdump`로 예상 packet path를 직접 확인한다.

---

# 5. ROS2 데이터 생성 설계

## 5.1 기본 토픽

로봇 1대 = namespace 1개.

```text
/robot_001/imu
/robot_001/odom
/robot_001/battery
```

| 토픽 | 메시지 | 기본 rate |
|---|---|---:|
| `/robot_xxx/imu` | `sensor_msgs/msg/Imu` | 100 Hz |
| `/robot_xxx/odom` | `nav_msgs/msg/Odometry` | 50 Hz |
| `/robot_xxx/battery` | `sensor_msgs/msg/BatteryState` | 1 Hz |

한 robot은 기본적으로 약:

```text
100 + 50 + 1 = 151 messages/sec
```

를 발생시킨다.

---

## 5.2 ROS2 QoS를 명시적으로 실험

QoS를 기본값에 맡기지 않는다.

실험할 항목:

- Reliability
  - BEST_EFFORT
  - RELIABLE
- History
  - KEEP_LAST
- Depth
- Durability
- Deadline

추천 첫 실험:

```text
IMU     → BEST_EFFORT, KEEP_LAST
Odometry→ BEST_EFFORT or RELIABLE 비교
Battery → RELIABLE
```

관찰할 것:

- packet loss가 있을 때 ROS2 레벨에서 어떤 데이터가 사라지는가?
- RELIABLE로 바꾸면 latency/queue가 어떻게 변하는가?
- publisher/subscriber QoS mismatch는 어떻게 보이는가?

---

## 5.3 더미 데이터 파라미터

```text
robot_id
seed
rate_scale
num_robots
payload_scale
```

이상치:

```text
spike_prob
drop_prob
nan_prob
inf_prob
stuck_prob
reorder_prob
duplicate_prob
delay_ms
clock_jump_prob
```

---

## 5.4 두 가지 부하 생성 모드

### Mode A — 많은 ROS node

실제 DDS discovery / executor overhead를 보기 위한 모드.

```text
1 robot = 1 ROS node
```

### Mode B — 적은 process에서 많은 logical robot

Kafka/data volume을 크게 만들기 위한 모드.

```text
1 process = N logical robots
```

> 500개의 logical robot을 한 process에서 생성하는 것은 500개의 실제 로봇/프로세스와 동일하지 않다. 이 차이를 실험 기록에 반드시 남긴다.

---

# 6. Event / Kafka 데이터 설계

## 6.1 Event envelope

1차 JSON 예시:

```json
{
  "schema_version": 1,
  "tenant_id": "demo-factory",
  "robot_id": "robot_001",
  "stream": "imu",
  "seq": 102934,
  "source_ts_ns": 1790000000000000000,
  "bridge_rx_ts_ns": 1790000000000200000,
  "message_id": "demo-factory:robot_001:imu:102934",
  "payload": {
    "ax": 0.01,
    "ay": -0.02,
    "az": 9.81
  }
}
```

### 필드 의미

| 필드 | 의미 |
|---|---|
| `schema_version` | 데이터 계약 버전 |
| `tenant_id` | SaaS tenant |
| `robot_id` | device identity |
| `stream` | imu/odom/battery |
| `seq` | source stream sequence |
| `source_ts_ns` | publisher/event time |
| `bridge_rx_ts_ns` | bridge가 받은 시각 |
| `message_id` | dedup용 안정적인 ID |
| `payload` | 실제 sensor payload |

추후 processor 단계에서 다음 timestamp를 추가 metric으로 사용한다.

```text
kafka_delivery_ts
processor_rx_ts
processor_done_ts
db_commit_ts
```

이렇게 해야 latency를 구간별로 나눠 분석할 수 있다.

---

## 6.2 Kafka topic

| Topic | Key | 초기 partitions | 역할 |
|---|---|---:|---|
| `telemetry.raw.imu` | `tenant_id:robot_id` | 6 | IMU 원본 |
| `telemetry.raw.odom` | `tenant_id:robot_id` | 6 | Odom 원본 |
| `telemetry.raw.battery` | `tenant_id:robot_id` | 3 | Battery 원본 |
| `telemetry.clean` | `tenant_id:robot_id` | 6 | 정제 데이터 |
| `telemetry.anomaly` | `tenant_id:robot_id` | 3 | 이상치 이벤트 |
| `telemetry.dlq` | 원래 key 유지 | 3 | 처리 불가 데이터 |

### 왜 `tenant_id:robot_id`인가?

서로 다른 tenant에 같은 `robot_001`이 존재해도 key 충돌 의미가 명확해지고, tenant/device 기준 파티션 분산을 관찰할 수 있다.

---

## 6.3 Kafka 순서 보장 — 정확한 표현

다음 표현은 틀리거나 과도하게 단순화된 표현이다.

```text
robot_id를 key로 두면 로봇 데이터의 전체 순서가 보장된다.
```

정확한 표현:

> Kafka는 **같은 topic의 같은 partition 안에서 record 순서를 보장**한다.

따라서:

- `telemetry.raw.imu` 안에서 같은 robot key → 같은 partition → IMU record order 유지 가능
- IMU topic과 Odom topic 사이의 전역 순서 → 보장되지 않음
- 여러 processor가 다시 `telemetry.clean`에 produce하는 경우에도 cross-topic event order는 별도 설계 필요

---

## 6.4 Producer 설정 실험

초기 안정성 설정 예:

```text
enable.idempotence=true
acks=all
compression.type=lz4
linger.ms=<experiment>
batch.size=<experiment>
```

`linger.ms`, `batch.size`, compression은 성능 실험 변수로 둔다.

### 주의

Kafka producer idempotence가 있다고 해서 전체 파이프라인이 자동으로 exactly-once가 되는 것은 아니다.

중복은 다음 위치에서도 생길 수 있다.

- edge spool 재전송
- consumer 처리 후 offset commit 전에 crash
- DB write 성공 후 consumer crash
- application retry

따라서 application-level dedup가 필요하다.

---

## 6.5 Consumer 처리 규칙

processor는 최소한 다음 순서를 따른다.

```text
consume
  ↓
parse / validate
  ↓
dedup check
  ↓
process
  ↓
DB write / output produce
  ↓
offset commit
```

실험 초기는 **at-least-once + idempotent sink**를 목표로 한다.

DB에는 `message_id` 또는 `(tenant_id, robot_id, stream, seq)` unique constraint를 둔다.

---

## 6.6 DLQ 설계

DLQ에는 원본 payload만 넣지 않는다.

예:

```json
{
  "error_code": "INVALID_JSON",
  "error_message": "...",
  "source_topic": "telemetry.raw.imu",
  "source_partition": 2,
  "source_offset": 10293,
  "failed_at_ns": 1790000000000000000,
  "original_key": "demo-factory:robot_001",
  "original_payload": "..."
}
```

그래야 나중에 재처리할 수 있다.

---

# 7. Bridge 설계

## 7.1 단순 callback에서 끝내지 않는다

bridge 내부:

```text
ROS callback
   ↓
bounded queue
   ↓
serializer
   ↓
Kafka producer async produce
   ↓
delivery callback
```

관찰 metric:

```text
bridge_ros_received_total
bridge_queue_depth
bridge_queue_drop_total
bridge_kafka_delivery_success_total
bridge_kafka_delivery_error_total
bridge_delivery_latency_seconds
```

---

## 7.2 Backpressure 정책

Kafka/server가 느려졌을 때 선택 가능한 정책:

1. 메모리 queue에서 기다린다.
2. 낮은 우선순위 sensor를 drop한다.
3. downsample한다.
4. disk spool에 저장한다.
5. publisher rate를 제한한다.

무제한 queue는 금지한다.

---

## 7.3 Disk spool

Phase 5에서 추가한다.

예시 구조:

```text
/var/lib/bridge-spool/
  pending/
  sent/
```

또는 SQLite/embedded queue를 사용한다.

요구 사항:

- max disk size
- FIFO 또는 priority
- retry backoff
- 서버 복구 후 replay
- duplicate 가능성 고려

---

# 8. 저장소 설계

## 8.1 Local TimescaleDB

예시 논리 schema:

```text
telemetry
- tenant_id
- robot_id
- stream
- seq
- message_id
- source_ts
- ingest_ts
- payload/jsonb or typed columns
```

가능하면 주요 sensor field는 typed column으로 분리한다.

예:

```text
imu_ax
imu_ay
imu_az
```

JSONB만 사용하면 개발은 쉽지만 대규모 분석/인덱스 실험에서 불리할 수 있다.

---

## 8.2 필수 인덱스

예:

```text
(tenant_id, robot_id, source_ts DESC)
(message_id) UNIQUE
```

Timescale hypertable은 `source_ts` 기준으로 구성한다.

---

## 8.3 Retention / downsampling

학습 항목:

- raw retention
- aggregate retention
- continuous aggregate 또는 별도 aggregate table

예:

```text
raw telemetry       7 days
1-minute aggregate 30 days
```

실제 값은 실험 용량에 맞춰 조정한다.

---

# 9. Observability

## 9.1 반드시 보는 지표

### Edge / Bridge

- ROS received msg/s
- Kafka produced msg/s
- queue depth
- local spool bytes
- produce error rate
- serialization latency

### Kafka

- bytes in/out
- records in
- partition count
- under-replicated partitions
- ISR 변화
- consumer lag
- request latency

### Processor

- consumed msg/s
- processed msg/s
- processing latency p50/p95/p99
- error rate
- anomaly rate
- DLQ rate

### DB

- insert rows/s
- transaction latency
- connection count
- storage size

### End-to-end

```text
source → bridge
bridge → Kafka
Kafka wait
processor
DB commit
```

각 단계 latency를 따로 본다.

---

## 9.2 로그 규칙

모든 서비스 로그에 최소 포함:

```text
timestamp
level
service
tenant_id
robot_id
message_id
error_code
```

개인정보는 없더라도 credential/token은 절대 로그에 남기지 않는다.

---

## 9.3 학습용 SLO

프로덕션 SLA가 아니라 실험 비교를 위한 기준이다.

예:

```text
steady state:
- consumer lag가 지속적으로 증가하지 않을 것
- bridge queue가 장시간 max에 붙어있지 않을 것
- unintentional drop = 0
- duplicate DB row = 0

load test:
- p99 end-to-end latency 기록
- burst 종료 후 lag recovery time 기록
```

---

# 10. Capacity Planning

기본 rate가 robot당 151 msg/s라면:

| Robot 수 | 대략적인 msg/s |
|---:|---:|
| 1 | 151 |
| 10 | 1,510 |
| 100 | 15,100 |
| 500 | 75,500 |
| 1,000 | 151,000 |

대략적인 네트워크/스토리지 양은 다음 식으로 추정한다.

```text
raw_data_rate ≈ messages_per_sec × average_record_bytes
```

Kafka replication을 고려하면 broker disk/network 내부 트래픽은 더 커진다.

매 실험 전에 실제 평균 record size를 측정한다.

```text
avg JSON bytes
compressed bytes
Kafka batch size
DB row size
```

> "로봇 500대"보다 "75k msg/s, 평균 420B, p99 latency 80ms" 같은 수치가 더 중요한 결과다.

---

# 11. 단계별 계획

## Phase 0 — 환경 / Repository 준비

### 구현

- Docker / Compose 확인
- Git repository 생성
- `.env.example`
- `Makefile` 또는 task script
- image version pinning
- basic lint/test

### 완료 기준

```bash
docker run --rm ros:jazzy ros2 topic list
```

동작.

또한:

- [ ] `docker compose config` 성공
- [ ] README에서 재현 가능
- [ ] 모든 서비스 버전 고정

---

## Phase 1 — Flat pipeline

```text
dummy_pub
   ↓ ROS2
bridge
   ↓ Kafka
single broker Kafka
   ↓
console consumer
```

### 구현

- robot 1대
- IMU 1 topic
- JSON serialization
- Kafka produce
- console consume

### 여기서는 하지 않는 것

- DB
- anomaly
- network isolation
- multi-broker

### 완료 기준

- [ ] `robot_001` IMU가 Kafka에 보임
- [ ] seq가 증가함
- [ ] bridge delivery callback 성공/실패가 로그에 남음
- [ ] bridge 재시작 후 다시 연결됨

---

## Phase 2 — Network segmentation

### 순서

1. edge/server network 분리
2. router 추가
3. pure routing
4. firewall
5. NAT
6. host DNAT
7. netem

한 번에 전부 넣지 않는다.

### 완료 기준

- [ ] bridge → Kafka 가능
- [ ] bridge → DB 직접 접근 차단
- [ ] host → Grafana는 router 경유
- [ ] DDS가 server LAN으로 넘어가지 않음
- [ ] 100ms delay 적용 시 latency 증가 확인
- [ ] 1% loss 적용 확인

---

## Phase 3 — Persistence + Monitoring

### 구현

```text
Kafka
 ↓
processor pass-through
 ↓
TimescaleDB
 ↓
Grafana
```

Prometheus도 추가한다.

### Grafana dashboard 최소 패널

1. robot별 IMU
2. battery
3. ingest msg/s
4. consumer lag
5. bridge queue
6. end-to-end latency p50/p99
7. anomaly count

### 완료 기준

- [ ] telemetry graph 표시
- [ ] consumer lag 표시
- [ ] bridge metric 표시
- [ ] message_id 중복 insert 방지 확인

---

## Phase 4 — Data Quality / Anomaly

processor에 state를 추가한다.

```text
last_seq
last_timestamp
last_value
rolling_window
```

### 실험

- spike
- drop
- NaN
- Inf
- stuck
- reorder
- late arrival
- duplicate
- schema error

### 완료 기준

실험마다 최소 기록:

```text
injected anomalies
true positive
false positive
false negative
precision
recall
processing overhead
```

규칙 기반 이상치 탐지라도 precision/recall을 계산한다.

---

## Phase 5 — Scale / Backpressure / Failure

Phase 5는 이 프로젝트의 핵심 성능 실험이다.

### 5A. Load scale

```text
10 robots
25 robots
50 robots
100 robots
250 robots
500 robots
```

CPU가 먼저 한계에 도달하면 robot 수 대신 rate/payload size를 조정한다.

### 5B. Producer tuning

비교:

```text
compression none vs lz4
linger.ms
batch.size
acks
```

관찰:

- throughput
- latency
- CPU
- network bytes

### 5C. Consumer scaling

```text
1 processor
2 processors
4 processors
8 processors
```

partition 수보다 consumer 수가 많을 때 어떤 일이 생기는지 직접 확인한다.

### 5D. Multi-broker Kafka

단일 broker 이후 3 broker cluster를 구성한다.

실험:

- replication.factor
- min.insync.replicas
- broker restart
- leader election
- under replicated partition
- ISR 변화

> 한 PC 안의 3개 container는 진짜 3개 서버 fault domain은 아니지만 Kafka replication/failover 메커니즘 학습에는 유용하다.

### 5E. Backpressure

Kafka를 느리게 하거나 network를 제한한다.

검증:

- bounded queue
- disk spool
- drop policy
- recovery replay

### 5F. Failure injection

- router 30초 차단
- Kafka broker restart
- processor kill -9
- DB stop
- malformed message burst
- disk spool full

### 완료 기준

최종 표:

| 조건 | Throughput | p99 latency | Max lag | Recovery | Drop | Duplicate |
|---|---:|---:|---:|---:|---:|---:|
| baseline | | | | | | |
| tuned | | | | | | |

그리고:

> "현재 노트북 환경에서 평균 X B record 기준 Y msg/s까지 lag가 안정적이며, Z msg/s부터 bridge CPU가 병목이 되었다. batch/compression 적용 후 처리량이 ..."

처럼 정량적인 결론을 작성한다.

---

## Phase 6 — SaaS Control Plane

여기부터 프로젝트를 실제 SaaS 구조로 확장한다.

### 6.1 FastAPI service

예시 API:

```text
POST   /tenants
GET    /tenants/{tenant_id}
POST   /tenants/{tenant_id}/devices
GET    /tenants/{tenant_id}/devices
POST   /devices/{device_id}/credentials
GET    /devices/{device_id}/status
GET    /tenants/{tenant_id}/usage
```

### 6.2 Metadata schema

```text
tenants
- tenant_id
- name
- created_at

users
- user_id
- tenant_id
- role

devices
- device_id
- tenant_id
- display_name
- status
- last_seen_at

credentials
- credential_id
- device_id
- hashed_secret / certificate metadata
- expires_at
- revoked_at
```

### 6.3 Multi-tenancy

최소 적용:

- 모든 telemetry row에 `tenant_id`
- API query에 tenant filter 강제
- Kafka key에 tenant 포함
- Grafana/dashboard query에 tenant scope

추가 실험:

- shared topic + tenant key
- tenant별 topic

두 방식을 비교한다.

### 6.4 인증

로컬:

- API token 또는 API key

AWS:

- HTTPS
- secret rotation
- 필요하면 Cognito/IAM/MSK auth 실험

### 완료 기준

- [ ] tenant A의 robot 등록 가능
- [ ] tenant B의 robot 등록 가능
- [ ] A credential로 B 데이터 접근 불가
- [ ] device last_seen 표시
- [ ] tenant별 telemetry usage 집계

---

## Phase 7 — AWS migration

## 7.1 목표 구조

```text
On-prem / Local Edge

ROS2 robots
   ↓
bridge
   ↓
VPN
   ↓
AWS VPC
   ↓
MSK
   ↓
ECS processor
   ↓
PostgreSQL
   ↓
Grafana / API
```

---

## 7.2 AWS 서비스 매핑

| Local | AWS 후보 |
|---|---|
| server LAN | VPC private subnet |
| Kafka | Amazon MSK Serverless 또는 MSK Provisioned |
| processor | ECS Fargate |
| SaaS API | ECS Fargate + ALB 또는 API Gateway/Lambda |
| PostgreSQL | Amazon RDS for PostgreSQL |
| TimescaleDB | 별도 managed Timescale/Tiger 서비스 또는 self-managed 환경 검토 |
| metrics | CloudWatch + Prometheus/Grafana 조합 |
| images | ECR |
| secrets | Secrets Manager / SSM Parameter Store |
| IaC | Terraform |

### 중요한 수정

`RDS/TimescaleDB`를 하나의 선택지처럼 쓰면 안 된다.

Amazon RDS for PostgreSQL에서 사용할 수 있는 extension은 AWS가 지원하는 목록으로 제한된다. 따라서 AWS 단계에서는 다음 중 하나를 명확히 선택한다.

1. **RDS PostgreSQL로 단순화**
2. TimescaleDB를 지원하는 별도 managed service 사용
3. TimescaleDB를 EC2/ECS 등에서 직접 운영

첫 AWS 학습에서는 **RDS PostgreSQL**로 시작하는 편이 구조를 단순하게 만든다.

---

## 7.3 Edge ↔ AWS connectivity

학습 순서 추천:

### Stage A — WireGuard lab

```text
edge/router ↔ EC2 WireGuard gateway ↔ VPC
```

VPN 개념을 이해하기 쉽다.

### Stage B — AWS Site-to-Site VPN

실제 기업형 hybrid networking 개념을 학습한다.

학습 항목:

- Customer Gateway
- Virtual Private Gateway / Transit Gateway 개념
- route propagation
- security group
- NACL
- private IP connectivity

---

## 7.4 MSK 연결

MSK는 기본적으로 VPC 기반 private connectivity를 중심으로 설계한다.

bridge가 로컬 edge에 있다면:

```text
edge → VPN → VPC → MSK
```

경로를 만든다.

실험:

- bootstrap broker DNS resolution
- route table
- security group
- TLS/auth

---

## 7.5 비용 안전장치

AWS Phase 시작 전에 반드시:

- AWS Budget 생성
- billing alarm 생성
- resource tag 부여
- Terraform destroy 절차 준비
- NAT Gateway / MSK / load balancer 등 시간당 비용 자원 확인

실험 완료 후:

```bash
terraform destroy
```

을 실제로 검증한다.

---

## Phase 8 — 선택: 실제 공유기 / Ethernet / VLAN 실습

Docker에서 배운 개념을 실제 network device로 옮긴다.

예시 구성:

```text
[Robot PC / Edge PC]
      │ Ethernet
      ▼
[Switch / Router]
      │
      ├── VLAN 10 : OT
      └── VLAN 20 : Server
                 │
                 ▼
            Server / AWS VPN
```

가능한 장비:

- OpenWrt 가능한 공유기
- VLAN 지원 managed switch
- NIC 2개 달린 mini PC/router

학습:

- DHCP/static IP
- VLAN tagging
- routing
- firewall
- port forwarding
- VPN
- tcpdump on physical interface

### 완료 기준

- [ ] OT VLAN에서 Server VLAN 직접 접근 제한
- [ ] 지정된 Kafka/VPN 경로만 허용
- [ ] 실제 cable/NIC link 장애 실험
- [ ] Docker 실험과 packet path 비교

---

# 12. 실험 시나리오

## 12.1 데이터 이상치

| Scenario | Injection | Detection / Handling |
|---|---|---|
| Spike | 비현실적 가속도 | range, derivative, z-score |
| Drop | publish 생략 | seq gap |
| NaN/Inf | invalid float | validation → DLQ |
| Stuck | 값 고정 | rolling variance |
| Reorder | seq 순서 변경 | reorder buffer / late flag |
| Delay | event hold | event-time window |
| Duplicate | 동일 seq 재전송 | message_id dedup |
| Schema error | 필드 누락/타입 변경 | schema validation → DLQ |
| Clock jump | timestamp 점프 | monotonicity / clock offset check |

---

## 12.2 Traffic / Load

| Scenario | Load method | Observe | Candidate fix |
|---|---|---|---|
| Robot scale | 10→500 | msg/s, CPU, lag | bridge scale / partitions |
| Rate scale | ×2, ×5 | queue, p99 | batching/compression |
| Payload scale | 큰 JSON | bandwidth | Protobuf/compression |
| Reconnect burst | 동시 burst | lag recovery | partitions/consumer scale |
| Slow consumer | sleep | lag | consumer group scale |
| Link limit | tc rate | queue/spool | edge buffer/downsample |
| Link cut | firewall block | loss/recovery | replay/spool |
| Hot key | robot 1대 ×20 | partition skew | key/topic design |

### Hot partition 주의

하나의 robot 데이터를 여러 partition으로 쪼개면 throughput은 늘릴 수 있지만 해당 robot의 전체 순서를 잃을 수 있다.

따라서 해결책은 단순히 "key 변경"이 아니라 다음 trade-off 비교가 필요하다.

- robot별 순서 보장 유지
- stream별 topic 분리
- substream key 사용
- hot robot 전용 topic

---

## 12.3 Infrastructure failure

| Failure | 확인할 것 |
|---|---|
| broker 1 restart | producer retry / leader election |
| processor crash | duplicate 여부 / offset 처리 |
| DB stop | lag 증가 / processor retry |
| router cut | bridge spool 증가 |
| router recovery | replay / duplicate |
| spool disk full | drop policy / alert |
| malformed burst | processor 생존 / DLQ 증가 |

---

# 13. 실험 기록 양식

```markdown
# Experiment: EXP-xxx

## Hypothesis

## Environment
- git commit:
- image versions:
- CPU/RAM limit:
- Kafka brokers:
- partitions:
- replication factor:

## Load
- robots:
- rate:
- avg payload bytes:
- expected msg/s:

## Network
- delay:
- loss:
- bandwidth:

## Baseline
- throughput:
- p50 latency:
- p95 latency:
- p99 latency:
- max consumer lag:
- CPU:
- memory:

## Failure / Change

## Result

## Root cause

## Fix

## After fix

## Conclusion
```

모든 실험은 Git commit과 image version을 남긴다.

---

# 14. 테스트 전략

## 14.1 Unit test

- serializer
- schema validation
- anomaly rule
- dedup key
- config parser

## 14.2 Integration test

```text
dummy → ROS → bridge → Kafka → processor → DB
```

검증:

- sample message 도착
- DB row 생성
- duplicate 재전송 시 row 증가하지 않음
- invalid message → DLQ

## 14.3 Network test

`scripts/verify_network.sh`

자동 확인:

- route
- allowed port
- blocked port
- DNS
- Kafka bootstrap

## 14.4 Failure regression

고친 장애가 다시 발생하지 않는지 script로 남긴다.

---

# 15. Security 학습 범위

초기에는 plaintext로 구조를 단순화해도 되지만 Phase 6 이후에는 최소한 다음을 넣는다.

- secret을 Git에 commit하지 않기
- `.env` 제외
- least privilege
- service별 credential 분리
- TLS
- API auth
- tenant authorization
- credential rotation
- audit log

Kafka 보안은 다음 순서로 학습한다.

```text
PLAINTEXT
   ↓
TLS
   ↓
SASL / IAM 등 인증
   ↓
ACL / authorization
```

---

# 16. 디렉토리 구조

```text
ros2-saas/
├── README.md
├── .env.example
├── Makefile
├── compose/
│   ├── compose.base.yml
│   ├── compose.network.yml
│   ├── compose.observability.yml
│   └── compose.kafka-ha.yml
│
├── docs/
│   ├── plan.md
│   ├── architecture.md
│   ├── network.md
│   ├── runbook.md
│   └── experiments/
│       └── EXP-001.md
│
├── edge/
│   ├── dummy_pub/
│   │   ├── package.xml
│   │   ├── setup.py
│   │   └── ...
│   └── bridge/
│       ├── src/
│       ├── tests/
│       └── Dockerfile
│
├── router/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── firewall.sh
│   ├── routes.sh
│   └── netem.sh
│
├── server/
│   ├── processor/
│   ├── api/
│   ├── db/
│   │   ├── init.sql
│   │   └── migrations/
│   ├── grafana/
│   └── prometheus/
│
├── scripts/
│   ├── verify_network.sh
│   ├── smoke_test.sh
│   ├── load_test.sh
│   ├── chaos_broker_restart.sh
│   └── chaos_network_cut.sh
│
├── tests/
│   └── integration/
│
└── infra/
    └── terraform/
        ├── modules/
        └── environments/
            └── dev/
```

---

# 17. 주요 리스크와 함정

## Docker network 우회

컨테이너가 의도치 않게 default network에 붙으면 실험이 무효가 될 수 있다.

검증:

```bash
docker inspect
ip route
tracepath
```

---

## Kafka advertised listeners

bootstrap 연결만 되고 실제 broker 연결이 실패하는 대표적인 원인이다.

client가 실제로 접근 가능한 주소를 broker가 advertise해야 한다.

multi-broker에서는 각 broker 주소가 모두 edge에서 route 가능해야 한다.

---

## Kafka partition ≠ 무조건 성능 향상

partition이 늘면:

- consumer parallelism 증가 가능
- broker overhead 증가
- file handle 증가
- rebalance 영향 증가

그리고 이미 존재하는 key의 partition mapping도 partition 수 변경 후 달라질 수 있으므로 순서/운영에 영향을 줄 수 있다.

---

## Producer idempotence ≠ end-to-end exactly once

Kafka producer retry 중복을 줄이는 기능과 전체 application pipeline의 exactly-once는 다른 문제다.

DB 멱등성/consumer offset 처리까지 같이 설계한다.

---

## `robot_id`만으로 tenant를 구분하지 않기

SaaS에서는 같은 robot ID가 서로 다른 고객에게 있을 수 있다.

```text
key = tenant_id:robot_id
```

형태를 기본으로 한다.

---

## CPU 한계와 실제 대규모 분산 시스템의 차이

노트북 한 대에서:

- robot containers
- Kafka brokers
- DB
- Grafana
- Prometheus

를 모두 돌리면 Kafka보다 host CPU/RAM이 먼저 병목일 수 있다.

이를 실패로 보지 말고 실험 결과에 host resource limit을 기록한다.

---

## Clock 문제

AWS/실물 장비로 이동하면 서로 다른 machine clock 때문에 latency 계산이 왜곡될 수 있다.

NTP sync 상태를 반드시 확인한다.

---

# 18. 단계별 산출물

| Phase | 산출물 |
|---|---|
| 0 | 재현 가능한 repository |
| 1 | ROS2→Kafka 최소 pipeline |
| 2 | network topology + packet capture 결과 |
| 3 | Grafana dashboard + DB schema |
| 4 | anomaly report |
| 5 | benchmark + bottleneck report |
| 6 | tenant/device API + auth model |
| 7 | Terraform + AWS architecture |
| 8 | physical network diagram + packet capture |

---

# 19. 최종 Definition of Done

프로젝트 전체 완료를 다음처럼 정의한다.

## Data Plane

- [ ] 100대 이상 logical robot load 생성 가능
- [ ] ROS2 → Kafka → processor → DB end-to-end 동작
- [ ] consumer lag / p99 latency 관측 가능
- [ ] duplicate 방지 가능
- [ ] network 단절 후 spool/replay 가능
- [ ] Kafka broker 장애 실험 완료

## Data Quality

- [ ] 8종 이상 anomaly/fault injection
- [ ] detection precision/recall 기록
- [ ] malformed data가 consumer 전체를 죽이지 않음

## Network

- [ ] edge/server segmentation 검증
- [ ] firewall allowlist 검증
- [ ] latency/loss/bandwidth injection
- [ ] packet capture로 경로 설명 가능

## SaaS

- [ ] tenant 생성
- [ ] device 등록
- [ ] credential 발급
- [ ] tenant isolation
- [ ] usage/status API

## AWS

- [ ] Terraform으로 dev environment 생성
- [ ] edge → VPN → AWS Kafka 경로 동작
- [ ] AWS에서 processor + DB 동작
- [ ] 비용 알림 설정
- [ ] destroy 후 리소스 정리 확인

## 결과물

- [ ] architecture diagram
- [ ] network diagram
- [ ] benchmark report
- [ ] anomaly experiment report
- [ ] AWS deployment guide
- [ ] runbook

---

# 20. 바로 시작할 순서

현재는 아래 순서만 집중한다.

```text
Step 1
Phase 0 repository 생성

Step 2
robot_001 IMU publisher 구현

Step 3
bridge가 IMU subscribe

Step 4
Kafka single broker 실행

Step 5
bridge → Kafka produce

Step 6
console consumer로 메시지 확인

Step 7
bridge metric 추가

여기까지 성공한 뒤 Phase 2 network segmentation으로 넘어간다.
```

처음부터 Grafana/AWS/VPN/멀티테넌시를 동시에 만들지 않는다.

---

# 21. 진행 체크리스트

- [ ] Phase 0 — Environment / Repository
- [ ] Phase 1 — Flat ROS2 → Kafka
- [ ] Phase 2 — Network segmentation
- [ ] Phase 3 — DB / Monitoring
- [ ] Phase 4 — Anomaly / Data Quality
- [ ] Phase 5 — Scale / Backpressure / Failure
- [ ] Phase 6 — SaaS Control Plane
- [ ] Phase 7 — AWS Migration
- [ ] Phase 8 — Physical Network Lab (Optional)

---

# 22. 기술 검증 메모

이 계획서에서 특히 다음 사항은 구현 전에 공식 문서를 다시 확인한다.

- Docker Compose `internal` network의 외부 연결/route 동작
- ROS2 Jazzy의 RMW / DDS 설정
- 사용하는 Kafka 버전의 producer idempotence 기본값과 broker 설정
- 사용하는 Kafka container image의 KRaft 설정 방법
- Amazon MSK의 VPC/private connectivity 및 인증 방식
- Amazon RDS for PostgreSQL의 지원 extension 목록

서비스/이미지의 설정 방식은 버전에 따라 달라질 수 있으므로, **계획서의 개념은 유지하되 구체적인 옵션 이름은 실제 구현 시점의 공식 문서를 기준으로 고정**한다.
