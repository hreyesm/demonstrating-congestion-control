import json
import time
from typing import Optional

from src.sender_strategy import SenderStrategy


class TcpRenoStrategy(SenderStrategy):
    def __init__(self, slow_start_thresh: int, initial_cwnd: int) -> None:
        self.slow_start_thresh = slow_start_thresh
        self.cwnd = initial_cwnd
        self.fast_retransmit_packet = None
        self.time_since_retransmit = None
        self.retransmitting_packet = False
        self.ack_count = 0
        self.duplicated_ack = None
        self.slow_start_thresholds = []

        super().__init__()

    def window_is_open(self) -> bool:
        return self.seq_num - self.next_ack < self.cwnd

    def next_packet_to_send(self) -> Optional[str]:
        send_data = None
        if (
            self.retransmitting_packet
            and self.time_of_retransmit
            and time.time() - self.time_of_retransmit > 1
        ):
            # The retransmit packet timed out--resend it
            self.retransmitting_packet = False

        if self.fast_retransmit_packet and not self.retransmitting_packet:
            # Logic for resending the packet
            self.unacknowledged_packets[self.fast_retransmit_packet["seq_num"]][
                "send_ts"
            ] = time.time()
            send_data = self.fast_retransmit_packet
            self.retransmitting_packet = True

            self.time_of_retransmit = time.time()

        elif self.window_is_open():
            send_data = {"seq_num": self.seq_num, "send_ts": time.time()}

            self.unacknowledged_packets[self.seq_num] = send_data
            self.seq_num += 1
        else:
            # Check to see if any segments have timed out. Note that this
            # isn't how TCP actually works--traditional TCP uses exponential
            # backoff for computing the timeouts
            for seq_num, segment in self.unacknowledged_packets.items():
                if time.time() - segment["send_ts"] > 4:
                    self.unacknowledged_packets[seq_num]["send_ts"] = time.time()
                    return json.dumps(segment)

        if send_data is None:
            return None
        else:
            return json.dumps(send_data)

    def process_ack(self, serialized_ack: str) -> None:
        ack = json.loads(serialized_ack)
        if ack.get("handshake"):
            return

        self.total_acks += 1
        self.times_of_acknowledgements.append(
            ((time.time() - self.start_time), ack["seq_num"])
        )

        if self.unacknowledged_packets.get(ack["seq_num"]) is None:
            # Duplicate ack

            self.num_duplicate_acks += 1
            if self.duplicated_ack and ack["seq_num"] == self.duplicated_ack["seq_num"]:
                self.curr_duplicate_acks += 1
            else:
                self.duplicated_ack = ack
                self.curr_duplicate_acks = 1

            if self.curr_duplicate_acks == 3:
                print("[T%s] Received 3 duplicate ACKs, retransmitting..." % time.time())
                self.fast_retransmit_packet = self.unacknowledged_packets[
                    ack["seq_num"] + 1
                ]

                print("Entering fast recovery, reducing congestion window by 50%\n")
                self.cwnd = int(self.cwnd / 2)
                self.slow_start_thresh = self.cwnd
        elif ack["seq_num"] >= self.next_ack:
            if self.fast_retransmit_packet:
                self.fast_retransmit_packet = None
                self.retransmitting_packet = False
                self.curr_duplicate_acks = 0
                self.seq_num = ack["seq_num"] + 1

            # Acknowledge all packets where seq_num < ack['seq_num']
            self.unacknowledged_packets = {
                k: v
                for k, v in self.unacknowledged_packets.items()
                if k > ack["seq_num"]
            }
            self.next_ack = max(self.next_ack, ack["seq_num"] + 1)
            self.ack_count += 1
            self.sent_bytes += ack["ack_bytes"]
            rtt = float(time.time() - ack["send_ts"])
            self.rtts.append(rtt)
            if self.cwnd < self.slow_start_thresh:
                # In slow start
                self.cwnd += 1
            # elif self.cwnd >= self.slow_start_thresh:
            #     # In congestion avoidance
            #     self.cwnd += (self.cwnd + 1) / self.cwnd
            elif (ack["seq_num"] + 1) % self.cwnd == 0:
                # In congestion avoidance
                self.cwnd += 1

        self.cwnds.append(self.cwnd)
        self.slow_start_thresholds.append(self.slow_start_thresh)

