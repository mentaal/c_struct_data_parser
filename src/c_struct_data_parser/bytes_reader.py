from .reader_abc import Reader, ReaderData


class BytesReader(Reader):
    def __init__(self, address: int, bs: bytes | memoryview, offset: int = 0):
        super().__init__(address, offset)
        self.bs = memoryview(bs)

    def read(self, size: int) -> ReaderData:
        current = self.offset
        read_bytes = self.bs[current : current + size]
        if len(read_bytes) < size:
            raise ValueError(f"Failed to read requested number of bytes: {size}")
        return (self.address + current, read_bytes), self.new_reader(self.address + size)

    def new_reader(self, address: int) -> Reader:
        delta = address - self.address
        new_offset = self.offset + delta
        if new_offset < 0:
            raise ValueError(
                f"Requested address: {address:#x} out of range. Lowest address: {self.address - self.offset:#x}"
            )
        return type(self)(address, self.bs, new_offset)
