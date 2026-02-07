from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple


AddressData = Tuple[int, bytes]


class Reader(ABC):

    def __init__(self, address: int):
        self.address = address
        self.offset = 0

    @abstractmethod
    def read(self, size: int) -> AddressData:
        current_offset = self.offset
        self.offset += size
        return (self.address + current_offset, bytes(size))

    def new_reader(self, address: int) -> Reader:
        return type(self)(address)
