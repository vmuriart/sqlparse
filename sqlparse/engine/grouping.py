# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andi Albrecht, albrecht.andi@gmail.com
#
# This module is part of python-sqlparse and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php

from sqlparse import sql
from sqlparse import tokens as T
from sqlparse.utils import imt

T_NUMERICAL = (T.Number, T.Number.Integer, T.Number.Float)
T_STRING = (T.String, T.String.Single, T.String.Symbol)
T_NAME = (T.Name, T.Name.Placeholder)


def _group_matching(tlist, cls):
    """Groups Tokens that have beginning and end."""
    opens = []
    tidx_offset = 0
    for idx, token in enumerate(list(tlist)):
        tidx = idx - tidx_offset

        if token.is_whitespace:
            # ~50% of tokens will be whitespace. Will checking early
            # for them avoid 3 comparisons, but then add 1 more comparison
            # for the other ~50% of tokens...
            continue

        if token.is_group and not isinstance(token, cls):
            # Check inside previously grouped (ie. parenthesis) if group
            # of differnt type is inside (ie, case). though ideally  should
            # should check for all open/close tokens at once to avoid recursion
            _group_matching(token, cls)
            continue

        if token.match(*cls.M_OPEN):
            opens.append(tidx)

        elif token.match(*cls.M_CLOSE):
            try:
                open_idx = opens.pop()
            except IndexError:
                # this indicates invalid sql and unbalanced tokens.
                # instead of break, continue in case other "valid" groups exist
                continue
            close_idx = tidx
            tlist.group_tokens(cls, open_idx, close_idx)
            tidx_offset += close_idx - open_idx


def group_brackets(tlist):
    _group_matching(tlist, sql.SquareBrackets)


def group_parenthesis(tlist):
    _group_matching(tlist, sql.Parenthesis)


def group_case(tlist):
    _group_matching(tlist, sql.Case)


def group_if(tlist):
    _group_matching(tlist, sql.If)


def group_for(tlist):
    _group_matching(tlist, sql.For)


def group_begin(tlist):
    _group_matching(tlist, sql.Begin)


def group_typecasts(tlist):
    def match(token):
        return token.match(T.Punctuation, '::')

    def valid(token):
        return token is not None

    def post(tlist, pidx, tidx, nidx):
        return pidx, nidx

    valid_prev = valid_next = valid
    _group(tlist, sql.Identifier, match, valid_prev, valid_next, post)


def group_period(tlist):
    def match(token):
        return token.match(T.Punctuation, '.')

    def valid_prev(token):
        sqlcls = sql.SquareBrackets, sql.Identifier
        ttypes = T.Name, T.String.Symbol
        return imt(token, i=sqlcls, t=ttypes)

    def valid_next(token):
        # issue261, allow invalid next token
        return True

    def post(tlist, pidx, tidx, nidx):
        # next_ validation is being performed here. issue261
        sqlcls = sql.SquareBrackets, sql.Function
        ttypes = T.Name, T.String.Symbol, T.Wildcard
        next_ = tlist[nidx] if nidx is not None else None
        valid_next = imt(next_, i=sqlcls, t=ttypes)

        return (pidx, nidx) if valid_next else (pidx, tidx)

    _group(tlist, sql.Identifier, match, valid_prev, valid_next, post)


def group_as(tlist):
    def match(token):
        return token.normalized == 'AS'

    def valid_prev(token):
        return token.normalized == 'NULL' or not token.is_keyword

    def valid_next(token):
        ttypes = T.DML, T.DDL
        return not imt(token, t=ttypes)

    def post(tlist, pidx, tidx, nidx):
        tlist[nidx].ttype = T.Alias
        return pidx, nidx

    _group(tlist, sql.Identifier, match, valid_prev, valid_next, post)


def group_assignment(tlist):
    def match(token):
        return token.match(T.Assignment, ':=')

    def valid(token):
        return token is not None

    def post(tlist, pidx, tidx, nidx):
        m_semicolon = T.Punctuation, ';'
        snidx, _ = tlist.token_next_by(m=m_semicolon, idx=nidx)
        nidx = snidx or nidx
        return pidx, nidx

    valid_prev = valid_next = valid
    _group(tlist, sql.Assignment, match, valid_prev, valid_next, post)


def group_comparison(tlist):
    sqlcls = (sql.Parenthesis, sql.Function, sql.Identifier,
              sql.Operation)
    ttypes = T_NUMERICAL + T_STRING + T_NAME

    def match(token):
        return token.ttype == T.Operator.Comparison

    def valid(token):
        if imt(token, t=ttypes, i=sqlcls):
            return True
        elif token and token.normalized == 'NULL':
            return True
        else:
            return False

    def post(tlist, pidx, tidx, nidx):
        return pidx, nidx

    valid_prev = valid_next = valid
    _group(tlist, sql.Comparison, match,
           valid_prev, valid_next, post, extend=False)


def group_identifier(tlist):
    ttypes = T.String.Symbol, T.Name

    def match(token):
        return imt(token, t=ttypes)

    def post(tlist, pidx, tidx, nidx):
        return tidx, tidx

    _group(tlist, sql.Identifier, match,
           post=post, extend=False)


def group_arrays(tlist):
    sqlcls = sql.SquareBrackets, sql.Identifier, sql.Function
    ttypes = T.Name, T.String.Symbol

    def match(token):
        return isinstance(token, sql.SquareBrackets)

    def valid_prev(token):
        return imt(token, i=sqlcls, t=ttypes)

    def post(tlist, pidx, tidx, nidx):
        return pidx, tidx

    _group(tlist, sql.Identifier, match,
           valid_prev, post=post, extend=True, recurse=False)


def group_operator(tlist):
    ttypes = T_NUMERICAL + T_STRING + T_NAME
    sqlcls = (sql.SquareBrackets, sql.Parenthesis, sql.Function,
              sql.Identifier, sql.Operation)

    def match(token):
        return imt(token, t=(T.Operator, T.Wildcard))

    def valid(token):
        return imt(token, i=sqlcls, t=ttypes)

    def post(tlist, pidx, tidx, nidx):
        tlist[tidx].ttype = T.Operator
        return pidx, nidx

    valid_prev = valid_next = valid
    _group(tlist, sql.Operation, match,
           valid_prev, valid_next, post, extend=False)


def group_identifier_list(tlist):
    m_role = T.Keyword, ('null', 'role')
    sqlcls = (sql.Function, sql.Case, sql.Identifier, sql.Comparison,
              sql.IdentifierList, sql.Operation)
    ttypes = (T_NUMERICAL + T_STRING + T_NAME +
              (T.Keyword, T.Comment, T.Wildcard, T.Comment.Multiline))

    def match(token):
        return token.match(T.Punctuation, ',')

    def valid(token):
        return imt(token, i=sqlcls, m=m_role, t=ttypes)

    def post(tlist, pidx, tidx, nidx):
        return pidx, nidx

    valid_prev = valid_next = valid
    _group(tlist, sql.IdentifierList, match,
           valid_prev, valid_next, post, extend=True, skip_cm=True)


def group_where(tlist):
    group_clauses(tlist, sql.Where)


def group_aliased(tlist):
    sqlcls = (sql.Parenthesis, sql.Function, sql.Case, sql.Identifier,
              sql.Operation)
    ttypes = T.Number

    def match(token):
        return isinstance(token, sql.Identifier)

    def valid_prev(token):
        return imt(token, i=sqlcls, t=ttypes)

    def post(tlist, pidx, tidx, nidx):
        tlist[tidx].ttype = T.Alias
        return pidx, tidx

    _group(tlist, sql.Identifier, match,
           valid_prev, post=post, extend=True)


def group_functions(tlist):
    has_create = False
    has_table = False
    for tmp_token in tlist.tokens:
        if tmp_token.normalized == 'CREATE':
            has_create = True
        if tmp_token.normalized == 'TABLE':
            has_table = True
    if has_create and has_table:
        return

    def match(token):
        return isinstance(token, sql.Parenthesis)

    def valid_prev(token):
        return imt(token, t=T.Name)

    def post(tlist, pidx, tidx, nidx):
        return pidx, tidx

    _group(tlist, sql.Function, match,
           valid_prev, post=post, extend=False)


def group_order(tlist):
    """Group together Identifier and Asc/Desc token"""

    def match(token):
        return token.ttype == T.Keyword.Order

    def valid_prev(token):
        return imt(token, i=sql.Identifier, t=T.Number)

    def post(tlist, pidx, tidx, nidx):
        return pidx, tidx

    _group(tlist, sql.Identifier, match,
           valid_prev, post=post, extend=False, recurse=False)


def group(stmt, advanced=False, pre=None):
    funcs = [
        # _group_matching
        group_brackets,
        group_parenthesis,
        group_case,
        group_if,
        group_for,
        group_begin,

        group_functions,
        group_where,
        group_period,
        group_arrays,
        group_identifier,
        group_operator,
        group_order,
        group_typecasts,
        group_as,
        group_aliased,
        group_assignment,
        group_comparison,

        group_identifier_list,

    ] if advanced is False else [

        # _group_matching
        group_brackets,
        group_parenthesis,
        group_case,
        group_if,
        group_for,
        group_begin,

        group_select,
        group_from,
        group_where,
        group_group_by,
        group_order_by,

        group_functions,
        group_period,
        group_arrays,
        group_identifier,
        group_operator,
        group_order,
        group_typecasts,
        group_as,
        group_aliased,
        group_assignment,
        group_comparison,

        group_identifier,
        group_order,

        group_table_stmt,
        group_identifier_list,
    ]

    for func in funcs:
        func(stmt)
    return stmt


def _group(tlist, cls, match,
           valid_prev=lambda t: True,
           valid_next=None,
           post=None,
           extend=True,
           recurse=True,
           skip_cm=False,
           ):
    """Groups together tokens that are joined by a middle token. ie. x < y"""

    tidx_offset = 0
    pidx, prev_ = None, None
    for idx, token in enumerate(list(tlist)):
        tidx = idx - tidx_offset

        if token.is_whitespace:
            continue

        if skip_cm and token.ttype in T.Comment:
            continue

        if recurse and token.is_group and not isinstance(token, cls):
            _group(token, cls, match, valid_prev, valid_next, post, extend)

        if match(token):
            if valid_next is None:
                nidx = None
                valid = valid_prev(prev_)
            else:
                nidx, next_ = tlist.token_next(tidx, skip_cm=skip_cm)
                valid = valid_prev(prev_) and valid_next(next_)

            if valid:
                from_idx, to_idx = post(tlist, pidx, tidx, nidx)
                grp = tlist.group_tokens(cls, from_idx, to_idx, extend=extend)

                tidx_offset += to_idx - from_idx
                pidx, prev_ = from_idx, grp
                continue

        pidx, prev_ = tidx, token


def group_clauses(tlist, cls, clause=None, i=None):
    tidx_offset = 0
    start_idx, start_token = None, None
    for idx, token in enumerate(list(tlist)):
        tidx = idx - tidx_offset

        if token.is_whitespace:
            continue

        if token.is_group and not isinstance(token, cls):
            group_clauses(token, cls, clause, i)

        if token.match(*cls.M_OPEN):
            start_idx, start_token = tidx, token
            continue

        if start_token is not None and token.match(*cls.M_CLOSE):
            tlist.group_tokens(cls, start_idx, tidx - 1)
            tidx_offset += tidx - 1 - start_idx
            start_idx, start_token = None, None

    if start_token is not None:
        # TODO: convert this to eidx instead of end token.
        # i think above values are len(tlist) and eidx-1
        end = tlist._groupable_tokens[-1]
        eidx = tlist.token_index(end)
        tlist.group_tokens(cls, start_idx, eidx)


def group_select(tlist):
    group_clauses(tlist, sql.Select)


def group_from(tlist):
    group_clauses(tlist, sql.From)


def group_group_by(tlist):
    group_clauses(tlist, sql.Group)


def group_order_by(tlist):
    group_clauses(tlist, sql.Order)


def group_table_stmt(tlist):
    group_clauses(tlist, sql.Table_Group, sql.From, i=sql.Identifier)
