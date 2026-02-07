from enum import Enum
from functools import partial
from itertools import chain, islice
from typing import Iterable

from c_struct_data_parser.bytes_reader import BytesReader
from c_struct_data_parser.data_structures import (
    create_array_definition,
    create_bit_fields_definition,
    create_forward_pointer,
    create_int_definition,
    create_pointer_definition,
    create_struct_definition,
    Int1Definition,
    Int4Definition,
)


def grouper(n: int, it: Iterable) -> Iterable:
    _it = iter(it)
    return iter(lambda: islice(_it, n), [])


int_to_le_bytes = partial(int.to_bytes, byteorder="little")
int_to_le_bytes_4 = partial(int_to_le_bytes, length=4)


def test_int_4_parse():
    num = 0x12345678
    num_as_bytes = int_to_le_bytes_4(num)
    bytes_reader = BytesReader(address=0, bs=num_as_bytes)
    int_4_definition, new_reader = Int4Definition.parser(bytes_reader)
    assert int_4_definition.value == num


Struct2Int = create_struct_definition(
    "Struct2Int",
    {
        "value_a": Int4Definition,
        "value_b": Int4Definition,
    },
)


def test_struct2Int() -> None:
    value_a = 0x12345678
    value_b = 0x99887766
    bs = b"".join(map(int_to_le_bytes_4, [value_a, value_b]))
    bytes_reader = BytesReader(address=0, bs=bs)
    struct_2_int, new_reader = Struct2Int.parser(bytes_reader)
    assert struct_2_int.value_a.value == value_a
    assert struct_2_int.value_b.value == value_b

    print(struct_2_int)


BitFieldsExample = create_bit_fields_definition(
    "BitFieldsExample",
    Int4Definition,
    {
        "field_a": 4,
        "reserved_1": 5,
        "field_b": 5,
    },
)


def test_bit_fields() -> None:
    val = 0x123456
    bs = int_to_le_bytes_4(val)
    bytes_reader = BytesReader(address=0, bs=bs)
    bit_fields_example, new_reader = BitFieldsExample.parser(bytes_reader)
    assert bit_fields_example.field_a.value == val & 0xF
    assert bit_fields_example.field_b.value == (val >> 9) & 0x1F
    print(bit_fields_example)


Struct2IntPointer = create_pointer_definition(
    Struct2Int,
    Int4Definition,
)


def test_pointer_type() -> None:
    value_a = 0x12345678
    value_b = 0x99887766
    bs_struct = b"".join(map(int_to_le_bytes_4, [value_a, value_b]))
    bs_pointer = int_to_le_bytes_4(0x2000)
    bs = b"".join([bs_struct, bs_pointer])
    bytes_reader = BytesReader(address=0x2000, bs=bs)

    struct_2_int, new_reader = Struct2Int.parser(bytes_reader)
    assert struct_2_int.value_a.value == value_a
    assert struct_2_int.value_b.value == value_b

    p_struct_2_int, new_reader_2 = Struct2IntPointer.parser(new_reader)

    print(p_struct_2_int)

    struct_2_int_copy = p_struct_2_int.resolve(new_reader_2)

    assert struct_2_int_copy.value_a.value == value_a
    assert struct_2_int_copy.value_b.value == value_b


Struct2IntArray5 = create_array_definition(
    target_type=Struct2Int,
    size=5,
)


def test_array_type() -> None:
    nums = range(5 * 2)
    bs = b"".join(map(int_to_le_bytes_4, nums))
    bytes_reader = BytesReader(address=0, bs=bs)

    struct_2_int_array, new_reader = Struct2IntArray5.parser(bytes_reader)
    print(struct_2_int_array)
    for (a, b), array_entry in zip(grouper(2, nums), struct_2_int_array.fields):
        assert array_entry.value_a.value == a
        assert array_entry.value_b.value == b


NestedStruct = create_struct_definition(
    "NestedStruct",
    {
        "value_a": Struct2Int,
        "value_b": Int1Definition,
    },
)


def test_nested_structs() -> None:
    value_a = 0x12345678
    value_b = 0x99887766
    int_1 = 0x6
    bs = b"".join(chain(map(int_to_le_bytes_4, [value_a, value_b]), [bytes([int_1])]))
    bytes_reader = BytesReader(address=0x10, bs=bs)
    nested_struct, new_reader = NestedStruct.parser(bytes_reader)
    assert nested_struct.value_a.value_a.value == value_a
    assert nested_struct.value_a.value_b.value == value_b

    print(nested_struct)


LinkedList = create_struct_definition(
    "LinkedList",
    {
        "value_a": Int4Definition,
        "p_next": create_forward_pointer(Int4Definition),
    },
)


def test_pointer_to_self_struct() -> None:
    base_addr = 0x10
    value_a = 0
    p_next = 0x8 + base_addr
    next_value_a = 5
    next_p_next = 0x0

    bs = b"".join(map(int_to_le_bytes_4, [value_a, p_next, next_value_a, next_p_next]))
    bytes_reader = BytesReader(address=base_addr, bs=bs)
    linked_list, new_reader = LinkedList.parser(bytes_reader)
    assert linked_list.value_a.value == value_a
    next_inst_parsed = linked_list.p_next.resolve(new_reader)
    assert next_inst_parsed.value_a.value == next_value_a
    assert next_inst_parsed.p_next.address == next_p_next

    print(linked_list)
    print(next_inst_parsed)


class E(Enum):
    a = 0
    b = 3
    c = 5


def test_enumeration():
    num = 0x3
    Int4DefinitionEnum = create_int_definition(
        "Int4DefinitionEnum",
        Int4Definition,
        E,
    )

    num_as_bytes = int_to_le_bytes_4(num)
    bytes_reader = BytesReader(address=0, bs=num_as_bytes)
    int_4_definition_enum, new_reader = Int4DefinitionEnum.parser(bytes_reader)
    assert int_4_definition_enum.value == num
    print(int_4_definition_enum)
    print(repr(int_4_definition_enum))
    print(str(int_4_definition_enum))
