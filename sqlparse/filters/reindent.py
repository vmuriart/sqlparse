# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andi Albrecht, albrecht.andi@gmail.com
#
# This module is part of python-sqlparse and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php

from sqlparse import sql, tokens as T
from sqlparse.compat import text_type
from sqlparse.utils import offset, indent


class ReindentFilter(object):
    def __init__(self, width=2, char=' ', wrap_after=0, n='\n'):
        self.n = n
        self.width = width
        self.char = char
        self.indent = 0
        self.offset = 0
        self.wrap_after = wrap_after
        self._curr_stmt = None
        self._last_stmt = None

    def _flatten_up_to_token(self, token):
        """Yields all tokens up to token but excluding current."""
        if token.is_group():
            token = next(token.flatten())

        for t in self._curr_stmt.flatten():
            if t == token:
                raise StopIteration
            yield t

    @property
    def leading_ws(self):
        return self.offset + self.indent * self.width

    def _get_offset(self, token):
        raw = ''.join(map(text_type, self._flatten_up_to_token(token)))
        line = (raw or '\n').splitlines()[-1]
        # Now take current offset into account and return relative offset.
        return len(line) - len(self.char * self.leading_ws)

    def nl(self):
        return sql.Token(T.Whitespace, self.n + self.char * self.leading_ws)

    def _next_token(self, tlist, idx=0):
        split_words = ('FROM', 'STRAIGHT_JOIN$', 'JOIN$', 'AND', 'OR',
                       'GROUP', 'ORDER', 'UNION', 'VALUES',
                       'SET', 'BETWEEN', 'EXCEPT', 'HAVING')
        token = tlist.token_next_by(m=(T.Keyword, split_words, True), idx=idx)

        if token and token.value.upper() == 'BETWEEN':
            token = self._next_token(tlist, token)

            if token and token.value.upper() == 'AND':
                token = self._next_token(tlist, token)

        return token

    def _split_kwds(self, tlist):
        token = self._next_token(tlist)
        while token:
            prev = tlist.token_prev(token, skip_ws=False)
            uprev = text_type(prev)

            if prev and prev.is_whitespace():
                tlist.tokens.remove(prev)

            if not (uprev.endswith('\n') or uprev.endswith('\r')):
                tlist.insert_before(token, self.nl())

            token = self._next_token(tlist, token)

    def _split_statements(self, tlist):
        token = tlist.token_next_by(t=(T.Keyword.DDL, T.Keyword.DML))
        while token:
            prev = tlist.token_prev(token, skip_ws=False)
            if prev and prev.is_whitespace():
                tlist.tokens.remove(prev)
            # only break if it's not the first token
            tlist.insert_before(token, self.nl()) if prev else None
            token = tlist.token_next_by(t=(T.Keyword.DDL, T.Keyword.DML),
                                        idx=token)

    def _process(self, tlist):
        func_name = '_process_{cls}'.format(cls=type(tlist).__name__)
        func = getattr(self, func_name.lower(), self._process_default)
        func(tlist)

    def _process_where(self, tlist):
        token = tlist.token_next_by(m=(T.Keyword, 'WHERE'))
        # issue121, errors in statement fixed??
        tlist.insert_before(token, self.nl())

        with indent(self):
            self._process_default(tlist)

    def _process_parenthesis(self, tlist):
        is_dml_dll = tlist.token_next_by(t=(T.Keyword.DML, T.Keyword.DDL))
        first = tlist.token_next_by(m=sql.Parenthesis.M_OPEN)

        with indent(self, 1 if is_dml_dll else 0):
            tlist.tokens.insert(0, self.nl()) if is_dml_dll else None
            with offset(self, self._get_offset(first) + 1):
                self._process_default(tlist, not is_dml_dll)

    def _process_identifierlist(self, tlist):
        identifiers = list(tlist.get_identifiers())
        first = next(identifiers.pop(0).flatten())
        num_offset = 1 if self.char == '\t' else self._get_offset(first)
        if not tlist.within(sql.Function):
            with offset(self, num_offset):
                [tlist.insert_before(token, self.nl()) for token in identifiers]
        self._process_default(tlist)

    def _process_case(self, tlist):
        iterable = iter(tlist.get_cases())
        cond, _ = next(iterable)
        first = next(cond[0].flatten())

        with offset(self, self._get_offset(tlist[0])):
            with offset(self, self._get_offset(first)):
                for cond, value in iterable:
                    token = value[0] if cond is None else cond[0]
                    tlist.insert_before(token, self.nl())

                # Line breaks on group level are done. let's add an offset of
                # len "when ", "then ", "else "
                with offset(self, len("WHEN ")):
                    self._process_default(tlist)
            end = tlist.token_next_by(m=sql.Case.M_CLOSE)
            tlist.insert_before(end, self.nl())

    def _process_default(self, tlist, stmts=True):
        self._split_statements(tlist) if stmts else None
        self._split_kwds(tlist)
        [self._process(sgroup) for sgroup in tlist.get_sublists()]

    def process(self, stmt):
        self._curr_stmt = stmt
        self._process(stmt)

        if self._last_stmt is not None:
            nl = '\n' if text_type(self._last_stmt).endswith('\n') else '\n\n'
            stmt.tokens.insert(0, sql.Token(T.Whitespace, nl))

        self._last_stmt = stmt
        return stmt


    def _process_subquery(self, tlist):
        # token = tlist[0]
        # tlist.insert_before(token, self.nl())

        token = tlist.token_next_by(i=sql.Select)
        with indent(self):
            tlist.insert_before(token, self.nl())
            self._process_default(tlist)
            tlist.insert_before(tlist[-1], self.nl())


    def _process_cte(self, tlist):
        token = tlist.token_next_by(i=sql.CTE_Subquery)
        with indent(self):
            while token:
                tlist.insert_before(token, self.nl())
                token = tlist.token_next_by(i=sql.CTE_Subquery, idx=token)

            token = tlist.token_next_by(m=(T.Punctuation, ','))
            while token:
                tlist.insert_after(token, self.nl())
                token = tlist.token_next_by(m=(T.Punctuation, ','), idx=token)

            self._process_default(tlist)
        tlist.insert_after(tlist[-1], self.nl())
