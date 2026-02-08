# c_struct_data_parser

Intended to facilitate declarative, dynamic definition of C data structures.
The library will autogenerate a parser which you can connect to a `BytesReader` or some IO based variant.

You're better off looking at https://github.com/fox-it/dissect.cstruct

Examples from `test_basic.py`:

```python
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

```
