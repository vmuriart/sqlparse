# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andi Albrecht, albrecht.andi@gmail.com
#
# This module is part of python-sqlparse and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php

class ColumnsSelect(object):
    """Get the columns names of a SELECT query"""

    def process(self, stream):
        mode = 0
        oldValue = ""
        parenthesis = 0

        for token_type, value in stream:
            # Ignore comments
            if token_type in Comment:
                continue

            # We have not detected a SELECT statement
            if mode == 0:
                if token_type in Keyword and value == 'SELECT':
                    mode = 1

            # We have detected a SELECT statement
            elif mode == 1:
                if value == 'FROM':
                    if oldValue:
                        yield oldValue

                    mode = 3  # Columns have been checked

                elif value == 'AS':
                    oldValue = ""
                    mode = 2

                elif (token_type == Punctuation
                      and value == ',' and not parenthesis):
                    if oldValue:
                        yield oldValue
                    oldValue = ""

                elif token_type not in Whitespace:
                    if value == '(':
                        parenthesis += 1
                    elif value == ')':
                        parenthesis -= 1

                    oldValue += value

            # We are processing an AS keyword
            elif mode == 2:
                # We check also for Keywords because a bug in SQLParse
                if token_type == Name or token_type == Keyword:
                    yield value
                    mode = 1
