# Feature Schema 1.0

The same ordered schema is used for every training row and live inference vector. The implementation is in `nids_engine/features.py`. Every model input is a finite, non-negative numeric value. IP addresses, flow IDs, capture timestamps, and finalization reasons are deliberately excluded from model input.

Missing ports are encoded as numeric zero plus a corresponding `*_missing` flag. Directional packet-size statistics use zero when that direction has no packets plus a `*_missing` flag. A genuine port zero is represented by a zero port value with the missing flag set to zero.

| Order | Feature | Calculation |
|---:|---|---|
| 1 | `flow_duration_seconds` | `last_seen_at - started_at`, clamped at zero. |
| 2 | `total_packets` | Forward packet count plus reverse packet count. |
| 3 | `total_bytes` | Sum of observed packet lengths in both directions. |
| 4 | `forward_packets` | Packets from canonical endpoint A to endpoint B. |
| 5 | `reverse_packets` | Packets from endpoint B to endpoint A. |
| 6 | `forward_bytes` | Sum of packet lengths from A to B. |
| 7 | `reverse_bytes` | Sum of packet lengths from B to A. |
| 8 | `packets_per_second` | Total packets divided by duration; zero for zero-duration flows. |
| 9 | `bytes_per_second` | Total bytes divided by duration; zero for zero-duration flows. |
| 10 | `average_packet_size` | Total bytes divided by packet count; zero if count is zero. |
| 11 | `min_packet_size` | Smallest packet length observed in either direction; zero if absent. |
| 12 | `max_packet_size` | Largest packet length observed in either direction; zero if absent. |
| 13 | `protocol_tcp` | 1 for TCP, otherwise 0. |
| 14 | `protocol_udp` | 1 for UDP, otherwise 0. |
| 15 | `protocol_icmp` | 1 for IPv4 ICMP, otherwise 0. |
| 16 | `protocol_icmpv6` | 1 for ICMPv6, otherwise 0. |
| 17 | `protocol_other` | 1 for other or unknown protocols, otherwise 0. |
| 18 | `endpoint_a_port` | Port for canonical endpoint A, or zero if unavailable. |
| 19 | `endpoint_a_port_missing` | 1 when endpoint A has no observed port, otherwise 0. |
| 20 | `endpoint_b_port` | Port for canonical endpoint B, or zero if unavailable. |
| 21 | `endpoint_b_port_missing` | 1 when endpoint B has no observed port, otherwise 0. |
| 22 | `tcp_syn_count` | Count of observed TCP packets carrying SYN in either direction. |
| 23 | `tcp_ack_count` | Count of observed TCP packets carrying ACK in either direction. |
| 24 | `tcp_fin_count` | Count of observed TCP packets carrying FIN in either direction. |
| 25 | `tcp_rst_count` | Count of observed TCP packets carrying RST in either direction. |
| 26 | `tcp_psh_count` | Count of observed TCP packets carrying PSH in either direction. |
| 27 | `forward_packet_size_min` | Minimum packet length A to B, or zero if absent. |
| 28 | `forward_packet_size_max` | Maximum packet length A to B, or zero if absent. |
| 29 | `forward_packet_size_missing` | 1 when no A-to-B packet was observed, otherwise 0. |
| 30 | `reverse_packet_size_min` | Minimum packet length B to A, or zero if absent. |
| 31 | `reverse_packet_size_max` | Maximum packet length B to A, or zero if absent. |
| 32 | `reverse_packet_size_missing` | 1 when no B-to-A packet was observed, otherwise 0. |

`validate_model_schema()` rejects a model whose schema version or exact feature-name ordering differs. Schema changes that alter names, order, values, or missing-value semantics must increment `FEATURE_SCHEMA_VERSION` and require a matching training artifact.
