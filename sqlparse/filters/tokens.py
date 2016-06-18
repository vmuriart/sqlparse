# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andi Albrecht, albrecht.andi@gmail.com
#
# This module is part of python-sqlparse and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php

from sqlparse import tokens as T
from sqlparse.compat import text_type


class _CaseFilter(object):
    ttype = None

    def __init__(self, case=None):
        case = case or 'upper'
        self.convert = getattr(text_type, case)

    def process(self, stream):
        for ttype, value in stream:
            if ttype in self.ttype:
                value = self.convert(value)
            yield ttype, value


class KeywordCaseFilter(_CaseFilter):
    ttype = T.Keyword


class IdentifierCaseFilter(_CaseFilter):
    ttype = T.Name, T.String.Symbol

    def process(self, stream):
        for ttype, value in stream:
            if ttype in self.ttype and value.strip()[0] != '"':
                value = self.convert(value)
            yield ttype, value


class TruncateStringFilter(object):
    def __init__(self, width, char):
        self.width = width
        self.char = char

    def process(self, stream):
        for ttype, value in stream:
            if ttype != T.Literal.String.Single:
                yield ttype, value
                continue

            if value[:2] == "''":
                inner = value[2:-2]
                quote = "''"
            else:
                inner = value[1:-1]
                quote = "'"

            if len(inner) > self.width:
                value = ''.join((quote, inner[:self.width], self.char, quote))
            yield ttype, value


class StripCommentsFilter(object):
    @staticmethod
    def process(stream):
        # Should this filter be handling all this whitespace changes?
        # Should single line comments be replaced by newline tokens?
        # Should comment.hints be removed as well or left intack?
        consume_ws = False
        prev_ttype, prev_value = None, None

        for ttype, value in stream:
            if consume_ws:
                if ttype in T.Whitespace:
                    continue
                else:
                    consume_ws = False
                    if (prev_ttype and prev_ttype not in T.Whitespace and
                            prev_value != '(' and value != ')'):
                        prev_ttype, prev_value = T.Whitespace, ' '
                        yield prev_ttype, prev_value

            if ttype in T.Comment:
                consume_ws = True
                continue

            prev_ttype, prev_value = ttype, value
            yield ttype, value
