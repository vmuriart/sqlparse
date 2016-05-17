# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andi Albrecht, albrecht.andi@gmail.com
#
# This module is part of python-sqlparse and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php

from sqlparse import sql
from sqlparse import tokens as T
from sqlparse.utils import recurse, imt, find_matching

M_ROLE = (T.Keyword, ('null', 'role'))
M_SEMICOLON = (T.Punctuation, ';')
M_COMMA = (T.Punctuation, ',')

T_NUMERICAL = (T.Number, T.Number.Integer, T.Number.Float)
T_STRING = (T.String, T.String.Single, T.String.Symbol)
T_NAME = (T.Name, T.Name.Placeholder)


def _group_left_right(tlist, m, cls,
                      valid_left=lambda t: t is not None,
                      valid_center=lambda t: t is not None,
                      valid_right=lambda t: t is not None):
    """Groups together tokens that are joined by a middle token. ie. x < y"""
    [_group_left_right(sgroup, m, cls, valid_left, valid_center, valid_right)
     for sgroup in tlist.get_sublists() if not isinstance(sgroup, cls)]

    token = tlist.token_next_by(m=m)
    while token:
        left, right = tlist.token_prev(token), tlist.token_next(token)

        if valid_left(left) and valid_center(token) and valid_right(right):
            tokens = tlist.tokens_between(left, right)
            token = tlist.group_tokens(cls, tokens, extend=True)
        token = tlist.token_next_by(m=m, idx=token)


def _group_matching(tlist, cls):
    """Groups Tokens that have beginning and end."""
    [_group_matching(sgroup, cls) for sgroup in tlist.get_sublists()
     if not isinstance(sgroup, cls)]
    idx = 1 if isinstance(tlist, cls) else 0

    token = tlist.token_next_by(m=cls.M_OPEN, idx=idx)
    while token:
        end = find_matching(tlist, token, cls.M_OPEN, cls.M_CLOSE)
        if end is not None:
            tokens = tlist.tokens_between(token, end)
            token = tlist.group_tokens(cls, tokens)
            _group_matching(token, cls)
        token = tlist.token_next_by(m=cls.M_OPEN, idx=token)


def group_if(tlist):
    _group_matching(tlist, sql.If)


def group_for(tlist):
    _group_matching(tlist, sql.For)


def group_foreach(tlist):
    _group_matching(tlist, sql.For)


def group_begin(tlist):
    _group_matching(tlist, sql.Begin)


def group_as(tlist):
    lfunc = lambda tk: not imt(tk, t=T.Keyword) or tk.value == 'NULL'

    def rfunc(tk):
        if imt(tk, t=(T.String.Symbol, T.Name)):
            tk.ttype = T.Alias
            return True

    _group_left_right(tlist, (T.Keyword, 'AS'), sql.Identifier,
                      valid_left=lfunc, valid_right=rfunc)


def group_assignment(tlist):
    _group_left_right(tlist, (T.Assignment, ':='), sql.Assignment)


def group_comparison(tlist):
    I_COMPERABLE = (sql.Parenthesis, sql.Function, sql.Identifier,
                    sql.Operation)
    T_COMPERABLE = T_NUMERICAL + T_STRING + T_NAME

    func = lambda tk: (imt(tk, t=T_COMPERABLE, i=I_COMPERABLE) or
                       (tk and tk.is_keyword and tk.normalized == 'NULL'))

    _group_left_right(tlist, (T.Operator.Comparison, None), sql.Comparison,
                      valid_left=func, valid_right=func)


def group_case(tlist):
    _group_matching(tlist, sql.Case)


@recurse()
def group_identifier(tlist):
    T_IDENT = (T.String.Symbol, T.Name, T.Wildcard)
    if isinstance(tlist, (sql.Identifier, sql.Function)):
        return

    token = tlist.token_next_by(t=T_IDENT)
    while token:
        token = tlist.group_tokens(sql.Identifier, [token, ])
        token = tlist.token_next_by(t=T_IDENT, idx=token)


def group_period(tlist):
    lfunc = lambda tk: imt(tk, i=(sql.SquareBrackets, sql.Identifier),
                           t=(T.Name, T.String.Symbol,))

    rfunc = lambda tk: imt(tk, i=(sql.SquareBrackets, sql.Function),
                           t=(T.Name, T.String.Symbol, T.Wildcard))

    _group_left_right(tlist, (T.Punctuation, '.'), sql.Identifier,
                      valid_left=lfunc, valid_right=rfunc)


def group_arrays(tlist):
    token = tlist.token_next_by(i=sql.SquareBrackets)
    while token:
        prev = tlist.token_prev(token)
        if imt(prev, i=(sql.SquareBrackets, sql.Identifier, sql.Function),
               t=(T.Name, T.String.Symbol,)):
            tokens = tlist.tokens_between(prev, token)
            token = tlist.group_tokens(sql.Identifier, tokens, extend=True)
        token = tlist.token_next_by(i=sql.SquareBrackets, idx=token)


@recurse(sql.Identifier)
def group_operator(tlist):
    I_CYCLE = (sql.SquareBrackets, sql.Parenthesis, sql.Function,
               sql.Identifier, sql.Operation)
    # wilcards wouldn't have operations next to them
    T_CYCLE = T_NUMERICAL + T_STRING + T_NAME
    func = lambda tk: imt(tk, i=I_CYCLE, t=T_CYCLE)

    token = tlist.token_next_by(t=(T.Operator, T.Wildcard))
    while token:
        left, right = tlist.token_prev(token), tlist.token_next(token)

        if func(left) and func(right):
            token.ttype = T.Operator
            tokens = tlist.tokens_between(left, right)
            token = tlist.group_tokens(sql.Operation, tokens)

        token = tlist.token_next_by(t=(T.Operator, T.Wildcard), idx=token)


@recurse(sql.IdentifierList)
def group_identifier_list(tlist):
    I_IDENT_LIST = (sql.Function, sql.Case, sql.Identifier,
                    sql.IdentifierList, sql.Operation)
    T_IDENT_LIST = (T_NUMERICAL + T_STRING + T_NAME +
                    (T.Keyword, T.Comment, T.Wildcard))

    if isinstance(tlist, sql.From):
        return

    func = lambda t: imt(t, i=I_IDENT_LIST, m=M_ROLE, t=T_IDENT_LIST)
    token = tlist.token_next_by(m=M_COMMA)

    while token:
        before, after = tlist.token_prev(token), tlist.token_next(token)

        if func(before) and func(after):
            tokens = tlist.tokens_between(before, after)
            token = tlist.group_tokens(sql.IdentifierList, tokens, extend=True)
        token = tlist.token_next_by(m=M_COMMA, idx=token)


def group_brackets(tlist):
    _group_matching(tlist, sql.SquareBrackets)


def group_parenthesis(tlist):
    _group_matching(tlist, sql.Parenthesis)


@recurse(sql.Comment)
def group_comments(tlist):
    token = tlist.token_next_by(t=T.Comment)
    while token:
        end = tlist.token_not_matching(
            token, lambda tk: imt(tk, t=T.Comment) or tk.is_whitespace())
        if end is not None:
            end = tlist.token_prev(end, False)
            tokens = tlist.tokens_between(token, end)
            token = tlist.group_tokens(sql.Comment, tokens)

        token = tlist.token_next_by(t=T.Comment, idx=token)


def group_where(tlist):
    group_clauses(tlist, sql.Where)


@recurse()
def group_aliased(tlist):
    I_ALIAS = (sql.Parenthesis, sql.Function, sql.Case, sql.Identifier,
               sql.Operation, sql.Subquery)

    token = tlist.token_next_by(i=I_ALIAS, t=T_NUMERICAL + (T.Name,))
    while token:
        next_ = tlist.token_next(token)
        if imt(next_, t=(T.String.Symbol, T.Name)):
            tokens = tlist.tokens_between(token, next_)
            token = tlist.group_tokens(sql.Identifier, tokens, extend=True)
        token = tlist.token_next_by(i=I_ALIAS, t=T_NUMERICAL + (T.Name,),
                                    idx=token)


def group_typecasts(tlist):
    _group_left_right(tlist, (T.Punctuation, '::'), sql.Identifier)


@recurse(sql.Function)
def group_functions(tlist):
    has_create = False
    has_table = False
    for tmp_token in tlist.tokens:
        if tmp_token.value == 'CREATE':
            has_create = True
        if tmp_token.value == 'TABLE':
            has_table = True
    if has_create and has_table:
        return
    token = tlist.token_next_by(t=T.Name)
    while token:
        next_ = tlist.token_next(token)
        if imt(next_, i=sql.Parenthesis):
            tokens = tlist.tokens_between(token, next_)
            token = tlist.group_tokens(sql.Function, tokens)
        token = tlist.token_next_by(t=T.Name, idx=token)


@recurse()
def group_order(tlist):
    """Group together Identifier and Asc/Desc token"""
    token = tlist.token_next_by(t=T.Keyword.Order)
    while token:
        prev = tlist.token_prev(token)
        if imt(prev, i=sql.Identifier, t=T.Number):
            tokens = tlist.tokens_between(prev, token)
            token = tlist.group_tokens(sql.Identifier, tokens, extend=True)
        token = tlist.token_next_by(t=T.Keyword.Order, idx=token)


@recurse()
def align_comments(tlist):
    token = tlist.token_next_by(i=sql.Comment)
    while token:
        before = tlist.token_prev(token)
        if isinstance(before, sql.TokenList):
            tokens = tlist.tokens_between(before, token)
            token = tlist.group_tokens(sql.TokenList, tokens, extend=True)
        token = tlist.token_next_by(i=sql.Comment, idx=token)


def group_clauses(tlist, cls, clause=None, i=None):
    [group_clauses(sgroup, cls, clause, i) for sgroup in tlist.get_sublists()
     if not isinstance(sgroup, cls)]

    if clause is None or imt(tlist, i=clause):
        token = tlist.token_next_by(i=i, m=cls.M_OPEN)
        while token:
            end = tlist.token_next_by(m=cls.M_CLOSE, idx=token)
            end = tlist.token_prev(idx=end) or tlist._groupable_tokens[-1]

            tokens = tlist.tokens_between(token, end)
            token = tlist.group_tokens(cls, tokens)
            token = tlist.token_next_by(i=i, m=cls.M_OPEN, idx=token)


def group_cte(tlist):
    group_clauses(tlist, sql.CTE)


def group_as_cte(tlist):
    def lfunc(tk):
        if imt(tk, t=(T.String.Symbol, T.Name)):
            tk.ttype = T.Alias
            return True

    def rfunc(tk):
        if imt(tk, i=sql.Subquery):
            return True

    _group_left_right(tlist, sql.Identifier.M_AS, sql.CTE_Subquery,
                      valid_left=lfunc, valid_right=rfunc)


def group_over(tlist):
    lfunc = lambda tk: imt(tk, i=sql.Function)
    rfunc = lambda tk: imt(tk, i=sql.Parenthesis)

    _group_left_right(tlist, sql.Function.M_OVER, sql.Function,
                      valid_left=lfunc, valid_right=rfunc)


def group_connect(tlist):
    group_clauses(tlist, sql.Connect)


def group_join(tlist):
    group_clauses(tlist, sql.Join_Clause)


@recurse()
def group_subquery(tlist):
    token = tlist.token_next_by(i=sql.Parenthesis)
    while token:
        if token.is_subquery():
            idx = tlist.token_index(token)
            tlist.tokens[idx] = sql.Subquery(token.tokens)
            token = tlist[idx]

        token = tlist.token_next_by(i=sql.Parenthesis, idx=token)


@recurse(sql.ComparisonList)
def group_comparison_list(tlist):
    I_IDENT_LIST = (sql.Function, sql.Case, sql.Identifier, sql.Comparison,
                    sql.ComparisonList, sql.Operation)
    T_IDENT_LIST = T_NUMERICAL + T_STRING + T_NAME + (
        T.Keyword, T.Comment, T.Wildcard)

    func = lambda t: imt(t, m=(T.Keyword, ('null', 'role')),
                         i=I_IDENT_LIST, t=T_IDENT_LIST)
    token = tlist.token_next_by(m=sql.ComparisonList.M_SEPARATOR)

    while token:
        before, after = tlist.token_prev(token), tlist.token_next(token)

        if func(before) and func(after):
            tokens = tlist.tokens_between(before, after)
            token = tlist.group_tokens(sql.ComparisonList, tokens,
                                       extend=True)
        token = tlist.token_next_by(m=sql.ComparisonList.M_SEPARATOR,
                                    idx=token)


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


def group(stmt):
    for func in [
        group_parenthesis,
        group_brackets,
        group_case,

        group_cte,
        group_select,
        group_from,
        group_where,
        group_connect,
        group_group_by,
        group_order_by,

        group_subquery,

        group_functions,
        group_over,

        group_period,

        group_operator,
        group_comparison,

        group_as,
        group_as_cte,
        group_aliased,

        group_identifier,
        group_order,

        group_join,
        group_table_stmt,
        group_comparison_list,
        group_identifier_list,
    ]:
        func(stmt)
    return stmt
