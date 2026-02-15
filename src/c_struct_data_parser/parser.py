from __future__ import annotations

from functools import reduce
from itertools import chain, repeat
from typing import (
    Any,
    Callable,
    Tuple,
    TypeVar,
)

from .reader_abc import Reader


T = TypeVar("T")
A = TypeVar("A")
B = TypeVar("B")

Parser = Callable[[Reader], Tuple[T, Reader]]
MakeParser = Callable[[A], Parser[B]]
ResultsTup = Tuple[Tuple[Any], Reader]


def fmap_parser(func: Callable[[A], B], parser: Parser[A]) -> Parser[B]:
    def fmapped_parser(reader: Reader) -> Tuple[B, Reader]:
        result_from_parser, result_reader = parser(reader)
        return func(result_from_parser), result_reader

    return fmapped_parser


def combine_parsers(
    parser_a: Parser[A],
    make_parser_b: MakeParser[A, B],
) -> Parser:
    ">>= (bind) if you squint"

    def combined_parser(reader: Reader) -> Tuple[B, Reader]:
        val_a, reader_a = parser_a(reader)
        parser_b = make_parser_b(val_a)
        return parser_b(reader_a)

    return combined_parser


def parser_reducer(results_tup: ResultsTup, parser: Parser) -> ResultsTup:
    results, reader = results_tup
    parser_res, parser_reader = parser(reader)
    new_results = tuple(chain(results, [parser_res]))
    return new_results, parser_reader


def create_sequence_parser(*parsers: Parser) -> Parser[Tuple[Any]]:
    empty_tuple = ()

    def sequence_parser(reader: Reader) -> ResultsTup:
        initial: Tuple[Tuple[Any, ...], Reader] = (empty_tuple, reader)
        return reduce(parser_reducer, parsers, initial)

    return sequence_parser


def create_repeat_parser(num: int, parser: Parser) -> Parser:
    return create_sequence_parser(*repeat(parser, num))
