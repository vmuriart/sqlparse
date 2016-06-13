# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andi Albrecht, albrecht.andi@gmail.com
#
# This module is part of python-sqlparse and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php

from sqlparse import sql, tokens as T
from sqlparse.compat import text_type
from sqlparse.utils import offset, indent


class AlignedIndentFilter(object):
    split_words = ('FROM',
                   '\bON',
                   'WHERE', 'AND', 'OR',
                   'GROUP\s+BY', 'HAVING', 'LIMIT',
                   'ORDER', 'UNION', 'CONNECT',
                   'SET', 'BETWEEN', 'EXCEPT')

    def __init__(self, char=' ', n='\n', width=11):
        self.n = n
        self.offset = 0
        self.indent = 0
        self.char = char
        self._max_kwd_len = len('select')
        self.width = width
        self.curr_stmt = None

    def nl(self):
        return sql.Token(T.Whitespace, '\n' + ' ' * self.leading_ws)

    def _process_statement(self, tlist):
        if tlist.tokens[0].is_whitespace() and self.indent == 0:
            tlist.tokens.pop(0)

        # process the main query body
        self._process(sql.TokenList(tlist.tokens))

    def _process_parenthesis(self, tlist):
        self._process_default(tlist)

    def _process_identifierlist(self, tlist):
        if not tlist.within(sql.Function):
            identifiers = list(tlist.get_identifiers())
            t0 = identifiers.pop(0)
            with offset(self, self.get_offset(t0)):
                [tlist.insert_before(token, self.nl()) for token in
                 identifiers]
        self._process_default(tlist)

    def _process_case(self, tlist):
        cases = tlist.get_cases(skip_ws=True)
        cond_width = [len(' '.join(map(str, cond))) if cond else 0 for cond, _
                      in cases]
        max_cond_width = max(cond_width)

        end_token = tlist.token_next_by(
            m=sql.Case.M_CLOSE)  # align the end as well
        cases.append((None, [end_token]))

        with offset(self, len('case ')):
            for i, (cond, value) in enumerate(cases):
                # Cond is None == else or end
                stmt = cond[0] if cond else value[0]

                ws = sql.Token(T.Whitespace, ' ' * (
                    max_cond_width - cond_width[i])) if cond else None
                tlist.insert_before(stmt, self.nl()) if i > 0 else None
                tlist.insert_after(cond[-1], ws) if cond else None

    def _next_token(self, tlist, idx=0):
        split_words = [(T.Keyword, self.split_words, True),
                       (T.CTE, 'WITH'),
                       (T.Keyword.DML, 'SELECT')]
        token = tlist.token_next_by(m=split_words, idx=idx)
        # treat "BETWEEN x and y" as a single statement
        if token and token.value.upper() == 'BETWEEN':
            token = self._next_token(tlist, token)
            if token and token.value.upper() == 'AND':
                token = self._next_token(tlist, token)
        return token

    def _split_kwds(self, tlist):
        token = self._next_token(tlist)
        while token:
            tlist.insert_before(token, self.nl())
            ws = len('SELECT') - len(token)
            if ws > 0:
                ws = sql.Token(T.Whitespace, ' ' * ws)
                tlist.insert_before(token, ws)

            token = self._next_token(tlist, token)

    def _process_default(self, tlist):
        self._split_kwds(tlist)
        # process any sub-sub statements
        for sgroup in tlist.get_sublists():
            prev = tlist.token_prev(sgroup)
            # HACK: make "group/order by" work. Longer than max_len.
            offset_ = 3 if prev and prev.match(T.Keyword, '.*BY', True) else 0
            with offset(self, offset_):
                self._process(sgroup)

    def _process(self, tlist):
        func_name = '_process_{cls}'.format(cls=type(tlist).__name__)
        func = getattr(self, func_name.lower(), self._process_default)
        func(tlist)

    def process(self, stmt):
        self.curr_stmt = stmt
        self._process(stmt)
        return stmt

    @property
    def leading_ws(self):
        return self.offset + self.indent * self.width

    def flatten_up_to(self, token):
        if isinstance(token, sql.TokenList):
            token = next(token.flatten())

        """Yields all tokens up to token but excluding current."""
        for t in self.curr_stmt.flatten():
            if t == token:
                raise StopIteration
            yield t

    def get_offset(self, token):
        raw = ''.join(map(text_type, self.flatten_up_to(token)))
        return len(raw.splitlines()[-1]) - self.leading_ws

    def _process_cte(self, tlist):
        token = tlist.token_next_by(i=sql.CTE_Subquery)
        with offset(self, self.get_offset(token)):
            token = tlist.token_next_by(i=sql.CTE_Subquery, idx=token)

            while token:
                tlist.insert_before(token, self.nl())
                token = tlist.token_next_by(i=sql.CTE_Subquery, idx=token)

        self._process_default(tlist)

    def _process_subquery(self, tlist):
        with indent(self):
            self._process_default(tlist)
            tlist.insert_before(tlist[-1], self.nl())
