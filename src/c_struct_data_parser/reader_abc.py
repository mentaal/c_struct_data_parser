from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple


AddressData = Tuple[int, bytes | memoryview]


class Reader(ABC):
    def __init__(self, address: int, offset: int = 0):
        self.address = address
        self.offset = offset

    @abstractmethod
    def read(self, size: int) -> Tuple[AddressData, Reader]:
        current_offset = self.offset
        return (
            (self.address + current_offset, bytes(size)),
            self.new_reader(self.address + size),
        )

    def new_reader(self, address: int) -> Reader:
        return type(self)(address)


ReaderData = Tuple[AddressData, Reader]
