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
    join_words = (r'((LEFT\s+|RIGHT\s+|FULL\s+)?'
                  r'(INNER\s+|OUTER\s+|STRAIGHT\s+)?|'
                  r'(CROSS\s+|NATURAL\s+)?)?JOIN\b')
    split_words = ('FROM',
                   join_words, r'\bON\b',
                   'WHERE', r'\bAND\b', r'\bOR\b',
                   'GROUP', 'HAVING', 'LIMIT',
                   'ORDER', 'UNION', 'VALUES',
                   '\bSET\b', 'BETWEEN', 'EXCEPT')

    def __init__(self, char=' ', n='\n'):
        self.n = n
        self.offset = 0
        self.indent = 0
        self.char = char
        self.curr_stmt = None
        self._max_kwd_len = len('select')

    def nl(self, offset=1):
        # offset = 1 represent a single space after SELECT
        offset = -len(offset) if not isinstance(offset, int) else offset
        # add two for the space and parens

        return sql.Token(T.Whitespace, self.n + self.char * (
            self.leading_ws + offset))

    def _process_statement(self, tlist):
        if tlist.tokens[0].is_whitespace and self.indent == 0:
            tlist.tokens.pop(0)

        # process the main query body
        self._process_default(tlist)

    def _process_parenthesis(self, tlist):
        # if this isn't a subquery, don't re-indent
        _, token = tlist.token_next_by(m=(T.DML, 'SELECT'))
        if token is not None:
            with indent(self):
                tlist.insert_after(tlist[0], self.nl('SELECT'))
                # process the inside of the parantheses
                self._process_default(tlist)

            # de-indent last parenthesis
            tlist.insert_before(tlist[-1], self.nl())
        else:
            with offset(self, -1):
                self._process_default(tlist)

    def _process_identifierlist(self, tlist):
        # columns being selected
        identifiers = list(tlist.get_identifiers())
        t0 = identifiers.pop(0)
        with offset(self, self.get_offset(t0)):
            [tlist.insert_before(token, self.nl(0)) for token in
             identifiers]
        self._process_default(tlist)

    def _process_case(self, tlist):
        cases = tlist.get_cases(skip_ws=True)
        # align the end as well
        _, end_token = tlist.token_next_by(m=(T.Keyword, 'END'))
        cases.append((None, [end_token]))

        condition_width = [len(' '.join(map(text_type, cond))) if cond else 0
                           for cond, _ in cases]
        max_cond_width = max(condition_width)

        offset_ = len('case ') + len('when ')
        for i, (cond, value) in enumerate(cases):
            # cond is None when 'else or end'
            stmt = cond[0] if cond else value[0]

            if i == 0:
                offset_ = self.get_offset(stmt)
            if i > 0:
                tlist.insert_before(stmt, self.nl(
                    offset_ - len(text_type(stmt)) + 4))
            if cond:
                ws = sql.Token(T.Whitespace, self.char * (
                    max_cond_width - condition_width[i]))
                tlist.insert_after(cond[-1], ws)

    def _process_default(self, tlist):
        tidx_offset = 0
        prev_kw = None  # previous keyword match
        prev_tk = None  # previous token
        for idx, token in enumerate(list(tlist)):
            tidx = idx + tidx_offset

            if token.is_whitespace:
                continue

            if token.is_group:
                # HACK: make "group/order by" work. Longer than max_len.
                offset_ = 3 if (prev_tk and prev_tk.normalized == 'BY') else 0
                with offset(self, offset_):
                    self._process(token)

            if not token.match(T.Keyword, self.split_words, regex=True):
                prev_tk = token
                continue

            if token.normalized == 'BETWEEN':
                prev_kw = token
                continue

            if token.normalized == 'AND' and prev_kw is not None and (
                    prev_kw.normalized == 'BETWEEN'):
                prev_kw = token
                continue

            if token.match(T.Keyword, self.join_words, regex=True):
                token_indent = token.value.split()[0]
            else:
                token_indent = text_type(token)

            tlist.insert_before(tidx, self.nl(token_indent))
            tidx_offset += 1

            prev_kw = prev_tk = token

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
        return (self._max_kwd_len + self.offset +
                self.indent * (2 + self._max_kwd_len))

    def flatten_up_to(self, token):
        """Yields all tokens up to token but excluding current."""
        if isinstance(token, sql.TokenList):
            token = next(token.flatten())

        for t in self.curr_stmt.flatten():
            if t == token:
                raise StopIteration
            yield t

    def get_offset(self, token):
        raw = ''.join(map(text_type, self.flatten_up_to(token)))
        return len(raw.splitlines()[-1]) - self.leading_ws
