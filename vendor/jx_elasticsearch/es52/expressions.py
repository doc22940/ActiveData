# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http:# mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import itertools

from jx_base.expressions import Variable, TupleOp, LeavesOp, OrOp, ScriptOp, WhenOp, extend, Literal, NullOp, TrueOp, FalseOp, DivOp, FloorOp, EqOp, NeOp, NotOp, LengthOp, StringOp, RegExpOp, CoalesceOp, MissingOp, ExistsOp, PrefixOp, InOp, CaseOp, AndOp, ConcatOp, BasicIndexOfOp, BasicEqOp, BooleanOp, NULL, FALSE, TRUE, SuffixOp, simplified, BasicStartsWithOp, EsNestedOp, BaseInequalityOp
from jx_elasticsearch.es52.util import es_not, es_script, es_or, es_and, es_missing, pull_functions, MATCH_ALL, MATCH_NONE, es_exists
from jx_python.jx import first
from mo_dots import wrap, Null, set_default, literal_field, Data
from mo_future import text_type
from mo_json import NUMBER, BOOLEAN, OBJECT, INTEGER, python_type_to_json_type, NESTED
from mo_logs import Log, suppress_exception
from mo_math import MAX, OR
from pyLibrary.convert import string2regexp, value2boolean


@extend(Variable)
def to_esfilter(self, schema):
    v = self.var
    cols = schema.values(v, (OBJECT, NESTED))
    if len(cols) == 0:
        return MATCH_NONE
    elif len(cols) == 1:
        c = first(cols)
        return {"term": {c.es_column: True}} if c.es_type == BOOLEAN else es_exists(c.es_column)
    else:
        return es_and([
            {"term": {c.es_column: True}} if c.es_type == BOOLEAN else es_exists(c.es_column)
            for c in cols
        ])


@extend(NeOp)
def to_esfilter(self, schema):
    if not isinstance(self.lhs, Variable) or not isinstance(self.rhs, Literal):
        return self.to_es_script(schema).to_esfilter(schema)

    return es_not({"term": {self.lhs.var: self.rhs.to_esfilter(schema)}})


@extend(CaseOp)
def to_esfilter(self, schema):
    if self.type == BOOLEAN:
        return OrOp(
            [
                AndOp([w.when, w.then])
                for w in self.whens[:-1]
            ] +
            self.whens[-1:]
        ).partial_eval().to_esfilter(schema)
    else:
        Log.error("do not know how to handle")
        return ScriptOp(self.to_es_script(schema).script(schema)).to_esfilter(schema)


@extend(ConcatOp)
def to_esfilter(self, schema):
    if isinstance(self.value, Variable) and isinstance(self.find, Literal):
        return {"regexp": {self.value.var: ".*" + string2regexp(self.find.value) + ".*"}}
    else:
        return ScriptOp( self.to_es_script(schema).script(schema)).to_esfilter(schema)


@extend(Literal)
def to_esfilter(self, schema):
    return self.json


@extend(CoalesceOp)
def to_esfilter(self, schema):
    return {"bool": {"should": [{"exists": {"field": v}} for v in self.terms]}}


@extend(ExistsOp)
def to_esfilter(self, schema):
    return self.field.exists().partial_eval().to_esfilter(schema)


@extend(NullOp)
def to_esfilter(self, schema):
    return MATCH_NONE


@extend(FalseOp)
def to_esfilter(self, schema):
    return MATCH_NONE


@extend(TupleOp)
def to_esfilter(self, schema):
    Log.error("not supported")


@extend(LeavesOp)
def to_esfilter(self, schema):
    Log.error("not supported")


@extend(BaseInequalityOp)
def to_esfilter(self, schema):
    if isinstance(self.lhs, Variable) and isinstance(self.rhs, Literal):
        cols = schema.leaves(self.lhs.var)
        if not cols:
            lhs = self.lhs.var  # HAPPENS DURING DEBUGGING, AND MAYBE IN REAL LIFE TOO
        elif len(cols) == 1:
            lhs = first(cols).es_column
        else:
            Log.error("operator {{op|quote}} does not work on objects", op=self.op)
        return {"range": {lhs: {self.op: self.rhs.value}}}
    else:
        script = self.to_es_script(schema)
        if script.miss is not FALSE:
            Log.error("inequality must be decisive")
        return {"script": es_script(script.expr)}


@extend(DivOp)
def to_esfilter(self, schema):
    return NotOp(self.missing()).partial_eval().to_esfilter(schema)


@extend(FloorOp)
def to_esfilter(self, schema):
    Log.error("Logic error")



@simplified
@extend(EqOp)
def partial_eval(self):
    lhs = self.lhs.partial_eval()
    rhs = self.rhs.partial_eval()
    return EqOp([lhs, rhs])


@extend(EqOp)
def to_esfilter(self, schema):
    if isinstance(self.lhs, Variable) and isinstance(self.rhs, Literal):
        rhs = self.rhs.value
        lhs = self.lhs.var
        cols = schema.leaves(lhs)

        if isinstance(rhs, list):
            if len(rhs) == 1:
                rhs = rhs[0]
            else:
                types = Data()  # MAP JSON TYPE TO LIST OF LITERALS
                for r in rhs:
                    types[python_type_to_json_type[rhs.__class__]] += [r]
                if len(types) == 1:
                    jx_type, values = first(types.items())
                    for c in cols:
                        if jx_type == c.jx_type:
                            return {"terms": {c.es_column: values}}
                    return FALSE.to_esfilter(schema)
                else:
                    return OrOp([
                        EqOp([self.lhs, values])
                        for t, values in types.items()
                    ]).partial_eval().to_esfilter(schema)

        for c in cols:
            if c.jx_type == BOOLEAN:
                rhs = pull_functions[c.jx_type](rhs)
            if python_type_to_json_type[rhs.__class__] == c.jx_type:
                return {"term": {c.es_column: rhs}}
        return FALSE.to_esfilter(schema)
    else:
        return CaseOp([
            WhenOp(self.lhs.missing(), **{"then": self.rhs.missing()}),
            WhenOp(self.rhs.missing(), **{"then": FALSE}),
            BasicEqOp([self.lhs, self.rhs])
        ]).partial_eval().to_esfilter(schema)


@extend(BasicEqOp)
def to_esfilter(self, schema):
    if isinstance(self.lhs, Variable) and isinstance(self.rhs, Literal):
        lhs = self.lhs.var
        cols = schema.leaves(lhs)
        if cols:
            lhs = first(cols).es_column
        rhs = self.rhs.value
        if isinstance(rhs, list):
            if len(rhs) == 1:
                return {"term": {lhs: rhs[0]}}
            else:
                return {"terms": {lhs: rhs}}
        else:
            return {"term": {lhs: rhs}}
    else:
        return self.to_es_script(schema).to_esfilter(schema)


@extend(MissingOp)
def to_esfilter(self, schema):
    if isinstance(self.expr, Variable):
        cols = schema.leaves(self.expr.var)
        if not cols:
            return MATCH_ALL
        elif len(cols) == 1:
            return es_missing(first(cols).es_column)
        else:
            return es_and([
                es_missing(c.es_column) for c in cols
            ])
    else:
        return ScriptOp(self.to_es_script(schema).script(schema)).to_esfilter(schema)


@extend(NeOp)
def to_esfilter(self, schema):
    if isinstance(self.lhs, Variable) and isinstance(self.rhs, Literal):
        columns = schema.values(self.lhs.var)
        if len(columns) == 0:
            return MATCH_ALL
        elif len(columns) == 1:
            return es_not({"term": {first(columns).es_column: self.rhs.value}})
        else:
            Log.error("column split to multiple, not handled")
    else:
        lhs = self.lhs.partial_eval().to_es_script(schema)
        rhs = self.rhs.partial_eval().to_es_script(schema)

        if lhs.many:
            if rhs.many:
                return es_not(
                    ScriptOp(
                        (
                            "(" + lhs.expr + ").size()==(" + rhs.expr + ").size() && " +
                            "(" + rhs.expr + ").containsAll(" + lhs.expr + ")"
                        )
                    ).to_esfilter(schema)
                )
            else:
                return es_not(
                    ScriptOp("(" + lhs.expr + ").contains(" + rhs.expr + ")").to_esfilter(schema)
                )
        else:
            if rhs.many:
                return es_not(
                    ScriptOp("(" + rhs.expr + ").contains(" + lhs.expr + ")").to_esfilter(schema)
                )
            else:
                return es_not(
                    ScriptOp("(" + lhs.expr + ") != (" + rhs.expr + ")").to_esfilter(schema)
                )

@extend(NotOp)
def to_esfilter(self, schema):
    if isinstance(self.term, MissingOp) and isinstance(self.term.expr, Variable):
        # PREVENT RECURSIVE LOOP
        v = self.term.expr.var
        cols = schema.values(v, (OBJECT, NESTED))
        if len(cols) == 0:
            return MATCH_NONE
        elif len(cols) == 1:
            return {"exists": {"field": first(cols).es_column}}
        else:
            return es_and([{"exists": {"field": c.es_column}} for c in cols])
    else:
        operand = self.term.to_esfilter(schema)
        return es_not(operand)


@extend(AndOp)
def to_esfilter(self, schema):
    if not len(self.terms):
        return MATCH_ALL
    else:
        return es_and([t.to_esfilter(schema) for t in self.terms])


@extend(OrOp)
def to_esfilter(self, schema):

    if schema.snowflake.namespace.es_cluster.version.startswith("5."):
        # VERSION 5.2.x
        # WE REQUIRE EXIT-EARLY SEMANTICS, OTHERWISE EVERY EXPRESSION IS A SCRIPT EXPRESSION
        # {"bool":{"should"  :[a, b, c]}} RUNS IN PARALLEL
        # {"bool":{"must_not":[a, b, c]}} ALSO RUNS IN PARALLEL

        # OR(x) == NOT(AND(NOT(xi) for xi in x))
        output = es_not(es_and([
            NotOp(t).partial_eval().to_esfilter(schema)
            for t in self.terms
        ]))
        return output
    else:
        # VERSION 6.2
        return es_or([t.partial_eval().to_esfilter(schema) for t in self.terms])


@extend(BooleanOp)
def to_esfilter(self, schema):
    if isinstance(self.term, Variable):
        return {"term": {self.term.var: True}}
    else:
        return self.to_es_script(schema).to_esfilter(schema)


@extend(LengthOp)
def to_esfilter(self, schema):
    return {"regexp": {self.var.var: self.pattern.value}}


@extend(RegExpOp)
def to_esfilter(self, schema):
    if isinstance(self.pattern, Literal) and isinstance(self.var, Variable):
        cols = schema.leaves(self.var.var)
        if len(cols) == 0:
            return MATCH_NONE
        elif len(cols) == 1:
            return {"regexp": {first(cols).es_column: self.pattern.value}}
        else:
            Log.error("regex on not supported ")
    else:
        Log.error("regex only accepts a variable and literal pattern")


@extend(TrueOp)
def to_esfilter(self, schema):
    return MATCH_ALL


@extend(EsNestedOp)
def to_esfilter(self, schema):
    if self.path.var == '.':
        return {"query": self.query.to_esfilter(schema)}
    else:
        return {"nested": {
            "path": self.path.var,
            "query": self.query.to_esfilter(schema)
        }}


@extend(BasicStartsWithOp)
def to_esfilter(self, schema):
    if not self.value:
        return MATCH_ALL
    elif isinstance(self.value, Variable) and isinstance(self.prefix, Literal):
        var = first(schema.leaves(self.value.var)).es_column
        return {"prefix": {var: self.prefix.value}}
    else:
        output = self.to_es_script(schema)
        if output is false_script:
            return MATCH_NONE
        return ScriptOp(output.script(schema)).to_esfilter(schema)


@extend(PrefixOp)
def partial_eval(self):
    if not self.expr:
        return TRUE

    expr = StringOp(self.expr).partial_eval()
    prefix = StringOp(self.prefix).partial_eval()

    if self.expr is NULL:
        return TRUE

    return PrefixOp([expr, prefix])


@extend(PrefixOp)
def to_esfilter(self, schema):
    if isinstance(self.prefix, Literal) and not self.prefix.value:
        return MATCH_ALL

    expr = self.expr

    if expr is NULL:
        return es_not(MATCH_ALL)
    elif not expr:
        return MATCH_ALL

    if isinstance(expr, StringOp):
        expr = expr.term

    if isinstance(expr, Variable) and isinstance(self.prefix, Literal):
        var = first(schema.leaves(expr.var)).es_column
        return {"prefix": {var: self.prefix.value}}
    else:
        return ScriptOp(self.to_es_script(schema).script(schema)).to_esfilter(schema)


@extend(SuffixOp)
def to_esfilter(self, schema):
    if not self.suffix:
        return MATCH_ALL
    elif isinstance(self.expr, Variable) and isinstance(self.suffix, Literal):
        var = first(schema.leaves(self.expr.var)).es_column
        return {"regexp": {var: ".*"+string2regexp(self.suffix.value)}}
    else:
        return ScriptOp(self.to_es_script(schema).script(schema)).to_esfilter(schema)


@extend(InOp)
def to_esfilter(self, schema):
    if isinstance(self.value, Variable):
        var = self.value.var
        cols = schema.leaves(var)
        if not cols:
            Log.error("expecting {{var}} to be a column", var=var)
        col = first(cols)
        var = col.es_column

        if col.jx_type == BOOLEAN:
            if isinstance(self.superset, Literal) and not isinstance(self.superset.value, (list, tuple)):
                return {"term": {var: value2boolean(self.superset.value)}}
            else:
                return {"terms": {var: map(value2boolean, self.superset.value)}}
        else:
            if isinstance(self.superset, Literal) and not isinstance(self.superset.value, (list, tuple)):
                return {"term": {var: self.superset.value}}
            else:
                return {"terms": {var: self.superset.value}}
    else:
        return ScriptOp(self.to_es_script(schema).script(schema)).to_esfilter(schema)


@extend(ScriptOp)
def to_esfilter(self, schema):
    return {"script": es_script(self.script)}


@extend(WhenOp)
def to_esfilter(self, schema):
    output = OrOp([
        AndOp([self.when, BooleanOp(self.then)]),
        AndOp([NotOp(self.when), BooleanOp(self.els_)])
    ]).partial_eval()

    return output.to_esfilter(schema)


@extend(BasicIndexOfOp)
def to_esfilter(self, schema):
    return ScriptOp(self.to_es_script(schema).script(schema)).to_esfilter(schema)


def simplify_esfilter(esfilter):
    try:
        output = wrap(_normalize(wrap(esfilter)))
        output.isNormal = None
        return output
    except Exception as e:
        from mo_logs import Log

        Log.unexpected("programmer error", cause=e)


def _normalize(esfilter):
    """
    TODO: DO NOT USE Data, WE ARE SPENDING TOO MUCH TIME WRAPPING/UNWRAPPING
    REALLY, WE JUST COLLAPSE CASCADING `and` AND `or` FILTERS
    """
    if esfilter == MATCH_ALL or esfilter == MATCH_NONE or esfilter.isNormal:
        return esfilter

    # Log.note("from: " + convert.value2json(esfilter))
    isDiff = True

    while isDiff:
        isDiff = False

        if esfilter.bool.filter:
            terms = esfilter.bool.filter
            for (i0, t0), (i1, t1) in itertools.product(enumerate(terms), enumerate(terms)):
                if i0 == i1:
                    continue  # SAME, IGNORE
                # TERM FILTER ALREADY ASSUMES EXISTENCE
                with suppress_exception:
                    if t0.exists.field != None and t0.exists.field == t1.term.items()[0][0]:
                        terms[i0] = MATCH_ALL
                        continue

                # IDENTICAL CAN BE REMOVED
                with suppress_exception:
                    if t0 == t1:
                        terms[i0] = MATCH_ALL
                        continue

                # MERGE range FILTER WITH SAME FIELD
                if i0 > i1:
                    continue  # SAME, IGNORE
                with suppress_exception:
                    f0, tt0 = t0.range.items()[0]
                    f1, tt1 = t1.range.items()[0]
                    if f0 == f1:
                        set_default(terms[i0].range[literal_field(f1)], tt1)
                        terms[i1] = MATCH_ALL

            output = []
            for a in terms:
                if isinstance(a, (list, set)):
                    from mo_logs import Log

                    Log.error("and clause is not allowed a list inside a list")
                a_ = _normalize(a)
                if a_ is not a:
                    isDiff = True
                a = a_
                if a == MATCH_ALL:
                    isDiff = True
                    continue
                if a == MATCH_NONE:
                    return MATCH_NONE
                if a.bool.filter:
                    isDiff = True
                    a.isNormal = None
                    output.extend(a.bool.filter)
                else:
                    a.isNormal = None
                    output.append(a)
            if not output:
                return MATCH_ALL
            elif len(output) == 1:
                # output[0].isNormal = True
                esfilter = output[0]
                break
            elif isDiff:
                esfilter = es_and(output)
            continue

        if esfilter.bool.should:
            output = []
            for a in esfilter.bool.should:
                a_ = _normalize(a)
                if a_ is not a:
                    isDiff = True
                a = a_

                if a.bool.should:
                    a.isNormal = None
                    isDiff = True
                    output.extend(a.bool.should)
                else:
                    a.isNormal = None
                    output.append(a)
            if not output:
                return MATCH_NONE
            elif len(output) == 1:
                esfilter = output[0]
                break
            elif isDiff:
                esfilter = wrap(es_or(output))
            continue

        if esfilter.term != None:
            if esfilter.term.keys():
                esfilter.isNormal = True
                return esfilter
            else:
                return MATCH_ALL

        if esfilter.terms:
            for k, v in esfilter.terms.items():
                if len(v) > 0:
                    if OR(vv == None for vv in v):
                        rest = [vv for vv in v if vv != None]
                        if len(rest) > 0:
                            output = es_or([
                                es_missing(k),
                                {"terms": {k: rest}}
                            ])
                        else:
                            output = es_missing(k)
                        output.isNormal = True
                        return output
                    else:
                        esfilter.isNormal = True
                        return esfilter
            return MATCH_NONE

        if esfilter.bool.must_not:
            _sub = esfilter.bool.must_not
            sub = _normalize(_sub)
            if sub == MATCH_NONE:
                return MATCH_ALL
            elif sub == MATCH_ALL:
                return MATCH_NONE
            elif sub is not _sub:
                sub.isNormal = None
                return wrap({"bool": {"must_not": sub, "isNormal": True}})
            else:
                sub.isNormal = None

    esfilter.isNormal = True
    return esfilter


def split_expression_by_depth(where, schema, output=None, var_to_depth=None):
    """
    :param where: EXPRESSION TO INSPECT
    :param schema: THE SCHEMA
    :param output:
    :param var_to_depth: MAP FROM EACH VARIABLE NAME TO THE DEPTH
    :return:
    """
    """
    It is unfortunate that ES can not handle expressions that
    span nested indexes.  This will split your where clause
    returning {"and": [filter_depth0, filter_depth1, ...]}
    """
    vars_ = where.vars()

    if var_to_depth is None:
        if not vars_:
            return Null
        # MAP VARIABLE NAMES TO HOW DEEP THEY ARE
        var_to_depth = {v.var: max(len(c.nested_path) - 1, 0) for v in vars_ for c in schema[v.var]}
        all_depths = set(var_to_depth.values())
        if len(all_depths) == 0:
            all_depths = {0}
        output = wrap([[] for _ in range(MAX(all_depths) + 1)])
    else:
        all_depths = set(var_to_depth[v.var] for v in vars_)

    if len(all_depths) == 1:
        output[first(all_depths)] += [where]
    elif isinstance(where, AndOp):
        for a in where.terms:
            split_expression_by_depth(a, schema, output, var_to_depth)
    else:
        Log.error("Can not handle complex where clause")

    return output


def split_expression_by_path(where, schema, output=None, var_to_columns=None):
    """
    :param where: EXPRESSION TO INSPECT
    :param schema: THE SCHEMA
    :param output: THE MAP FROM PATH TO EXPRESSION WE WANT UPDATED
    :param var_to_columns: MAP FROM EACH VARIABLE NAME TO THE DEPTH
    :return: output: A MAP FROM PATH TO EXPRESSION
    """
    if var_to_columns is None:
        var_to_columns = {v.var: schema.leaves(v.var) for v in where.vars()}
        output = wrap({schema.query_path[0]: []})
        if not var_to_columns:
            output["\\."] += [where]  # LEGIT EXPRESSIONS OF ZERO VARIABLES
            return output

    where_vars = where.vars()
    all_paths = set(c.nested_path[0] for v in where_vars for c in var_to_columns[v.var])

    if len(all_paths) == 0:
        output["\\."] += [where]
    elif len(all_paths) == 1:
        output[literal_field(first(all_paths))] += [where.map({v.var: c.es_column for v in where.vars() for c in var_to_columns[v.var]})]
    elif isinstance(where, AndOp):
        for w in where.terms:
            split_expression_by_path(w, schema, output, var_to_columns)
    else:
        Log.error("Can not handle complex where clause")

    return output


def box(script):
    """
    :param es_script:
    :return: TEXT EXPRESSION WITH NON OBJECTS BOXXED
    """
    if script.type is BOOLEAN:
        return "Boolean.valueOf(" + text_type(script.expr) + ")"
    elif script.type is INTEGER:
        return "Integer.valueOf(" + text_type(script.expr) + ")"
    elif script.type is NUMBER:
        return "Double.valueOf(" + text_type(script.expr) + ")"
    else:
        return script.expr

def get_type(var_name):
    type_ = var_name.split(".$")[1:]
    if not type_:
        return "j"
    return json_type_to_es_script_type.get(type_[0], "j")


json_type_to_es_script_type = {
    "string": "s",
    "boolean": "b",
    "number": "n"
}


from jx_elasticsearch.es52.painless import false_script
