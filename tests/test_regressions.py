# -*- coding: utf-8 -*-

import sys

from tests.utils import TestCaseBase, load_file

import sqlparse
from sqlparse import sql
from sqlparse import tokens as T


class RegressionTests(TestCaseBase):

    def test_issue9(self):
        # make sure where doesn't consume parenthesis
        p = sqlparse.parse('(where 1)')[0]
        self.assert_(isinstance(p, sql.Statement))
        self.assertEqual(len(p.tokens), 1)
        self.assert_(isinstance(p.tokens[0], sql.Parenthesis))
        prt = p.tokens[0]
        self.assertEqual(len(prt.tokens), 3)
        self.assertEqual(prt.tokens[0].ttype, T.Punctuation)
        self.assertEqual(prt.tokens[-1].ttype, T.Punctuation)

    def test_issue13(self):
        parsed = sqlparse.parse(("select 'one';\n"
                                 "select 'two\\'';\n"
                                 "select 'three';"))
        self.assertEqual(len(parsed), 3)
        self.assertEqual(str(parsed[1]).strip(), "select 'two\\'';")

    def test_issue26(self):
        # parse stand-alone comments
        p = sqlparse.parse('--hello')[0]
        self.assertEqual(len(p.tokens), 1)
        self.assert_(p.tokens[0].ttype is T.Comment.Single)
        p = sqlparse.parse('-- hello')[0]
        self.assertEqual(len(p.tokens), 1)
        self.assert_(p.tokens[0].ttype is T.Comment.Single)
        p = sqlparse.parse('--hello\n')[0]
        self.assertEqual(len(p.tokens), 1)
        self.assert_(p.tokens[0].ttype is T.Comment.Single)
        p = sqlparse.parse('--')[0]
        self.assertEqual(len(p.tokens), 1)
        self.assert_(p.tokens[0].ttype is T.Comment.Single)
        p = sqlparse.parse('--\n')[0]
        self.assertEqual(len(p.tokens), 1)
        self.assert_(p.tokens[0].ttype is T.Comment.Single)

    def test_issue34(self):
        t = sqlparse.parse("create")[0].token_next()
        self.assertEqual(t.match(T.Keyword.DDL, "create"), True)
        self.assertEqual(t.match(T.Keyword.DDL, "CREATE"), True)

    def test_issue35(self):
        # missing space before LIMIT
        sql = sqlparse.format("select * from foo where bar = 1 limit 1",
                              reindent=True)
        self.ndiffAssertEqual(sql, "\n".join(["select *",
                                              "from foo",
                                              "where bar = 1 limit 1"]))

    def test_issue38(self):
        sql = sqlparse.format("SELECT foo; -- comment",
                              strip_comments=True)
        self.ndiffAssertEqual(sql, "SELECT foo;")
        sql = sqlparse.format("/* foo */", strip_comments=True)
        self.ndiffAssertEqual(sql, "")

    def test_issue39(self):
        p = sqlparse.parse('select user.id from user')[0]
        self.assertEqual(len(p.tokens), 3)

        idt = p.tokens[0][2]
        self.assertEqual(idt.__class__, sql.Identifier)
        self.assertEqual(len(idt.tokens), 3)
        self.assertEqual(idt.tokens[0].match(T.Name, 'user'), True)
        self.assertEqual(idt.tokens[1].match(T.Punctuation, '.'), True)
        self.assertEqual(idt.tokens[2].match(T.Name, 'id'), True)

    def test_issue40(self):
        # make sure identifier lists in subselects are grouped
        p = sqlparse.parse(('SELECT id, name FROM (SELECT id, name FROM bar) as foo'))[0]
        self.assertEqual(len(p.tokens), 3)
        self.assertEqual(p.tokens[0][2].__class__, sql.IdentifierList)
        self.assertEqual(p.tokens[-1][-1].__class__, sql.Identifier)


def test_issue78():
    # the bug author provided this nice examples, let's use them!
    def _get_identifier(sql):
        p = sqlparse.parse(sql)[0]
        return p.tokens[2]
    results = (('get_name', 'z'),
               ('get_real_name', 'y'),
               ('get_parent_name', 'x'),
               ('get_alias', 'z'),
               ('get_typecast', 'text'))
    variants = (
        'select x.y::text as z from foo',
        'select x.y::text as "z" from foo',
        'select x."y"::text as z from foo',
        'select x."y"::text as "z" from foo',
        'select "x".y::text as z from foo',
        'select "x".y::text as "z" from foo',
        'select "x"."y"::text as z from foo',
        'select "x"."y"::text as "z" from foo',
    )
    for variant in variants:
        i = _get_identifier(variant)
        assert isinstance(i, sql.Identifier)
        for func_name, result in results:
            func = getattr(i, func_name)
            assert func() == result


def test_issue83():
    sql = """
CREATE OR REPLACE FUNCTION func_a(text)
  RETURNS boolean  LANGUAGE plpgsql STRICT IMMUTABLE AS
$_$
BEGIN
 ...
END;
$_$;

CREATE OR REPLACE FUNCTION func_b(text)
  RETURNS boolean  LANGUAGE plpgsql STRICT IMMUTABLE AS
$_$
BEGIN
 ...
END;
$_$;

ALTER TABLE..... ;"""
    t = sqlparse.split(sql)
    assert len(t) == 3


def test_comment_encoding_when_reindent():
    # There was an UnicodeEncodeError in the reindent filter that
    # casted every comment followed by a keyword to str.
    sql = u'select foo -- Comment containing Ümläuts\nfrom bar'
    formatted = sqlparse.format(sql, reindent=True)
    assert formatted == sql


def test_parse_sql_with_binary():
    # See https://github.com/andialbrecht/sqlparse/pull/88
    # digest = '|ËêplL4¡høN{'
    digest = '\x82|\xcb\x0e\xea\x8aplL4\xa1h\x91\xf8N{'
    sql = "select * from foo where bar = '{0}'".format(digest)
    formatted = sqlparse.format(sql, reindent=True)
    tformatted = "select *\nfrom foo\nwhere bar = '{0}'".format(digest)
    if sys.version_info < (3,):
        tformatted = tformatted.decode('unicode-escape')
    assert formatted == tformatted


def test_dont_alias_keywords():
    # The _group_left_right function had a bug where the check for the
    # left side wasn't handled correctly. In one case this resulted in
    # a keyword turning into an identifier.
    p = sqlparse.parse('FROM AS foo')[0]
    assert len(p.tokens) == 5
    assert p.tokens[0].ttype is T.Keyword
    assert p.tokens[2].ttype is T.Keyword


def test_format_accepts_encoding():  # issue20
    sql = load_file('test_cp1251.sql', 'cp1251')
    formatted = sqlparse.format(sql, reindent=True, encoding='cp1251')
    tformatted = u'insert into foo\nvalues (1); -- Песня про надежду\n'

    assert formatted == tformatted


def test_issue90():
    sql = ('UPDATE "gallery_photo" SET "owner_id" = 4018, "deleted_at" = NULL,'
           ' "width" = NULL, "height" = NULL, "rating_votes" = 0,'
           ' "rating_score" = 0, "thumbnail_width" = NULL,'
           ' "thumbnail_height" = NULL, "price" = 1, "description" = NULL')
    formatted = sqlparse.format(sql, reindent=True)
    tformatted = '\n'.join(['UPDATE "gallery_photo"',
                            'SET "owner_id" = 4018,',
                            '    "deleted_at" = NULL,',
                            '    "width" = NULL,',
                            '    "height" = NULL,',
                            '    "rating_votes" = 0,',
                            '    "rating_score" = 0,',
                            '    "thumbnail_width" = NULL,',
                            '    "thumbnail_height" = NULL,',
                            '    "price" = 1,',
                            '    "description" = NULL'])
    assert formatted == tformatted


def test_except_formatting():
    sql = 'SELECT 1 FROM foo WHERE 2 = 3 EXCEPT SELECT 2 FROM bar WHERE 1 = 2'
    formatted = sqlparse.format(sql, reindent=True)
    tformatted = '\n'.join([
        'SELECT 1',
        'FROM foo',
        'WHERE 2 = 3',
        'EXCEPT',
        'SELECT 2',
        'FROM bar',
        'WHERE 1 = 2'
    ])
    assert formatted == tformatted


def test_null_with_as():
    sql = 'SELECT NULL AS c1, NULL AS c2 FROM t1'
    formatted = sqlparse.format(sql, reindent=True)
    tformatted = '\n'.join([
        'SELECT NULL AS c1,',
        '       NULL AS c2',
        'FROM t1'
    ])
    assert formatted == tformatted


def test_issue193_splitting_function():
    sql = """CREATE FUNCTION a(x VARCHAR(20)) RETURNS VARCHAR(20)
BEGIN
 DECLARE y VARCHAR(20);
 RETURN x;
END;
SELECT * FROM a.b;"""
    splitted = sqlparse.split(sql)
    assert len(splitted) == 2


def test_issue194_splitting_function():
    sql = """CREATE FUNCTION a(x VARCHAR(20)) RETURNS VARCHAR(20)
BEGIN
 DECLARE y VARCHAR(20);
 IF (1 = 1) THEN
 SET x = y;
 END IF;
 RETURN x;
END;
SELECT * FROM a.b;"""
    splitted = sqlparse.split(sql)
    assert len(splitted) == 2


def test_issue186_get_type():
    sql = "-- comment\ninsert into foo"
    p = sqlparse.parse(sql)[0]
    assert p.get_type() == 'INSERT'


def test_issue212_py2unicode():
    t1 = sql.Token(T.String, u"schöner ")
    t2 = sql.Token(T.String, u"bug")
    l = sql.TokenList([t1, t2])
    assert str(l) == 'schöner bug'


def test_issue213_leadingws():
    sql = " select * from foo"
    assert sqlparse.format(sql, strip_whitespace=True) == "select * from foo"


def test_issue227_gettype_cte():
    select_stmt = sqlparse.parse('SELECT 1, 2, 3 FROM foo;')
    assert select_stmt[0].get_type() == 'SELECT'
    with_stmt = sqlparse.parse('WITH foo AS (SELECT 1, 2, 3)'
                               'SELECT * FROM foo;')
    assert with_stmt[0].get_type() == 'SELECT'
    with2_stmt = sqlparse.parse('''
        WITH foo AS (SELECT 1 AS abc, 2 AS def),
             bar AS (SELECT * FROM something WHERE x > 1)
        INSERT INTO elsewhere SELECT * FROM foo JOIN bar;
    ''')
    assert with2_stmt[0].get_type() == 'INSERT'


def test_issue207_runaway_format():
    sql = 'select 1 from (select 1 as one, 2 as two, 3 from dual) t0'
    p = sqlparse.format(sql, reindent=True)
    assert p == '\n'.join(["select 1",
                           "from",
                           "  (select 1 as one,",
                           "          2 as two,",
                           "          3",
                           "   from dual) t0"])


def test_case_within_parenthesis():
    # see issue #164
    s = '(case when 1=1 then 2 else 5 end)'
    p = sqlparse.parse(s)[0]
    assert isinstance(p[0][1], sql.Case)
