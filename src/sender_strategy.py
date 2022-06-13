import time
from typing import Dict, List, Optional, Tuple


class SenderStrategy(object):
    def __init__(self) -> None:
        self.seq_num = 0
        self.next_ack = 0
        self.sent_bytes = 0
        self.start_time = time.time()
        self.total_acks = 0
        self.num_duplicate_acks = 0
        self.curr_duplicate_acks = 0
        self.rtts: List[float] = []
        self.cwnds: List[int] = []
        self.unacknowledged_packets: Dict = {}
        self.times_of_acknowledgements: List[Tuple[float, int]] = []
        self.ack_count = 0
        self.slow_start_thresholds: List = []
        self.time_of_retransmit: Optional[float] = None

    def next_packet_to_send(self):
        raise NotImplementedError

    def process_ack(self, ack: str):
        raise NotImplementedError
