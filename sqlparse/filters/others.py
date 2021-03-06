# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andi Albrecht, albrecht.andi@gmail.com
#
# This module is part of python-sqlparse and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php

from sqlparse import sql, tokens as T
from sqlparse.utils import split_unquoted_newlines


class StripWhitespaceFilter(object):
    def _stripws(self, tlist):
        func_name = '_stripws_{cls}'.format(cls=type(tlist).__name__)
        func = getattr(self, func_name.lower(), self._stripws_default)
        func(tlist)

    @staticmethod
    def _stripws_default(tlist):
        last_was_ws = False
        is_first_char = True
        for token in list(tlist.tokens):
            if token.is_whitespace:
                if last_was_ws or is_first_char:
                    tlist.tokens.remove(token)
                    continue  # continue to remove multiple ws on first char
                else:
                    token.value = ' '
            last_was_ws = token.is_whitespace
            is_first_char = False

    def _stripws_identifierlist(self, tlist):
        # Removes newlines before commas, see issue140
        last_nl = None
        for token in list(tlist.tokens):
            if last_nl and token.ttype is T.Punctuation and token.value == ',':
                tlist.tokens.remove(last_nl)
            last_nl = token if token.is_whitespace else None

            # # Add space after comma.
            # next_ = tlist.token_next(token, skip_ws=False)
            # if (next_ is not None and not next_.is_whitespace and
            #             token.ttype is T.Punctuation and token.value == ','):
            #     tlist.insert_after(token, sql.Token(T.Whitespace, ' '))
        return self._stripws_default(tlist)

    def _stripws_parenthesis(self, tlist):
        while tlist.tokens[1].is_whitespace:
            tlist.tokens.pop(1)
        while tlist.tokens[-2].is_whitespace:
            tlist.tokens.pop(-2)
        self._stripws_default(tlist)

    def process(self, stmt, depth=0):
        [self.process(sgroup, depth + 1) for sgroup in stmt.get_sublists()]
        self._stripws(stmt)
        if depth == 0 and stmt.tokens and stmt.tokens[-1].is_whitespace:
            stmt.tokens.pop(-1)
        return stmt


class SpacesAroundOperatorsFilter(object):
    @staticmethod
    def _process(tlist):

        ttypes = (T.Operator, T.Comparison)
        tidx, token = tlist.token_next_by(t=ttypes)
        while token:
            nidx, next_ = tlist.token_next(tidx, skip_ws=False)
            if next_ and next_.ttype != T.Whitespace:
                tlist.insert_after(tidx, sql.Token(T.Whitespace, ' '))

            pidx, prev_ = tlist.token_prev(tidx, skip_ws=False)
            if prev_ and prev_.ttype != T.Whitespace:
                tlist.insert_before(tidx, sql.Token(T.Whitespace, ' '))
                tidx += 1  # has to shift since token inserted before it

            # assert tlist.token_index(token) == tidx
            tidx, token = tlist.token_next_by(t=ttypes, idx=tidx)

    def process(self, stmt):
        [self.process(sgroup) for sgroup in stmt.get_sublists()]
        SpacesAroundOperatorsFilter._process(stmt)
        return stmt


# ---------------------------
# postprocess

class SerializerUnicode(object):
    @staticmethod
    def process(stmt):
        lines = split_unquoted_newlines(stmt)
        return '\n'.join(line.rstrip() for line in lines)
