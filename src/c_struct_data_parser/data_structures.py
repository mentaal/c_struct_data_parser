from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import partial, reduce
from itertools import chain
from operator import attrgetter, methodcaller
from textwrap import indent
from typing import Dict, Literal, Optional, Sequence, Tuple, Type

from .parser import create_repeat_parser, create_sequence_parser, Parser, Reader


int_from_bytes_le = partial(int.from_bytes, byteorder="little")

get_parser = attrgetter("parser")
from_register = partial(methodcaller, "from_register")
get_size = attrgetter("size")

indent_4 = partial(indent, prefix="    ")


@dataclass
class Metadata:
    address: int


class DataDefinition(ABC):
    size: int = 0

    @classmethod
    @abstractmethod
    def parser(cls, reader: Reader) -> Tuple[DataDefinition, Reader]: ...

    def __init__(
        self,
        metadata: Optional[Metadata],
    ):
        self.metadata = metadata

    def __repr__(self) -> str:
        cls_name = type(self).__name__
        return f"{cls_name}({self.add_metadata_repr()})"

    def add_metadata_repr(self, *args: str) -> str:
        m = self.metadata
        args_str = ", ".join(args)
        if m:
            prefix = ", " if args else ""
            return f"{args_str}{prefix}Metadata(address={m.address:#x})"
        return args_str


class IntDefinition(DataDefinition):
    size: int = 0  # num bytes
    byteorder: Literal["little", "big"] = "little"
    _enum_type: Optional[Type[Enum]] = None

    def __init__(
        self,
        value: int | Enum,
        metadata: Optional[Metadata] = None,
    ):

        super().__init__(metadata)
        if isinstance(value, int):
            self.value = value
        elif self._enum_type and isinstance(value, self._enum_type):
            self.value = value.value
        else:
            raise ValueError(f"Unexpected value type: {type(value)}")

    @classmethod
    def parser(cls, reader: Reader) -> Tuple[IntDefinition, Reader]:
        address, data_bytes = reader.read(cls.size)
        return cls(int.from_bytes(data_bytes, byteorder=cls.byteorder), metadata=Metadata(address)), reader

    def __repr__(self) -> str:
        cls_name = type(self).__name__
        val = self.value
        enum_type = self._enum_type
        if enum_type:
            try:
                val_str = str(enum_type(val))
            except ValueError:
                val_str = hex(val)
        else:
            val_str = hex(val)

        return f"{cls_name}({self.add_metadata_repr(val_str)})"

    def __str__(self) -> str:
        cls_name = type(self).__name__
        val = self.value
        enum_type = self._enum_type
        if enum_type:
            try:
                val_str = repr(enum_type(val))  # repr(Enum(<num>)) looks more like str(Enum(<num>)) and vice versa
            except ValueError:
                val_str = f"{val:#x} ({val}) not a valid Enumeration of type: {enum_type}"
        else:
            val_str = hex(val)

        return f"{cls_name}({self.add_metadata_repr(val_str)})"


class Int4Definition(IntDefinition):
    size: int = 4


class Int1Definition(IntDefinition):
    size: int = 1


class Int2Definition(IntDefinition):
    size: int = 2


def create_int_definition(
    name: str,
    int_definition: Type[IntDefinition],
    enumeration: Optional[Type[Enum]] = None,
) -> Type[IntDefinition]:
    attrs = {"_enum_type": enumeration} if enumeration else {}
    return type(
        name,
        (int_definition,),
        attrs,
    )


class StructDefinition(DataDefinition):
    size: int = 0
    field_types: Dict[str, Type[DataDefinition]] = {}

    def __init__(
        self,
        fields: Sequence[DataDefinition],
        metadata: Optional[Metadata] = None,
    ):
        super().__init__(metadata)
        self.fields = tuple(fields)
        fields_len = len(fields)
        field_types_len = len(self.field_types)
        if fields_len != field_types_len:
            raise ValueError(f"Supplied number of fields: {fields_len} doesn't match expectation: {field_types_len}")
        for (k, t), v in zip(self.field_types.items(), fields):
            if not isinstance(v, t):
                raise ValueError(f"Got unexpected value: {v} for type: {t}")
            setattr(self, k, v)

    def __str__(self) -> str:
        cls_name = type(self).__name__

        fields_strs = map(lambda k, v: f"{k}: {v}", self.field_types.keys(), map(str, self.fields))
        fields_strs_indented = map(indent_4, fields_strs)
        fields_str = "\n".join(fields_strs_indented)
        return f"{cls_name} {self.add_metadata_repr()}:\n{fields_str}"

    @classmethod
    def parser(cls, reader: Reader) -> Tuple[StructDefinition, Reader]:
        raise NotImplementedError(f"{cls} is abstract")


@dataclass
class ForwardPointer:
    address_type: Type[IntDefinition]


def create_forward_pointer(
    address_type: Type[IntDefinition],
) -> ForwardPointer:
    return ForwardPointer(address_type)


def replace_forward_pointer(
    target_type: Type[DataDefinition], field_type: Type[DataDefinition] | ForwardPointer
) -> Type[DataDefinition]:
    if isinstance(field_type, ForwardPointer):
        return _create_pointer_definition_from_forward_pointer(target_type, field_type)
    else:
        return field_type


def create_struct_definition(
    struct_name: str,
    field_types: Dict[str, Type[DataDefinition] | ForwardPointer],
) -> Type[StructDefinition]:

    new_struct = type(
        struct_name,
        (StructDefinition,),
        {},
    )

    normalized_field_types = {k: replace_forward_pointer(new_struct, v) for (k, v) in field_types.items()}
    sequence_parser = create_sequence_parser(*map(get_parser, normalized_field_types.values()))

    @classmethod
    def parser(cls: Type[StructDefinition], reader: Reader) -> Tuple[StructDefinition, Reader]:
        parsed_field_results, new_reader = sequence_parser(reader)
        metadata = Metadata(parsed_field_results[0].metadata.address)
        return cls(parsed_field_results, metadata=metadata), new_reader

    new_struct.field_types = normalized_field_types
    new_struct.parser = parser
    new_struct.size = sum(map(get_size, normalized_field_types.values()))

    return new_struct


class BitFieldDefinition:
    size: int
    position: int
    mask: int

    def __init__(
        self,
        value: int,
    ):
        if value > self.mask:
            raise ValueError(f"Passed in value: {value:#x} greater than mask: {self.mask:#x}")
        self.value = value

    def __repr__(self):
        cls_name = type(self).__name__
        return f"{cls_name}({self.value:#x})"

    def __str__(self):
        cls_name = type(self).__name__
        return f"{cls_name}: {self.value:#x}"

    @classmethod
    def from_register(cls, value: int) -> BitFieldDefinition:
        return cls((value >> cls.position) & cls.mask)


class BitFieldsDefinition(DataDefinition):
    field_types: Dict[str, Type[BitFieldDefinition]]
    IntDefinition: Type[IntDefinition]
    size: int

    def __init__(
        self,
        value: int,
        metadata: Optional[Metadata],
    ):
        super().__init__(metadata)
        self.value = value
        self.fields = tuple(map(from_register(value), self.field_types.values()))
        fields_len = len(self.fields)
        field_types_len = len(self.field_types)

        if fields_len != field_types_len:
            raise ValueError(f"Supplied number of fields: {fields_len} doesn't match expectation: {field_types_len}")
        for (k, t), v in zip(self.field_types.items(), self.fields):
            if not isinstance(v, t):
                raise ValueError(f"Got unexpected value: {v} for type: {t}")
            setattr(self, k, v)

    @classmethod
    def parser(cls, reader: Reader) -> Tuple[BitFieldsDefinition, Reader]:
        int_definition, new_reader = cls.IntDefinition.parser(reader)
        return (
            cls(
                int_definition.value,
                metadata=int_definition.metadata,
            ),
            new_reader,
        )

    def __repr__(self) -> str:
        cls_name = type(self).__name__
        return f"{cls_name}({self.add_metadata_repr(hex(self.value))})"

    def __str__(self) -> str:
        cls_name = type(self).__name__
        fields_strs = map(str, self.fields)
        fields_strs_indented = map(indent_4, fields_strs)
        fields_str = "\n".join(fields_strs_indented)
        return f"{cls_name}({self.add_metadata_repr(hex(self.value))})\n{fields_str}"


BitFieldDef = Tuple[str, int]
BitFieldDefs = Dict[str, int]


def _create_bit_field_definition_from_bit_field_def(position: int, bf_def: BitFieldDef) -> Type[BitFieldDefinition]:
    name, size = bf_def
    bit_field_definition = type(
        name,
        (BitFieldDefinition,),
        {
            "size": size,
            "position": position,
            "mask": (1 << size) - 1,
        },
    )

    return bit_field_definition


PosFieldsTup = Tuple[int, Tuple[Type[BitFieldDefinition], ...]]


def _create_fields_reducer(pos_fields_tup: PosFieldsTup, field_def: BitFieldDef) -> PosFieldsTup:
    pos, fields = pos_fields_tup
    name, size = field_def
    new_field = _create_bit_field_definition_from_bit_field_def(pos, field_def)
    return (pos + size, tuple(chain(fields, [new_field])))


def create_bit_fields_definition(
    name: str,
    int_definition: Type[IntDefinition],
    field_defs: BitFieldDefs,
) -> Type[BitFieldsDefinition]:
    empty_tuple = ()

    size, fields = reduce(_create_fields_reducer, field_defs.items(), (0, empty_tuple))
    fields_dict = dict(zip(field_defs.keys(), fields, strict=True))
    return type(
        name,
        (BitFieldsDefinition,),
        {
            "field_types": fields_dict,
            "IntDefinition": int_definition,
            "size": int_definition.size,
        },
    )


class PointerDefinition(DataDefinition):
    size: int = 0
    target_type: Type[DataDefinition]
    address_type: Type[IntDefinition] = Int4Definition
    is_forward_ref: bool = False

    def __init__(
        self,
        address: int,
        metadata: Optional[Metadata],
    ):
        super().__init__(metadata)
        self.address = address

    def __repr__(self) -> str:
        cls_name = type(self).__name__
        return f"{cls_name}({self.add_metadata_repr(hex(self.address))})"

    def __str__(self) -> str:
        cls_name = type(self).__name__

        target_name = self.target_type.__name__
        p_str = f"pointer to object of type: {target_name}"
        return (
            f"{cls_name}({self.add_metadata_repr(hex(self.address))})\n*{self.address:#x} -> {target_name} :: {p_str}"
        )

    @classmethod
    def parser(cls, reader: Reader) -> Tuple[PointerDefinition, Reader]:
        int_definition, new_reader = cls.address_type.parser(reader)
        return (cls(int_definition.value, metadata=int_definition.metadata), new_reader)

    def resolve(self, reader: Reader) -> DataDefinition:
        if self.address == 0:
            raise ValueError(f"Attempting to resolve a null pointer: {self}")
        new_reader = reader.new_reader(self.address)
        resolved, _ = self.target_type.parser(new_reader)
        return resolved


def create_pointer_definition(
    target_type: Type[DataDefinition],
    address_type: Type[IntDefinition],
) -> Type[PointerDefinition]:
    return type(
        f"Pointer2{target_type.__name__}",
        (PointerDefinition,),
        {
            "target_type": target_type,
            "address_type": address_type,
            "size": target_type.size,
        },
    )


def _create_pointer_definition_from_forward_pointer(
    target_type: Type[DataDefinition],
    forward_pointer: ForwardPointer,
) -> Type[PointerDefinition]:
    return create_pointer_definition(
        target_type=target_type,
        address_type=forward_pointer.address_type,
    )


class ArrayDefinition(DataDefinition):
    target_type: Type[DataDefinition]
    size: int
    _fields_parser: Parser
    _array_splitter = "\n" + 80 * "=" + "\n"

    def __init__(
        self,
        fields: Sequence[DataDefinition],
        metadata: Optional[Metadata],
    ):
        super().__init__(metadata)
        self.fields = fields

    def __str__(self) -> str:
        cls_name = type(self).__name__
        target_cls = self.target_type.__name__
        fields_strs = map(str, self.fields)
        fields_strs_indented = map(indent_4, fields_strs)
        fields_str = self._array_splitter.join(fields_strs_indented)
        return f"{cls_name}:: {target_cls}[{self.size}] {self.add_metadata_repr()}:\n{fields_str}"

    @classmethod
    def parser(cls, reader: Reader) -> Tuple[ArrayDefinition, Reader]:
        fields, new_reader = cls._fields_parser(reader)
        return cls(fields, metadata=fields[0].metadata), new_reader


def create_array_definition(
    target_type: Type[DataDefinition],
    size: int,
) -> Type[ArrayDefinition]:
    fields_parser = create_repeat_parser(size, target_type.parser)
    return type(
        f"{target_type.__name__}Array",
        (ArrayDefinition,),
        {
            "target_type": target_type,
            "size": size,
            "_fields_parser": fields_parser,
        },
    )
