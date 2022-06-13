import json
import time
from typing import Optional

from src.sender_strategy import SenderStrategy


class FixedWindowStrategy(SenderStrategy):
    def __init__(self, cwnd: int) -> None:
        self.cwnd = cwnd

        super().__init__()

    def window_is_open(self) -> bool:
        # Returns true if the congestion window is not full
        return self.seq_num - self.next_ack < self.cwnd

    def next_packet_to_send(self) -> Optional[str]:
        if not self.window_is_open():
            return None

        serialized_data = json.dumps(
            {
                "seq_num": self.seq_num,
                "send_ts": time.time(),
                "sent_bytes": self.sent_bytes,
            }
        )
        self.unacknowledged_packets[self.seq_num] = True
        self.seq_num += 1
        return serialized_data

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
            self.curr_duplicate_acks += 1

            if self.curr_duplicate_acks == 3:
                # Received 3 duplicate acks, retransmit
                self.curr_duplicate_acks = 0
                self.seq_num = ack["seq_num"] + 1
        else:
            del self.unacknowledged_packets[ack["seq_num"]]
            self.next_ack = max(self.next_ack, ack["seq_num"] + 1)
            self.sent_bytes += ack["ack_bytes"]
            rtt = float(time.time() - ack["send_ts"])
            self.rtts.append(rtt)
            self.ack_count += 1

        self.cwnds.append(self.cwnd)
