from .reader_abc import AddressData, Reader


class BytesReader(Reader):
    def __init__(self, address: int, bs: bytes):
        super().__init__(address)
        self.bs = bs

    def read(self, size: int) -> AddressData:
        current = self.offset
        self.offset += size
        read_bytes = self.bs[current : current + size]
        if len(read_bytes) < size:
            raise ValueError(f"Failed to read requested number of bytes: {size}")
        return self.address + current, read_bytes

    def new_reader(self, address: int) -> Reader:
        if address < self.address:
            raise ValueError(
                f"Supplied address: {address:#010x} cannot be lower than original address: {self.address:#010x}"
            )
        offset = address - self.address
        return type(self)(address, self.bs[offset:])
